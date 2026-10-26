# -*- coding: utf-8 -*-
"""Etapas 10B/10C: registro WS y serializacion conservadora MD + MI."""
from __future__ import absolute_import

import importlib
import os
import sys
import threading
import types
import unittest
from datetime import datetime
from xml.etree import ElementTree

from mock import Mock
from types import ModuleType
# Simulamos el módulo tools que proporciona GISCE-ERP.
tools_mock = ModuleType('tools')
tools_mock.__path__ = []  # Permite tratarlo como paquete
tools_mock.config = Mock()

# Simulamos tools.translate.
translate_mock = ModuleType('tools.translate')
translate_mock._ = lambda text: text

# Registramos ambos módulos.
tools_mock.translate = translate_mock

sys.modules['tools'] = tools_mock
sys.modules['tools.translate'] = translate_mock

from test_siom_control_ejecucion import FakeFields, FakeOsV, FakeBusinessCursor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
APP = os.path.join(ROOT, 'giscedata_omie_api')


class ServicioStore(object):
    def __init__(self):
        self.rows = []
        self.counter = 1
        self.lock = threading.RLock()
        self.commits = 0
        self.closed = 0
        self.queries = []

    def cursor(self):
        return ServicioCursor(self)


class ServicioCursor(object):
    def __init__(self, db):
        self.db = db
        self.locked = False
        self.result = []
        self.rowcount = 0
        self.pending_insert = None
        self.pending_update = None

    def execute(self, sql, params=()):
        clean = ' '.join(sql.lower().split())
        self.db.queries.append((sql, params))
        self.rowcount = 0
        if 'pg_advisory_xact_lock' in clean:
            self.db.lock.acquire()
            self.locked = True
        elif clean.startswith('select id, servicio, estado'):
            pending = [r for r in self.db.rows if r['servicio'] in
                       ('ServicioAltaOfertasMD', 'ServicioAltaOfertasMI')
                       and r['estado'] in ('reservada', 'incierta')]
            self.result = [(r['id'], r['servicio'], r['estado']) for r in pending[-1:]]
        elif clean.startswith('insert into giscedata_omie_siom_service_execution'):
            new_id = self.db.counter
            self.db.counter += 1
            self.pending_insert = {
                'id': new_id, 'servicio': params[0], 'oferta_id': params[1],
                'usuario_id': params[2], 'fecha_intento': datetime.utcnow(),
                'estado': 'reservada', 'detalle': '', 'fecha_fin': None}
            self.result = [(new_id,)]
        elif clean.startswith('update giscedata_omie_siom_service_execution'):
            if "estado='reconciliada'" in clean:
                row = next((r for r in self.db.rows if r['id'] == params[1] and
                            r['estado'] == 'incierta' and
                            r['servicio'] in ('ServicioAltaOfertasMD', 'ServicioAltaOfertasMI')), None)
                self.pending_update = (row, 'reconciliada', params[0]) if row else None
            else:
                row = next((r for r in self.db.rows if r['id'] == params[2] and
                            r['estado'] == 'reservada'), None)
                self.pending_update = (row, params[0], params[1]) if row else None
            self.rowcount = int(self.pending_update is not None)
        else:
            raise AssertionError('SQL no soportado: %s' % sql)

    def fetchone(self):
        if not self.result:
            return None
        return self.result.pop(0)

    def commit(self):
        if self.pending_insert:
            self.db.rows.append(self.pending_insert)
        if self.pending_update:
            row, state, detail = self.pending_update
            row['estado'], row['detalle'], row['fecha_fin'] = state, detail, datetime.utcnow()
        self.pending_insert = self.pending_update = None
        self.db.commits += 1
        self._unlock()

    def _unlock(self):
        if self.locked:
            self.db.lock.release()
            self.locked = False

    def rollback(self):
        self.pending_insert = self.pending_update = None
        self._unlock()

    def close(self):
        self.db.closed += 1
        self._unlock()


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backup = {}
        for k in ('osv', 'giscedata_omie_api',
                  'giscedata_omie_api.giscedata_omie_siom_service_execution'):
            cls.backup[k] = sys.modules.get(k)
        mock = types.ModuleType('osv')
        mock.osv = type('OSV', (), {'osv': FakeOsV})
        mock.fields = FakeFields()
        sys.modules['osv'] = mock
        pkg = types.ModuleType('giscedata_omie_api')
        pkg.__path__ = [APP]
        sys.modules[pkg.__name__] = pkg
        cls.module = importlib.import_module('giscedata_omie_api.giscedata_omie_siom_service_execution')

    @classmethod
    def tearDownClass(cls):
        for k, original in cls.backup.items():
            if original is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = original

    def setUp(self):
        self.db = ServicioStore()
        self.cr = FakeBusinessCursor()
        self.model = self.module.GiscedataOmieSiomServiceExecution()
        self.model._nueva_conexion = lambda cr: self.db.cursor()

    def test_consulta_auxiliar_registrada_y_respuesta_original(self):
        respuesta = object()
        self.assertIs(
            self.model.ejecutar_servicio(self.cr, 7, 'ServicioConsultaMercados',
                                         lambda: respuesta), respuesta)
        self.assertEqual(len(self.db.rows), 1)
        self.assertEqual(self.db.rows[0]['estado'], 'respondida')
        self.assertIsNone(self.db.rows[0]['oferta_id'])

    def test_un_envio_md_bloquea_mi_mientras_espera(self):
        def md():
            with self.assertRaises(self.module.EnvioOMIEPendiente):
                self.model.ejecutar_servicio(self.cr, 8, 'ServicioAltaOfertasMI',
                                            lambda: self.fail('No debe tocar OMIE'), oferta_id=2)
            return 'ok MD'
        self.assertEqual(self.model.ejecutar_servicio(
            self.cr, 7, 'ServicioAltaOfertasMD', md, oferta_id=1), 'ok MD')
        self.assertEqual(len(self.db.rows), 1)
        self.assertEqual(self.db.rows[0]['estado'], 'respondida')

    def test_dos_envios_tras_respuesta_si_se_permiten(self):
        self.model.ejecutar_servicio(self.cr, 7, 'ServicioAltaOfertasMD',
                                    lambda: 'ok', oferta_id=1)
        self.model.ejecutar_servicio(self.cr, 7, 'ServicioAltaOfertasMI',
                                    lambda: 'ok', oferta_id=2)
        self.assertEqual(len(self.db.rows), 2)

    def test_timeout_deja_incierta_y_bloquea_ambos_mercados(self):
        def fallar():
            raise IOError('time out')
        with self.assertRaises(IOError):
            self.model.ejecutar_servicio(self.cr, 7, 'ServicioAltaOfertasMD',
                                        fallar, oferta_id=1)
        with self.assertRaises(self.module.EnvioOMIEPendiente):
            self.model.ejecutar_servicio(self.cr, 7, 'ServicioAltaOfertasMI',
                                        lambda: 'prohibido', oferta_id=2)
        self.assertEqual(self.db.rows[0]['estado'], 'incierta')

    def test_no_confunde_servicios_consulta_con_envios(self):
        self.model.ejecutar_servicio(self.cr, 7, 'ServicioAltaOfertasMD',
                                    lambda: self.model.ejecutar_servicio(
                                        self.cr, 8, 'ServicioConsultaFechaHora',
                                        lambda: 'fecha'), oferta_id=1)
        self.assertEqual([r['estado'] for r in self.db.rows], ['respondida', 'respondida'])

    def test_reserva_confirmada_antes_de_soap(self):
        def ejecutar():
            self.assertEqual(len(self.db.rows), 1)
            self.assertEqual(self.db.rows[0]['estado'], 'reservada')
            self.assertEqual(self.db.commits, 1)
            return True
        self.model.ejecutar_servicio(self.cr, 7, 'ServicioAltaOfertasMD',
                                    ejecutar, oferta_id=1)
        self.assertFalse(self.cr.called)
        self.assertEqual(self.db.commits, 2)

    def test_excepcion_servicio_informativo_no_bloquea_ofertas(self):
        def fallar():
            raise IOError('error')
        with self.assertRaises(IOError):
            self.model.ejecutar_servicio(self.cr, 7, 'ServicioConsultaMercados', fallar)
        self.model.ejecutar_servicio(self.cr, 7, 'ServicioAltaOfertasMD',
                                    lambda: True, oferta_id=1)
        self.assertEqual(self.db.rows[0]['estado'], 'incierta')
        self.assertEqual(self.db.rows[1]['estado'], 'respondida')

    def test_conciliacion_solo_admin_con_justificacion(self):
        def fallar():
            raise IOError('error')
        with self.assertRaises(IOError):
            self.model.ejecutar_servicio(self.cr, 7, 'ServicioAltaOfertasMI', fallar, oferta_id=2)
        with self.assertRaises(Exception):
            self.model.conciliar_envio(self.cr, 7, 1, 'Consultado en OMIE, no existe')
        with self.assertRaises(ValueError):
            self.model.conciliar_envio(self.cr, 1, 1, 'ok')
        self.assertTrue(self.model.conciliar_envio(self.cr, 1, 1,
                                                  'Comprobado en OMIE: envio no procesado'))
        self.model.ejecutar_servicio(self.cr, 8, 'ServicioAltaOfertasMD',
                                    lambda: True, oferta_id=3)
        self.assertEqual(self.db.rows[0]['estado'], 'reconciliada')

    def test_concurrencia_dos_threads_solo_un_envio_simultaneo(self):
        entrando, liberar = threading.Event(), threading.Event()
        resultados = []
        def hilo1():
            def lento():
                entrando.set()
                self.assertTrue(liberar.wait(2.0))
                return True
            resultados.append(self.model.ejecutar_servicio(
                self.cr, 7, 'ServicioAltaOfertasMD', lento, oferta_id=1))
        t = threading.Thread(target=hilo1)
        t.start()
        self.assertTrue(entrando.wait(2.0))
        try:
            with self.assertRaises(self.module.EnvioOMIEPendiente):
                self.model.ejecutar_servicio(self.cr, 8, 'ServicioAltaOfertasMI',
                                            lambda: False, oferta_id=2)
        finally:
            liberar.set()
            t.join(2)
        self.assertFalse(t.is_alive())
        self.assertEqual(resultados, [True])
        self.assertEqual(len(self.db.rows), 1)

    def test_servicios_y_ofertas_integrados_en_codigo_erp(self):
        with open(os.path.join(APP, 'giscedata_omie_oferta.py')) as f:
            oferta = f.read()
        for token in ('ServicioAltaOfertasMD', 'ServicioAltaOfertasMI',
                      'ejecutar_servicio(', 'oferta_id=oferta_id'):
            self.assertIn(token, oferta)
        for name, service in (
                ('wizard_consulta_sesiones.py', 'ServicioConsultaMercados'),
                ('wizard_consulta_fecha_hora.py', 'ServicioConsultaFechaHora'),
                ('wizard_consulta_datos_usuario.py', 'ServicioConsultaDatosUsuario')):
            with open(os.path.join(APP, 'wizard', name)) as f:
                contenido = f.read()
            self.assertIn('ejecutar_servicio(', contenido)
            self.assertIn(service, contenido)


if __name__ == '__main__':
    unittest.main()
