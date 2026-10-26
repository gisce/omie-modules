# -*- coding: utf-8 -*-
"""Pruebas offline del control de cadencia PostgreSQL para Python 2.7 / 3.x."""
from __future__ import absolute_import

from datetime import datetime, timedelta
import importlib
import os
import sys
import types
import unittest
from xml.etree import ElementTree

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
APP = os.path.join(ROOT, 'giscedata_omie_api')


class FakeFields(object):
    def __getattr__(self, name):
        return lambda *args, **kw: (name, args, kw)


class FakeOsV(object):
    pass


class FakeStore(object):
    def __init__(self):
        self.time = datetime(2026, 10, 26, 12, 0, 0)
        self.limits = {}
        self.attempts = []
        self.next_id = 1
        self.close_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.fail_commit = False
        self.cursor_log = []
        self.cr = None

    def cursor(self):
        c = FakePgCursor(self)
        self.cr = c
        self.cursor_log.append(c)
        return c


class FakePgCursor(object):
    def __init__(self, store):
        self.store = store
        self.result = None
        self.rowcount = 0
        self.closed = False
        self.pending_insert = None
        self.pending_update = None
        self.sql = []

    def execute(self, statement, params=()):
        self.sql.append((statement, params))
        text = ' '.join(statement.lower().split())
        self.rowcount = 0
        if 'pg_advisory_xact_lock' in text:
            self.result = None
        elif 'select tiempo_agente_ms, tiempo_certificado_ms' in text:
            row = self.store.limits.get(params[0])
            self.result = (row,) if row is not None else ()
        elif 'clock_timestamp() at time zone' in text and text.startswith('select'):
            self.result = ((self.store.time,),)
        elif 'select fecha_intento' in text:
            candidates = [r for r in self.store.attempts if r['consulta'] == params[0]]
            candidates.sort(key=lambda r: (r['fecha_intento'], r['id']), reverse=True)
            self.result = ((candidates[0]['fecha_intento'],),) if candidates else ()
        elif text.startswith('insert into giscedata_omie_siom_query_execution'):
            codigo, uid, fecha, limite, configurada, detalle = params
            new_id = self.store.next_id
            self.store.next_id += 1
            self.pending_insert = dict(id=new_id, consulta=codigo, usuario_id=uid,
                                       fecha_intento=fecha, limite_ms=limite,
                                       configurada=configurada, detalle=detalle,
                                       estado='reservada', fecha_fin=None)
            self.result = ((new_id,),)
        elif text.startswith('update giscedata_omie_siom_query_execution'):
            estado, detalle, execution_id = params
            existing = [r for r in self.store.attempts if r['id'] == execution_id and r['estado'] == 'reservada']
            self.rowcount = len(existing)
            self.pending_update = (existing, estado, detalle) if existing else None
            self.result = None
        else:
            raise AssertionError('SQL inesperado: %s' % statement)

    def fetchone(self):
        if not self.result:
            return None
        row = self.result[0]
        self.result = self.result[1:]
        return row

    def commit(self):
        if self.store.fail_commit:
            raise RuntimeError('Error de commit simulado')
        if self.pending_insert:
            self.store.attempts.append(self.pending_insert)
            self.pending_insert = None
        if self.pending_update:
            rows, state, detail = self.pending_update
            for row in rows:
                row['estado'] = state
                row['detalle'] = detail
                row['fecha_fin'] = self.store.time
            self.pending_update = None
        self.store.commit_count += 1

    def rollback(self):
        self.pending_insert = None
        self.pending_update = None
        self.store.rollback_count += 1

    def close(self):
        self.closed = True
        self.store.close_count += 1


class FakeBusinessCursor(object):
    dbname = 'mycompany'
    def __init__(self):
        self.called = False
    def commit(self):
        self.called = True
        raise AssertionError('No debe hacerse commit del cursor negocio')


class ControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backup = {}
        for k in ('osv', 'giscedata_omie_api',
                  'giscedata_omie_api.giscedata_omie_siom_query_execution'):
            cls.backup[k] = sys.modules.get(k)
        fake_osv = types.ModuleType('osv')
        fake_osv.osv = type('OSV', (), {'osv': FakeOsV})
        fake_osv.fields = FakeFields()
        sys.modules['osv'] = fake_osv
        pkg = types.ModuleType('giscedata_omie_api')
        pkg.__path__ = [APP]
        sys.modules[pkg.__name__] = pkg
        cls.module = importlib.import_module('giscedata_omie_api.giscedata_omie_siom_query_execution')

    @classmethod
    def tearDownClass(cls):
        for k, original in cls.backup.items():
            if original is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = original

    def setUp(self):
        self.db = FakeStore()
        self.business = FakeBusinessCursor()
        self.model = self.module.GiscedataOmieSiomQueryExecution()
        self.model._nueva_conexion = lambda cr: self.db.cursor()
        self.soap_calls = 0

    def llamada(self):
        self.soap_calls += 1
        return {'CodConsulta': 5222, 'Respuesta': []}

    def ejecutar(self, codigo=5222, **kwargs):
        return self.model.ejecutar_consulta(self.business, 7, codigo, self.llamada, **kwargs)

    def test_ejecuta_y_devuelve_respuesta_original(self):
        self.db.limits[5222] = (10000, 20000)
        self.assertEqual(self.ejecutar()['CodConsulta'], 5222)
        self.assertEqual(self.soap_calls, 1)

    def test_registra_intento_antes_de_ejecutar_soap(self):
        self.db.limits[5222] = (3000, 4000)
        observed = []
        def check():
            observed.append((len(self.db.attempts), self.db.attempts[0]['estado']))
            return 'respuesta'
        value = self.model.ejecutar_consulta(self.business, 7, 5222, check)
        self.assertEqual(value, 'respuesta')
        self.assertEqual(observed, [(1, 'reservada')])

    def test_estados_respuesta_recibida(self):
        self.db.limits[5222] = (10, 30)
        self.ejecutar()
        self.assertEqual(self.db.attempts[0]['estado'], 'respondida')
        self.assertIsNotNone(self.db.attempts[0]['fecha_fin'])

    def test_maximo_de_ambos_tiempos_aplica(self):
        self.db.limits[5222] = (60000, 30000)
        self.ejecutar()
        self.assertEqual(self.db.attempts[0]['limite_ms'], 60000)
        with self.assertRaises(self.module.TiempoMinimoNoCumplido):
            self.ejecutar()
        self.assertEqual(self.soap_calls, 1)

    def test_limite_por_certificado_prevalece(self):
        self.db.limits[5222] = (10000, 80000)
        self.ejecutar()
        self.assertEqual(self.db.attempts[0]['limite_ms'], 80000)

    def test_espera_correcta(self):
        self.db.limits[5222] = (60000, 30000)
        self.ejecutar()
        self.db.time += timedelta(milliseconds=12500)
        try:
            self.ejecutar()
        except self.module.TiempoMinimoNoCumplido as exc:
            self.assertAlmostEqual(exc.espera_segundos, 47.5)
        else:
            self.fail('Debia bloquear por tiempo minimo')

    def test_libera_despues_de_plazo(self):
        self.db.limits[5222] = (60000, 10000)
        self.ejecutar()
        self.db.time += timedelta(seconds=60)
        self.ejecutar()
        self.assertEqual(self.soap_calls, 2)

    def test_plazo_independiente_por_codigo(self):
        self.db.limits[5222] = (60000, 10000)
        self.db.limits[5608] = (60000, 10000)
        self.ejecutar()
        self.ejecutar(5608)
        self.assertEqual(self.soap_calls, 2)

    def test_cero_es_cero_real(self):
        self.db.limits[5222] = (0, 0)
        self.ejecutar()
        self.ejecutar()
        self.assertEqual(self.soap_calls, 2)

    def test_sin_datos_8101_observa_pero_no_inventa(self):
        self.ejecutar()
        self.assertFalse(self.db.attempts[0]['configurada'])
        self.assertEqual(self.db.attempts[0]['limite_ms'], 0)
        self.assertEqual(self.db.attempts[0]['estado'], 'respondida')

    def test_sin_datos_modo_estricto_impide_consulta(self):
        with self.assertRaises(self.module.SinConfiguracionTiempoMinimo):
            self.ejecutar(exigir_configuracion=True)
        self.assertEqual(self.soap_calls, 0)
        self.assertEqual(len(self.db.attempts), 0)

    def test_reserva_perdura_tras_excepcion_soap(self):
        self.db.limits[5222] = (60000, 10000)
        def failure():
            raise IOError('fallo de transporte')
        with self.assertRaises(IOError):
            self.model.ejecutar_consulta(self.business, 7, 5222, failure)
        self.assertEqual(self.db.attempts[0]['estado'], 'incierta')
        with self.assertRaises(self.module.TiempoMinimoNoCumplido):
            self.ejecutar()

    def test_no_reintenta_al_fallar_soap(self):
        calls = [0]
        def fail():
            calls[0] += 1
            raise IOError('fallo')
        with self.assertRaises(IOError):
            self.model.ejecutar_consulta(self.business, 7, 5222, fail)
        self.assertEqual(calls, [1])

    def test_no_commit_en_cursor_principal(self):
        self.ejecutar()
        self.assertFalse(self.business.called)
        self.assertEqual(self.db.commit_count, 2)

    def test_fallo_commit_no_hace_llamada(self):
        self.db.fail_commit = True
        with self.assertRaises(RuntimeError):
            self.ejecutar()
        self.assertEqual(self.soap_calls, 0)
        self.assertEqual(self.db.attempts, [])

    def test_entrada_invalida_no_abre_conexion(self):
        for codigo in (0, -1, 2.5, 'a', None, True):
            with self.assertRaises(ValueError):
                self.ejecutar(codigo)
        self.assertEqual(self.db.cursor_log, [])

    def test_cierra_y_revierte_si_bloqueada(self):
        self.db.limits[5222] = (60000, 30000)
        self.ejecutar()
        with self.assertRaises(self.module.TiempoMinimoNoCumplido):
            self.ejecutar()
        self.assertEqual(self.db.close_count, 3)
        self.assertTrue(self.db.rollback_count >= 1)

    def test_advisory_lock_por_codigo(self):
        self.db.limits[5222] = (60000, 30000)
        self.ejecutar()
        sql = self.db.cursor_log[0].sql[0]
        self.assertIn('pg_advisory_xact_lock', sql[0])
        self.assertEqual(sql[1][1], 5222)

    def test_sin_sleep_ni_redis(self):
        path = os.path.join(APP, 'giscedata_omie_siom_query_execution.py')
        with open(path, 'rb') as fh:
            text = fh.read().decode('utf-8')
        self.assertNotIn('time.sleep(', text)
        self.assertNotIn('import redis', text)

    def test_estructura_erp_registrada(self):
        with open(os.path.join(APP, '__terp__.py')) as stream:
            manifest = stream.read()
        with open(os.path.join(APP, '__init__.py')) as stream:
            init = stream.read()
        self.assertIn('giscedata_omie_siom_query_execution_view.xml', manifest)
        self.assertIn('giscedata_omie_siom_query_execution', init)
        ElementTree.parse(os.path.join(APP, 'giscedata_omie_siom_query_execution_view.xml'))

    def test_integracion_casacion(self):
        path = os.path.join(APP, 'giscedata_omie_casacion.py')
        with open(path, 'rb') as fh:
            text = fh.read().decode('utf-8')
        self.assertEqual(text.count('control.ejecutar_consulta('), 3)
        self.assertIn("casacion_dict['CodConsulta']", text)

    def test_acls_lectura_sin_escritura(self):
        path = os.path.join(APP, 'security', 'ir.model.access.csv')
        with open(path, 'rb') as fh:
            contents = fh.read().decode('utf-8')
        lines = [line for line in contents.splitlines() if 'model_giscedata_omie_siom_query_execution' in line]
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].endswith(',1,0,0,0'))


if __name__ == '__main__':
    unittest.main()
