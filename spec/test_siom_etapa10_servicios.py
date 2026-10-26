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
        self.offers = {}  # Tuplas visibles despues de commit de ERP

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
        self.pending_response = None

    def execute(self, sql, params=()):
        clean = ' '.join(sql.lower().split())
        self.db.queries.append((sql, params))
        self.rowcount = 0
        self.result = []
        if 'pg_advisory_xact_lock' in clean:
            self.db.lock.acquire()
            self.locked = True
        elif clean.startswith('select max(version_enviada), max(num_oferta_enviado)'):
            matches = [r for r in self.db.rows
                       if r['servicio'] == params[0] and
                       r.get('id_remitente') == params[1] and
                       r.get('fecha_sesion') == params[2] and
                       r.get('id_unidad') == params[3] and
                       r.get('num_sesion') == params[4] and
                       r['estado'] not in ('preparada', 'cancelada')]
            versions = [r['version_enviada'] for r in matches if r.get('version_enviada') is not None]
            nums = [r['num_oferta_enviado'] for r in matches if r.get('num_oferta_enviado') is not None]
            self.result = [(max(versions) if versions else None,
                            max(nums) if nums else None)]
        elif clean.startswith('select id, oferta_id, version_enviada, id_respuesta'):
            self.result = [(r['id'], r['oferta_id'], r.get('version_enviada'),
                            r.get('id_respuesta')) for r in self.db.rows
                           if r['estado'] == 'respondida_pendiente']
        elif clean.startswith('select ver_mensaje, id_mensaje_respuesta, state'):
            self.result = ([self.db.offers[params[0]]]
                           if params[0] in self.db.offers else [])
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
                'estado': params[3], 'detalle': params[4], 'fecha_fin': None,
                'id_mensaje_enviado': params[5] if len(params) > 5 else None,
                'version_enviada': params[6] if len(params) > 6 else None,
                'num_oferta_enviado': params[7] if len(params) > 7 else None,
                'id_remitente': params[8] if len(params) > 8 else None,
                'fecha_sesion': params[9] if len(params) > 9 else None,
                'id_unidad': params[10] if len(params) > 10 else None,
                'num_sesion': params[11] if len(params) > 11 else None,
                'respuesta_json': None, 'id_respuesta': None,
                'codigo_respuesta': None}
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
            elif "set estado='integrada'" in clean:
                row = next((r for r in self.db.rows if r['id'] == params[0] and
                            r['estado'] == 'respondida_pendiente'), None)
                if row:
                    self.pending_updates.append((row, 'integrada', row['detalle']))
                    self.rowcount = 1
            elif "set estado='respondida_pendiente'" in clean:
                row = next((r for r in self.db.rows if r['id'] == params[3] and
                            r['estado'] == 'enviando'), None)
                if row:
                    self.pending_updates.append((row, 'respondida_pendiente',
                                                 'SOAP recibido; integracion ERP pendiente de commit'))
                    self.pending_response = (row, params[0], params[1], params[2])
                    self.rowcount = 1
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

    def fetchall(self):
        result = self.result
        self.result = []
        return result

    def commit(self):
        if self.pending_insert:
            self.db.rows.append(self.pending_insert)
        for row, state, detail in self.pending_updates:
            row['estado'], row['detalle'] = state, detail
            if state not in ('enviando',):
                row['fecha_fin'] = datetime.utcnow()
        if self.pending_response:
            row, payload, response_id, code = self.pending_response
            row.update(respuesta_json=payload, id_respuesta=response_id,
                       codigo_respuesta=code)
        self.pending_response = None
        self.pending_insert = None
        self.pending_updates = []
        self.db.commits += 1
        self._unlock()

    def _unlock(self):
        if self.locked:
            self.db.lock.release()
            self.locked = False

    def rollback(self):
        self.pending_response = None
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

    def test_10d2_respuesta_durable_y_version_no_espera_commit_erp(self):
        self.model._datos_respuesta = lambda respuesta: (
            '{"Respuesta":"OK"}', 'RESP-123', '0')
        result = self.model.ejecutar_servicio(
            self.cr, 7, 'ServicioAltaOfertasMD', lambda: {'correctas': 1},
            oferta_id=100, metadatos={
                'id_mensaje': 'REQ-123', 'version': 7, 'num_oferta': None})
        self.assertEqual(result, {'correctas': 1})
        fila = self.db.rows[0]
        self.assertEqual(fila['estado'], 'respondida_pendiente')
        self.assertEqual(fila['id_mensaje_enviado'], 'REQ-123')
        self.assertEqual(fila['version_enviada'], 7)
        self.assertEqual(fila['id_respuesta'], 'RESP-123')
        self.assertEqual(fila['codigo_respuesta'], '0')
        self.assertEqual(fila['respuesta_json'], '{"Respuesta":"OK"}')
        self.assertFalse(self.cr.called)

    def test_10d2_rollback_de_negocio_no_libera_soap_respondido(self):
        self.model._datos_respuesta = lambda r: ('{}', 'RESP-123', '0')
        self.model.ejecutar_servicio(
            self.cr, 7, 'ServicioAltaOfertasMD', lambda: {'ok': True},
            oferta_id=100, metadatos={'id_mensaje': 'REQ', 'version': 7})
        # No consta integracion COMMIT de la oferta => bloquear siguientes.
        with self.assertRaises(self.module.EnvioOMIEPendiente):
            self.model._reservar(self.cr, 8, 'ServicioAltaOfertasMI', oferta_id=101)
        self.assertEqual(self.db.rows[0]['estado'], 'respondida_pendiente')

    def test_10d2_integracion_confirmada_levanta_pendiente(self):
        self.model._datos_respuesta = lambda r: ('{}', 'RESP-123', '0')
        self.model.ejecutar_servicio(
            self.cr, 7, 'ServicioAltaOfertasMD', lambda: {'ok': True},
            oferta_id=100, metadatos={'id_mensaje': 'REQ', 'version': 7})
        self.db.offers[100] = (7, 'RESP-123', 'enviada')
        nueva = self.model._reservar(self.cr, 8, 'ServicioAltaOfertasMI', oferta_id=101)
        self.assertEqual(nueva, 2)
        self.assertEqual(self.db.rows[0]['estado'], 'integrada')
        self.assertEqual(self.db.rows[1]['estado'], 'preparada')

    def test_10d2_version_o_respuesta_distintas_no_son_commit_valido(self):
        self.model._datos_respuesta = lambda r: ('{}', 'RESP-123', '0')
        self.model.ejecutar_servicio(
            self.cr, 7, 'ServicioAltaOfertasMD', lambda: {'ok': True},
            oferta_id=100, metadatos={'id_mensaje': 'REQ', 'version': 7})
        for oferta_confirmada in ((6, 'RESP-123', 'enviada'),
                                  (7, 'RESP-OLD', 'enviada'),
                                  (7, 'RESP-123', 'no_enviada')):
            self.db.offers[100] = oferta_confirmada
            with self.assertRaises(self.module.EnvioOMIEPendiente):
                self.model._reservar(self.cr, 8, 'ServicioAltaOfertasMI', oferta_id=101)
        self.assertEqual(self.db.rows[0]['estado'], 'respondida_pendiente')

    def test_10d2_segundo_envio_en_misma_transaccion_puede_continuar(self):
        self.model._datos_respuesta = lambda r: ('{}', 'RESP-123', '0')
        self.model.ejecutar_servicio(
            self.cr, 7, 'ServicioAltaOfertasMD', lambda: {'ok': True},
            oferta_id=100, metadatos={'id_mensaje': 'REQ', 'version': 7})

        class CursorLocal(object):
            def __init__(self):
                self.reads = []
            def execute(self, sql, params):
                self.reads.append((sql, params))
            def fetchone(self):
                return (7, 'RESP-123', 'enviada')
        negocio = CursorLocal()
        nueva = self.model._reservar(
            negocio, 7, 'ServicioAltaOfertasMI', oferta_id=101,
            permitir_pendientes_propias=True)
        self.assertEqual(nueva, 2)
        # No equivale a COMMIT: registro sigue pendiente, el siguiente
        # automatismo ajeno debera esperar hasta ver la integracion real.
        self.assertEqual(self.db.rows[0]['estado'], 'respondida_pendiente')
        self.assertEqual(len(negocio.reads), 1)

    def test_10d2_error_guardando_respuesta_no_libera_envio(self):
        def fallo(_):
            raise ValueError('Respuesta corrupta')
        self.model._datos_respuesta = fallo
        with self.assertRaises(ValueError):
            self.model.ejecutar_servicio(
                self.cr, 7, 'ServicioAltaOfertasMD', lambda: {'ok': True},
                oferta_id=100, metadatos={'id_mensaje': 'REQ', 'version': 7})
        self.assertEqual(self.db.rows[0]['estado'], 'incierta')
        with self.assertRaises(self.module.EnvioOMIEPendiente):
            self.model._reservar(self.cr, 7, 'ServicioAltaOfertasMI', oferta_id=101)

    def test_10d2_separacion_bloqueos_y_actualizacion_version_modelo(self):
        with open(os.path.join(APP, 'giscedata_omie_oferta.py')) as f:
            codigo = f.read()
        self.assertIn('giscedata_omie_api.siom.versiones', codigo)
        self.assertIn("'ver_mensaje': oferta_dicc['VerMensaje']", codigo)
        self.assertLess(codigo.index('pg_advisory_xact_lock'),
                        codigo.index('for oferta_id in ids:',
                                     codigo.index('def enviar_oferta')))
        with open(os.path.join(APP, 'giscedata_omie_siom_service_execution.py')) as f:
            servicios = f.read()
        self.assertIn('giscedata_omie_api.siom.ofertas', servicios)
        self.assertIn('respondida_pendiente', servicios)

    def test_10d2_maximos_durables_visibles_sin_commit_del_negocio(self):
        self.model._datos_respuesta = lambda r: ('{}', 'RESP-12', '0')
        self.model.ejecutar_servicio(
            self.cr, 7, 'ServicioAltaOfertasMI', lambda: {'ok': True},
            oferta_id=12, metadatos={
                'id_mensaje': 'REQ', 'version': 5, 'num_oferta': 8,
                'id_remitente': 'AGENTE', 'fecha_sesion': '2026-10-27',
                'id_unidad': 'UNIDAD', 'num_sesion': '1'})
        self.assertEqual(self.model.ultimos_identificadores(
            self.cr, 'MI', 'AGENTE', '2026-10-27', 'UNIDAD', '1'), (5, 8))
        self.assertEqual(self.model.ultimos_identificadores(
            self.cr, 'MI', 'AGENTE', '2026-10-27', 'OTRA', '1'), (None, None))
        # Se incluye respuesta pendiente: el commit del negocio aun no existe.
        self.assertEqual(self.db.rows[0]['estado'], 'respondida_pendiente')
        self.assertFalse(self.cr.called)

    def test_10d2_migracion_add_campos_y_no_reescribe_legacy(self):
        path = os.path.join(APP, 'migrations', '5.0.26.12',
                            'post-0007_siom_respuestas_versiones.py')
        with open(path) as f:
            codigo = f.read()
        self.assertIn("mh.init_model(model_name='giscedata.omie.siom.service.execution')", codigo)
        self.assertNotIn('DELETE FROM', codigo)

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
