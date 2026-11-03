# -*- coding: utf-8 -*-
"""Fase B 8100: pruebas sin ERP ni OMIE, Python 2.7 / 3.x."""
from __future__ import absolute_import

from datetime import datetime
from decimal import Decimal
import hashlib
import importlib
import json
import os
import sys
import types
import unittest
from xml.etree import ElementTree

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
APP = os.path.join(ROOT, 'giscedata_omie_api')


class FakeFields(object):
    def __getattr__(self, name):
        return lambda *a, **k: (name, a, k)


class FakePool(object):
    def __init__(self, model):
        self.model = model
    def get(self, name):
        if name == 'giscedata.omie.siom.query.execution':
            return self.model
        raise AssertionError(name)


def respuesta(filas=None, codigo=8100, mensajes=None):
    return {'CodConsulta': {'v': codigo},
            'Fila': [] if filas is None else filas,
            'Respuesta': [] if mensajes is None else mensajes}


def fila():
    return {'_value_1': [
        {'Num': {'n': 'ConsultaAfectada', 'v': 5222}},
        {'Txt': {'n': 'CampoDesconocido', 'v': 'valor no interpretado'}},
    ]}


class FaseB8100Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        nombres = ('giscedata_omie_api', 'osv', 'tools', 'tools.translate',
                   'zeep', 'zeep.helpers',
                   'giscedata_omie_api.giscedata_omie_siom_exclusion_diagnostic',
                   'giscedata_omie_api.giscedata_omie_siom_exclusion_observation_parser',
                   'giscedata_omie_api.giscedata_omie_siom_exclusion_observation',
                   'giscedata_omie_api.giscedata_omie_siom_query_execution',
                   'giscedata_omie_api.wizard',
                   'giscedata_omie_api.wizard.wizard_siom_exclusion_observation')
        cls.originales = dict((k, sys.modules.get(k)) for k in nombres)
        pkg = types.ModuleType('giscedata_omie_api')
        pkg.__path__ = [APP]
        sys.modules['giscedata_omie_api'] = pkg
        wizard_pkg = types.ModuleType('giscedata_omie_api.wizard')
        wizard_pkg.__path__ = [os.path.join(APP, 'wizard')]
        sys.modules[wizard_pkg.__name__] = wizard_pkg
        osv = types.ModuleType('osv')
        osv.osv = type('FakeOSV', (), {'osv': type('Base', (), {}),
                                     'osv_memory': type('Memory', (), {}),
                                     'except_osv': Exception})
        osv.fields = FakeFields()
        sys.modules['osv'] = osv
        tools = types.ModuleType('tools')
        tools.__path__ = []
        trans = types.ModuleType('tools.translate')
        trans._ = lambda s: s
        tools.translate = trans
        sys.modules['tools'] = tools
        sys.modules[trans.__name__] = trans
        zeep = types.ModuleType('zeep')
        helpers = types.ModuleType('zeep.helpers')
        helpers.serialize_object = lambda x: x
        zeep.helpers = helpers
        sys.modules['zeep'] = zeep
        sys.modules[helpers.__name__] = helpers
        cls.parser = importlib.import_module(
            'giscedata_omie_api.giscedata_omie_siom_exclusion_observation_parser')
        cls.observation = importlib.import_module(
            'giscedata_omie_api.giscedata_omie_siom_exclusion_observation')
        cls.execution = importlib.import_module(
            'giscedata_omie_api.giscedata_omie_siom_query_execution')
        cls.wizard = importlib.import_module(
            'giscedata_omie_api.wizard.wizard_siom_exclusion_observation')

    @classmethod
    def tearDownClass(cls):
        for name, old in cls.originales.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old

    def setUp(self):
        self.record = self.observation.GiscedataOmieSiomExclusionObservation()
        self.created = []
        self.record.create = lambda cr, uid, vals, context=None: self._insert(vals)

    def _insert(self, vals):
        self.created.append(vals.copy())
        return len(self.created)

    def _mock_controller(self, value):
        class Control(object):
            def __init__(self, v):
                self.value = v
                self.calls = []
            def _consultar_datos_8100(self, cr, uid, context=None, client=None):
                self.calls.append(uid)
                return self.value
        control = Control(value)
        self.record.pool = FakePool(control)
        return control

    def test_vacia_registra_observacion_y_no_reglas(self):
        control = self._mock_controller(respuesta())
        x = self.record.registrar_observacion_8100(None, 1)
        self.assertEqual(control.calls, [1])
        self.assertEqual(x['estado'], 'vacia')
        self.assertEqual(x['total_filas'], 0)
        self.assertFalse(x['reglas_activadas'])
        self.assertEqual(self.created[0]['respuesta_json'] and
                         json.loads(self.created[0]['respuesta_json'])['Fila'], [])

    def test_varias_consultas_vacias_no_borran_historial(self):
        self._mock_controller(respuesta([fila()]))
        self.record.registrar_observacion_8100(None, 1)
        self._mock_controller(respuesta())
        self.record.registrar_observacion_8100(None, 1)
        self.assertEqual([x['estado'] for x in self.created], ['con_datos', 'vacia'])
        self.assertEqual(len(self.created), 2)

    def test_datos_guardan_evidencia_y_no_inventan_horarios(self):
        self._mock_controller(respuesta([fila()]))
        resultado = self.record.registrar_observacion_8100(None, 1)
        self.assertEqual(resultado['total_filas'], 1)
        registro = self.created[0]
        self.assertIn('CampoDesconocido', json.loads(registro['columnas_json']))
        self.assertIn('CampoDesconocido', registro['respuesta_json'])
        self.assertNotIn('inicio_utc', registro)
        self.assertNotIn('bloquear', registro)
        hash_actual = hashlib.sha256(registro['respuesta_json'].encode('utf-8')).hexdigest()
        self.assertEqual(hash_actual, registro['huella_sha256'])

    def test_fallo_de_formato_no_crea_observacion(self):
        self._mock_controller(respuesta([fila()], codigo=8101))
        with self.assertRaises(self.parser.Formato8100NoReconocido):
            self.record.registrar_observacion_8100(None, 1)
        self.assertEqual(self.created, [])

    def test_error_omie_no_se_persiste_como_vacia(self):
        self._mock_controller(respuesta([], mensajes=[{'Codigo': 'ERROR'}]))
        with self.assertRaises(self.parser.Formato8100NoReconocido):
            self.record.registrar_observacion_8100(None, 1)
        self.assertEqual(self.created, [])

    def test_rpc_denegado_no_llama_controlador(self):
        control = self._mock_controller(respuesta())
        with self.assertRaises(Exception):
            self.record.registrar_observacion_8100(None, 2)
        self.assertEqual(control.calls, [])

    def test_decimal_y_fecha_pueden_guardarse_sin_inferencias(self):
        r = respuesta([{'_value_1': [
            {'Feh': {'n': 'FechaNoInterpretada', 'v': datetime(2026, 10, 28, 7, 0)}},
            {'Num': {'n': 'Cantidad', 'v': Decimal('1.5')}}]}])
        obs = self.parser.preparar_observacion_8100(r)
        self.assertIn('2026-10-28T07:00:00', obs['respuesta_json'])
        self.assertIn('1.5', obs['respuesta_json'])

    def test_limite_tamano_rechaza_sin_truncar(self):
        with self.assertRaises(self.parser.Formato8100NoReconocido):
            self.parser.preparar_observacion_8100(respuesta([fila()]), max_bytes=30)

    def test_rechaza_flotantes_no_finitos(self):
        with self.assertRaises(self.parser.Formato8100NoReconocido):
            self.parser.preparar_observacion_8100(
                respuesta([{'Num': {'n': 'Desconocido', 'v': float('nan')}}]))

    def test_limite_filas_es_estricto(self):
        with self.assertRaises(self.parser.Formato8100NoReconocido):
            self.parser.preparar_observacion_8100(
                respuesta([{}] * (self.parser.MAX_FILAS + 1)))

    def test_llamada_8100_usa_controlador_sin_reintentos(self):
        obj = self.execution.GiscedataOmieSiomQueryExecution()
        calls = []
        def ejecutar(cr, uid, codigo, llamada, **kwargs):
            calls.append((codigo, kwargs['reintentos']))
            return llamada()
        obj.ejecutar_consulta = ejecutar
        class Client(object):
            def ServicioEjecucionConsultaEncolumnada(self, **kwargs):
                calls.append(kwargs['MensajeEjecucionConsulta']['CodConsulta'])
                return respuesta()
        self.assertEqual(obj._consultar_datos_8100(None, 1, client=Client())['Fila'], [])
        self.assertEqual(calls, [(8100, 0), '8100'])

    def test_diagnostico_se_mantiene_sin_persistencia(self):
        obj = self.execution.GiscedataOmieSiomQueryExecution()
        obj._consultar_datos_8100 = lambda *a, **kw: respuesta([fila()])
        result = obj.diagnosticar_8100(None, 1)
        self.assertEqual(result['total_filas'], 1)
        self.assertTrue(result['solo_diagnostico'])

    def test_acceso_wizard_denegado_antes_de_elevacion(self):
        wizard = self.wizard.WizardSiomExclusionObservation()
        wizard._puede_consultar = lambda *a, **kw: False
        wizard.simple_browse = lambda *a, **kw: self.fail('no se debe leer wizard')
        with self.assertRaises(Exception):
            wizard.consultar_desde_omie(None, 9, [12])

    def test_acceso_wizard_admin_con_resultado_vacio(self):
        wizard = self.wizard.WizardSiomExclusionObservation()
        wizard._puede_consultar = lambda *a, **kw: True
        wizard.simple_browse = lambda *a, **kw: type('W', (), {'state': 'init'})()
        escritos = []
        wizard.write = lambda *a, **kw: escritos.append(a[3])
        class Model(object):
            def registrar_observacion_8100(self, cr, uid, context=None):
                if uid != 1: raise AssertionError('No se elevo')
                return {'observacion_id': 7, 'estado': 'vacia',
                        'total_filas': 0, 'huella_sha256': 'f' * 64}
        class Pool(object):
            def get(self, key):
                if key != 'giscedata.omie.siom.exclusion.observation':
                    raise AssertionError(key)
                return Model()
        wizard.pool = Pool()
        self.assertTrue(wizard.consultar_desde_omie(None, 9, [12]))
        self.assertIn('NO implica ausencia', escritos[0]['info'])

    def test_migracion_y_xml_registrados(self):
        import csv
        from io import open as fopen
        with fopen(os.path.join(APP, '__terp__.py'), encoding='utf-8') as f:
            manifest = f.read()
        self.assertIn('giscedata_omie_siom_exclusion_observation_view.xml', manifest)
        self.assertIn('wizard/wizard_siom_exclusion_observation_view.xml', manifest)
        for item in ('giscedata_omie_siom_exclusion_observation_view.xml',
                     'wizard/wizard_siom_exclusion_observation_view.xml'):
            ElementTree.parse(os.path.join(APP, item))
        migration = os.path.join(APP, 'migrations', '5.0.26.12',
                                 'post-0008_siom_8100_observaciones.py')
        self.assertTrue(os.path.isfile(migration))
        with fopen(os.path.join(APP, 'security', 'ir.model.access.csv'),
                   encoding='utf-8') as f:
            self.assertIn('model_giscedata_omie_siom_exclusion_observation', f.read())


if __name__ == '__main__':
    unittest.main()
