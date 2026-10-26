# -*- coding: utf-8 -*-
"""Tests offline, Python 2.7 y Python 3.11; no requieren OMIE ni OpenERP."""
from __future__ import absolute_import

import csv
import importlib
import os
import sys
import types
import unittest
from xml.etree import ElementTree

from mock import Mock
from types import ModuleType
# Simulamos el módulo tools que proporciona GISCE-ERP.
tools_mock = ModuleType('tools')
tools_mock.config = Mock()
sys.modules['tools'] = tools_mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
APP = os.path.join(ROOT, 'giscedata_omie_api')


def importar_con_stubs():
    originals = dict((key, sys.modules.get(key)) for key in
                     ('osv', 'zeep', 'zeep.helpers', 'giscedata_omie_api',
                      'giscedata_omie_api.giscedata_omie_siom_minimum_time',
                      'giscedata_omie_api.giscedata_omie_siom_minimum_time_parser'))
    class FakeFields(object):
        def __getattr__(self, name):
            def f(*args, **kwargs):
                return (name, args, kwargs)
            return f
    class FakeModel(object):
        pass
    fake_osv = types.ModuleType('osv')
    fake_osv.osv = type('OsV', (), {'osv': FakeModel, 'except_osv': Exception})
    fake_osv.fields = FakeFields()
    sys.modules['osv'] = fake_osv
    pkg = types.ModuleType('giscedata_omie_api')
    pkg.__path__ = [APP]
    sys.modules[pkg.__name__] = pkg
    zeep = types.ModuleType('zeep')
    helpers = types.ModuleType('zeep.helpers')
    helpers.serialize_object = lambda value: value
    zeep.helpers = helpers
    sys.modules['zeep'] = zeep
    sys.modules['zeep.helpers'] = helpers
    parser = importlib.import_module('giscedata_omie_api.giscedata_omie_siom_minimum_time_parser')
    model = importlib.import_module('giscedata_omie_api.giscedata_omie_siom_minimum_time')
    return originals, parser, model


def restore(originals):
    for key, old in originals.items():
        if old is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = old


def fila(codigo=5222, agente=60000, certificado=30000):
    return {'_value_1': [
        {'Num': {'n': 'CdConsult', 'v': codigo}},
        {'Txt': {'n': 'Titulo', 'v': 'Consulta de prueba'}},
        {'Num': {'n': 'TMinAge', 'v': agente}},
        {'Num': {'n': 'TMinCert', 'v': certificado}},
        {'Txt': {'n': 'TipoAcceso', 'v': 'Ambas'}},
    ]}


def respuesta(filas=None, codigo=8101, mensajes=None):
    return {'CodConsulta': {'v': codigo},
            'Fila': filas if filas is not None else [],
            'Respuesta': mensajes if mensajes is not None else []}


class FakeCursor(object):
    def __init__(self):
        self.queries = []
    def execute(self, query, params):
        self.queries.append((query, params))


class FakeORM(object):
    def __init__(self):
        self.rows = {}
        self.next_id = 1
        self.writes = []
        self.creates = []
    def search(self, cr, uid, domain, context=None):
        return [row_id for row_id, row in self.rows.items()
                if all(row.get(field) == val for field, op, val in domain if op == '=')]
    def create(self, cr, uid, values, context=None):
        row_id = self.next_id
        self.next_id += 1
        self.rows[row_id] = values.copy()
        self.creates.append(values.copy())
        return row_id
    def write(self, cr, uid, ids, values, context=None):
        for row_id in ids:
            self.rows[row_id].update(values)
        self.writes.append(values.copy())
        return True


class FakePool(object):
    def __init__(self, sync):
        self.sync = sync
    def get(self, model):
        if model != 'giscedata.omie.siom.minimum.time.sync':
            raise AssertionError(model)
        return self.sync


class FakeClient(object):
    def __init__(self, value):
        self.value = value
        self.sent = []
    def ServicioEjecucionConsultaEncolumnada(self, **kwargs):
        self.sent.append(kwargs)
        return self.value


class MinimumTimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.originals, cls.parser, cls.model = importar_con_stubs()
        # Debe ser instancia del modelo real: Python 2.7 valida el primer
        # argumento de los metodos no vinculados (unbound methods).
        cls.FakeOMIEModel = type(
            'FakeOMIEModel',
            (FakeORM, cls.model.GiscedataOmieSiomMinimumTime),
            {}
        )
    @classmethod
    def tearDownClass(cls):
        restore(cls.originals)

    def setUp(self):
        self.obj = self.FakeOMIEModel()
        self.sync = FakeORM()
        self.obj.pool = FakePool(self.sync)
        self.cursor = FakeCursor()
        self.obj.consultar_tiempos_minimos = lambda cr, uid, context=None, client=None: []

    def actualizar(self, uid=1):
        return self.obj.actualizar_tiempos_minimos(self.cursor, uid)

    def test_formato_encol(self):
        rows = self.parser.parsear_8101(respuesta([fila()]))
        self.assertEqual(rows, [{
            'consulta': 5222, 'titulo': 'Consulta de prueba',
            'tiempo_agente_ms': 60000, 'tiempo_certificado_ms': 30000,
            'tipo_acceso': 'Ambas'}])

    def test_ceros_no_son_ausencias(self):
        result = self.parser.parsear_8101(respuesta([fila(5222, 0, 0)]))
        self.assertEqual(result[0]['tiempo_agente_ms'], 0)
        self.assertEqual(result[0]['tiempo_certificado_ms'], 0)

    def test_admite_valores_numericos_como_texto(self):
        res = self.parser.parsear_8101(respuesta([fila('5222', '1000', '3000')]))
        self.assertEqual(res[0]['tiempo_agente_ms'], 1000)

    def test_retorna_lista_vacia_sin_inventar_filas(self):
        self.assertEqual(self.parser.parsear_8101(respuesta()), [])

    def test_rechaza_cod_consulta_incorrecto(self):
        with self.assertRaises(self.parser.Formato8101Error):
            self.parser.parsear_8101(respuesta([fila()], codigo=8100))

    def test_rechaza_errores_funcionales(self):
        with self.assertRaises(self.parser.Formato8101Error):
            self.parser.parsear_8101(respuesta([], mensajes=[{'codigo': 109}]))

    def test_rechaza_estructura_sin_fila(self):
        with self.assertRaises(self.parser.Formato8101Error):
            self.parser.parsear_8101({'CodConsulta': {'v': 8101}})

    def test_rechaza_valores_negativos(self):
        with self.assertRaises(self.parser.Formato8101Error):
            self.parser.parsear_8101(respuesta([fila(5222, -1, 3000)]))

    def test_rechaza_decimales_truncables(self):
        with self.assertRaises(self.parser.Formato8101Error):
            self.parser.parsear_8101(respuesta([fila(5222, 1.4, 3000)]))

    def test_rechaza_columnas_obligatorias_ausentes(self):
        f = fila()
        f['_value_1'].pop()
        with self.assertRaises(self.parser.Formato8101Error):
            self.parser.parsear_8101(respuesta([f]))

    def test_rechaza_codigos_duplicados(self):
        with self.assertRaises(self.parser.Formato8101Error):
            self.parser.parsear_8101(respuesta([fila(5222), fila(5222)]))

    def test_consulta_no_modifica_base_de_datos(self):
        client = FakeClient(respuesta([fila()]))
        obj = self.model.GiscedataOmieSiomMinimumTime()
        result = obj.consultar_tiempos_minimos(self.cursor, 1, client=client, controlar=False)
        self.assertEqual(result[0]['consulta'], 5222)
        self.assertEqual(client.sent, [{'MensajeEjecucionConsulta': {
            'CodConsulta': '8101', 'Parametros': {'_value_1': []}}}])

    def test_crea_filas_nuevas_y_estado(self):
        rows = self.parser.parsear_8101(respuesta([fila(5222), fila(5223)]))
        self.obj.consultar_tiempos_minimos = lambda *a, **kw: rows
        result = self.actualizar()
        self.assertEqual(result['nuevas'], 2)
        self.assertEqual(len(self.obj.rows), 2)
        self.assertEqual(self.sync.creates[0]['estado'], 'con_datos')
        self.assertEqual(len(self.cursor.queries), 1)
        self.assertEqual(self.cursor.queries[0][1], ('giscedata_omie_api.8101', 'all'))
        self.assertNotIn('scope', self.obj.creates[0])
        self.assertNotIn('scope', self.sync.creates[0])

    def test_actualiza_una_fila_y_no_la_duplica(self):
        self.obj.consultar_tiempos_minimos = lambda *a, **kw: self.parser.parsear_8101(respuesta([fila()]))
        self.actualizar()
        self.obj.consultar_tiempos_minimos = lambda *a, **kw: self.parser.parsear_8101(respuesta([fila(5222, 5000)]))
        result = self.actualizar()
        self.assertEqual(result['actualizadas'], 1)
        self.assertEqual(len(self.obj.rows), 1)
        self.assertEqual(list(self.obj.rows.values())[0]['tiempo_agente_ms'], 5000)

    def test_respuesta_vacia_conserva_limites(self):
        self.obj.consultar_tiempos_minimos = lambda *a, **kw: self.parser.parsear_8101(respuesta([fila()]))
        self.actualizar()
        self.obj.consultar_tiempos_minimos = lambda *a, **kw: []
        result = self.actualizar()
        self.assertEqual(result['estado'], 'vacia')
        self.assertEqual(len(self.obj.rows), 1)
        self.assertEqual(list(self.sync.rows.values())[0]['total_filas'], 0)

    def test_una_configuracion_por_consulta(self):
        self.obj.consultar_tiempos_minimos = lambda *a, **kw: self.parser.parsear_8101(respuesta([fila()]))
        self.actualizar()
        self.actualizar()
        self.assertEqual(len(self.obj.rows), 1)
        self.assertEqual(len(self.sync.rows), 1)

    def test_rechaza_usuario_no_autorizado(self):
        with self.assertRaises(Exception):
            self.actualizar(uid=14)
        self.assertEqual(self.cursor.queries, [])

    def test_no_se_exige_ambito(self):
        self.obj.consultar_tiempos_minimos = lambda *a, **kw: []
        resultado = self.actualizar()
        self.assertNotIn('scope', resultado)
        self.assertFalse(any('scope' in vals for vals in self.sync.creates))
        with self.assertRaises(TypeError):
            self.obj.actualizar_tiempos_minimos(self.cursor, 1, scope='default')

    def test_no_persiste_si_el_parser_falla(self):
        def error(*a, **kw):
            raise self.parser.Formato8101Error('respuesta inconsistente')
        self.obj.consultar_tiempos_minimos = error
        with self.assertRaises(self.parser.Formato8101Error):
            self.actualizar()
        self.assertEqual(self.obj.rows, {})
        self.assertEqual(self.sync.rows, {})

    def test_estructura_views_y_acls(self):
        doc = ElementTree.parse(os.path.join(APP, 'giscedata_omie_siom_minimum_time_view.xml'))
        models = [node.text for node in doc.findall(".//record[@model='ir.ui.view']/field[@name='model']")]
        self.assertIn('giscedata.omie.siom.minimum.time', models)
        self.assertIn('giscedata.omie.siom.minimum.time.sync', models)
        with open(os.path.join(APP, 'giscedata_omie_siom_minimum_time_view.xml')) as handle:
            self.assertNotIn('scope', handle.read())
        access = os.path.join(APP, 'security', 'ir.model.access.csv')
        with open(access, 'r') as f:
            rows = list(csv.DictReader(f))
        for name in ('model_giscedata_omie_siom_minimum_time',
                     'model_giscedata_omie_siom_minimum_time_sync'):
            matches = [r for r in rows if r['model_id:id'] == name]
            self.assertEqual(len(matches), 3)
            self.assertTrue(all(r['perm_read'] == '1' for r in matches))
            self.assertTrue(all(r['perm_write'] == '0' for r in matches))


if __name__ == '__main__':
    unittest.main()
