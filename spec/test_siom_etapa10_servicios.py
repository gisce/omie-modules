# -*- coding: utf-8 -*-
"""Etapas 10B/10C: registro WS y serializacion conservadora MD + MI."""
from __future__ import absolute_import

import importlib
import os
import sys
import threading
import types
import unittest
from datetime import datetime, timedelta
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
        self.pending_updates = []

    def execute(self, sql, params=()):
        clean = ' '.join(sql.lower().split())
        self.db.queries.append((sql, params))
        self.rowcount = 0
        self.result = []
        if 'pg_advisory_xact_lock' in clean:
            self.db.lock.acquire()
            self.locked = True
        elif clean.startswith('select id, servicio, estado'):
            changes = {r['id']: state for r, state, detail in self.pending_updates}
            pending = [(r['id'], r['servicio'], changes.get(r['id'], r['estado']))
                       for r in self.db.rows if r['servicio'] in
                       ('ServicioAltaOfertasMD', 'ServicioAltaOfertasMI') and
                       changes.get(r['id'], r['estado']) in
                       ('preparada', 'enviando', 'incierta', 'reservada')]
            self.result = pending[-1:]
        elif clean.startswith('select estado,'):
            row = next((r for r in self.db.rows if r['id'] == params[1] and
                        r['servicio'] in ('ServicioAltaOfertasMD',
                                         'ServicioAltaOfertasMI')), None)
            if row:
                self.result = [(row['estado'],
                                row['fecha_intento'] <= datetime.utcnow() -
                                timedelta(seconds=params[0]))]
        elif clean.startswith('insert into giscedata_omie_siom_service_execution'):
            new_id = self.db.counter
            self.db.counter += 1
            self.pending_insert = {
                'id': new_id, 'servicio': params[0], 'oferta_id': params[1],
                'usuario_id': params[2], 'fecha_intento': datetime.utcnow(),
                'estado': params[3], 'detalle': params[4], 'fecha_fin': None}
            self.result = [(new_id,)]
        elif clean.startswith('update giscedata_omie_siom_service_execution'):
            if "estado='cancelada'" in clean:
                old = datetime.utcnow() - timedelta(seconds=params[0])
                rows = [r for r in self.db.rows if r['estado'] == 'preparada' and
                        r['servicio'] in ('ServicioAltaOfertasMD', 'ServicioAltaOfertasMI')
                        and r['fecha_intento'] <= old]
                for row in rows:
                    self.pending_updates.append((row, 'cancelada',
                                                 'Preparacion caducada: anulada antes del envio SOAP'))
                self.rowcount = len(rows)
            elif "set estado='enviando'" in clean:
                row = next((r for r in self.db.rows if r['id'] == params[0] and
                            r['estado'] == 'preparada'), None)
                if row:
                    self.pending_updates.append((row, 'enviando', 'Envio SOAP autorizado'))
                    self.rowcount = 1
            elif "estado='reconciliada'" in clean:
                row = next((r for r in self.db.rows if r['id'] == params[1] and
                            r['estado'] == params[2] and
                            r['servicio'] in ('ServicioAltaOfertasMD',
                                             'ServicioAltaOfertasMI')), None)
                if row:
                    self.pending_updates.append((row, 'reconciliada', params[0]))
                    self.rowcount = 1
            else:
                row = next((r for r in self.db.rows if r['id'] == params[2] and
                            r['estado'] == 'enviando'), None)
                if row:
                    self.pending_updates.append((row, params[0], params[1]))
                    self.rowcount = 1
        else:
            raise AssertionError('SQL no soportado: %s' % sql)

    def fetchone(self):
        if not self.result:
            return None
        return self.result.pop(0)

    def commit(self):
        if self.pending_insert:
            self.db.rows.append(self.pending_insert)
        for row, state, detail in self.pending_updates:
            row['estado'], row['detalle'] = state, detail
            if state not in ('enviando',):
                row['fecha_fin'] = datetime.utcnow()
        self.pending_insert = None
        self.pending_updates = []
        self.db.commits += 1
        self._unlock()

    def _unlock(self):
        if self.locked:
            self.db.lock.release()
            self.locked = False

    def rollback(self):
        self.pending_insert = None
        self.pending_updates = []
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
            self.assertEqual(self.db.rows[0]['estado'], 'enviando')
            self.assertEqual(self.db.commits, 2)
            return True
        self.model.ejecutar_servicio(self.cr, 7, 'ServicioAltaOfertasMD',
                                    ejecutar, oferta_id=1)
        self.assertFalse(self.cr.called)
        self.assertEqual(self.db.commits, 3)

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

    def test_10d1_reserva_preparada_sin_soap_y_promocion_antes_de_enviar(self):
        envio = self.model._reservar(self.cr, 7, 'ServicioAltaOfertasMD', oferta_id=11)
        self.assertEqual(self.db.rows[0]['estado'], 'preparada')
        self.assertEqual(self.db.commits, 1)
        self.model._iniciar_envio(self.cr, envio)
        self.assertEqual(self.db.rows[0]['estado'], 'enviando')
        self.assertEqual(self.db.commits, 2)
        self.model._finalizar(self.cr, envio, 'respondida', 'Ok')
        self.assertEqual(self.db.rows[0]['estado'], 'respondida')

    def test_10d1_preparada_reciente_no_se_cancela(self):
        self.model._reservar(self.cr, 7, 'ServicioAltaOfertasMD', oferta_id=11)
        self.assertEqual(self.model.recuperar_envios_pendientes(self.cr, 7), 0)
        with self.assertRaises(self.module.EnvioOMIEPendiente):
            self.model._reservar(self.cr, 8, 'ServicioAltaOfertasMI', oferta_id=12)
        self.assertEqual(self.db.rows[0]['estado'], 'preparada')

    def test_10d1_preparada_antigua_se_cancela_y_deja_pasar_mi(self):
        self.model._reservar(self.cr, 7, 'ServicioAltaOfertasMD', oferta_id=11)
        self.db.rows[0]['fecha_intento'] -= timedelta(minutes=5)
        self.assertEqual(self.model.recuperar_envios_pendientes(self.cr, 7), 1)
        self.assertEqual(self.db.rows[0]['estado'], 'cancelada')
        self.assertIsNotNone(self.db.rows[0]['fecha_fin'])
        self.assertTrue(self.model.ejecutar_servicio(
            self.cr, 7, 'ServicioAltaOfertasMI', lambda: True, oferta_id=12))
        self.assertEqual([r['estado'] for r in self.db.rows],
                         ['cancelada', 'respondida'])

    def test_10d1_preparada_caducada_se_recupera_durante_reserva(self):
        self.model._reservar(self.cr, 7, 'ServicioAltaOfertasMD', oferta_id=11)
        self.db.rows[0]['fecha_intento'] -= timedelta(minutes=5)
        # No hace falta llamar explicitamente a recuperar: _reservar lo hace.
        nuevo = self.model._reservar(self.cr, 7, 'ServicioAltaOfertasMI', oferta_id=12)
        self.assertEqual(nuevo, 2)
        self.assertEqual([r['estado'] for r in self.db.rows],
                         ['cancelada', 'preparada'])

    def test_10d1_cas_perdida_no_permite_soap(self):
        envio = self.model._reservar(self.cr, 7, 'ServicioAltaOfertasMD', oferta_id=11)
        self.db.rows[0]['fecha_intento'] -= timedelta(minutes=5)
        self.model.recuperar_envios_pendientes(self.cr, 7)
        with self.assertRaises(self.module.EnvioOMIEPendiente):
            self.model._iniciar_envio(self.cr, envio)
        self.assertEqual(self.db.rows[0]['estado'], 'cancelada')

    def test_10d1_cas_cancelada_no_invoca_soap_ni_una_vez(self):
        calls = []
        iniciar = self.model._iniciar_envio
        def cancelar_antes(cr, execution_id):
            self.db.rows[0]['fecha_intento'] -= timedelta(minutes=5)
            self.model.recuperar_envios_pendientes(cr, 7)
            return iniciar(cr, execution_id)
        self.model._iniciar_envio = cancelar_antes
        with self.assertRaises(self.module.EnvioOMIEPendiente):
            self.model.ejecutar_servicio(
                self.cr, 7, 'ServicioAltaOfertasMD',
                lambda: calls.append('SOAP'), oferta_id=11)
        self.assertEqual(calls, [])
        self.assertEqual(self.db.rows[0]['estado'], 'cancelada')

    def test_10d1_enviando_antiguo_nunca_se_libera_solo(self):
        envio = self.model._reservar(self.cr, 7, 'ServicioAltaOfertasMD', oferta_id=11)
        self.model._iniciar_envio(self.cr, envio)
        self.db.rows[0]['fecha_intento'] -= timedelta(days=2)
        self.assertEqual(self.model.recuperar_envios_pendientes(self.cr, 7), 0)
        with self.assertRaises(self.module.EnvioOMIEPendiente):
            self.model._reservar(self.cr, 8, 'ServicioAltaOfertasMI', oferta_id=12)
        self.assertEqual(self.db.rows[0]['estado'], 'enviando')

    def test_10d1_conciliar_enviando_solo_con_pruebas_y_antiguedad(self):
        envio = self.model._reservar(self.cr, 7, 'ServicioAltaOfertasMD', oferta_id=11)
        self.model._iniciar_envio(self.cr, envio)
        razon = 'Comprobado contra OMIE y proceso ERP finalizado'
        with self.assertRaises(ValueError):
            self.model.conciliar_envio(self.cr, 1, envio, razon)
        with self.assertRaises(ValueError):
            self.model.conciliar_envio(self.cr, 1, envio, razon,
                                      proceso_terminado=True)
        self.db.rows[0]['fecha_intento'] -= timedelta(minutes=10)
        self.assertTrue(self.model.conciliar_envio(self.cr, 1, envio, razon,
                                                   proceso_terminado=True))
        self.assertEqual(self.db.rows[0]['estado'], 'reconciliada')
        self.assertTrue(self.model.ejecutar_servicio(
            self.cr, 7, 'ServicioAltaOfertasMI', lambda: True, oferta_id=12))

    def test_10d1_legacy_reservada_conserva_bloqueo(self):
        envio = self.model._reservar(self.cr, 7, 'ServicioAltaOfertasMD', oferta_id=11)
        self.db.rows[0]['estado'] = 'reservada'
        self.db.rows[0]['fecha_intento'] -= timedelta(days=1)
        self.assertEqual(self.model.recuperar_envios_pendientes(self.cr, 7), 0)
        with self.assertRaises(self.module.EnvioOMIEPendiente):
            self.model._reservar(self.cr, 8, 'ServicioAltaOfertasMI', oferta_id=12)
        with self.assertRaises(ValueError):
            self.model.conciliar_envio(
                self.cr, 1, envio, 'Resultado contrastado en OMIE')

    def test_10d1_preparada_no_conciliable_manualmente(self):
        envio = self.model._reservar(self.cr, 7, 'ServicioAltaOfertasMD', oferta_id=11)
        self.db.rows[0]['fecha_intento'] -= timedelta(days=1)
        with self.assertRaises(ValueError):
            self.model.conciliar_envio(
                self.cr, 1, envio, 'Verificado manualmente en OMIE',
                proceso_terminado=True)
        self.assertEqual(self.db.rows[0]['estado'], 'preparada')

    def test_10d1_migracion_no_declara_reserva_antigua_seguramente_cancelable(self):
        path = os.path.join(APP, 'migrations', '5.0.26.12',
                            'post-0006_siom_envio_recuperacion.py')
        with open(path) as f:
            codigo = f.read()
        self.assertIn("SET estado='incierta'", codigo)
        self.assertIn("WHERE estado='reservada'", codigo)

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
