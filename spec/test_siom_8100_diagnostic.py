# -*- coding: utf-8 -*-
"""Consulta 8100: diagnostico no intrusivo; tests Python 2.7 / 3.x."""
from __future__ import absolute_import
import importlib
import os
import sys
import types
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
APP = os.path.join(ROOT, 'giscedata_omie_api')


class Consulta8100Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.originales = dict((x, sys.modules.get(x)) for x in
                              ('giscedata_omie_api', 'osv', 'tools', 'tools.translate',
                               'zeep', 'zeep.helpers',
                               'giscedata_omie_api.giscedata_omie_siom_query_execution',
                               'giscedata_omie_api.giscedata_omie_siom_exclusion_diagnostic'))
        pkg = types.ModuleType('giscedata_omie_api')
        pkg.__path__ = [APP]
        sys.modules['giscedata_omie_api'] = pkg
        fields = type('Fields', (), {'__getattr__': lambda self, name:
                      lambda *args, **kw: (name, args, kw)})()
        osv = types.ModuleType('osv')
        osv.osv = type('OsV', (), {'osv': type('Base', (), {})})
        osv.fields = fields
        sys.modules['osv'] = osv
        tools = types.ModuleType('tools')
        tools.__path__ = []
        translate = types.ModuleType('tools.translate')
        translate._ = lambda x: x
        tools.translate = translate
        sys.modules['tools'] = tools
        sys.modules['tools.translate'] = translate
        zeep = types.ModuleType('zeep')
        helpers = types.ModuleType('zeep.helpers')
        helpers.serialize_object = lambda x: x
        zeep.helpers = helpers
        sys.modules['zeep'] = zeep
        sys.modules['zeep.helpers'] = helpers
        cls.diagnostic = importlib.import_module(
            'giscedata_omie_api.giscedata_omie_siom_exclusion_diagnostic')
        cls.module = importlib.import_module(
            'giscedata_omie_api.giscedata_omie_siom_query_execution')

    @classmethod
    def tearDownClass(cls):
        for nombre, original in cls.originales.items():
            if original is None:
                sys.modules.pop(nombre, None)
            else:
                sys.modules[nombre] = original

    def _respuesta(self, filas=None, codigo=8100, mensajes=None):
        return {'CodConsulta': {'v': codigo},
                'Fila': [] if filas is None else filas,
                'Respuesta': [] if mensajes is None else mensajes}

    def test_vacia_es_diagnostico_no_ausencia_de_reglas(self):
        result = self.diagnostic.diagnosticar_respuesta_8100(self._respuesta())
        self.assertEqual(result['total_filas'], 0)
        self.assertTrue(result['solo_diagnostico'])
        self.assertNotIn('bloquear', result)

    def test_descubre_columnas_sin_inventar_esquema(self):
        fila = {'_value_1': [{'Num': {'n': 'Codigo', 'v': 5222}},
                             {'Txt': {'n': 'Ventana', 'v': 'prueba'}}]}
        result = self.diagnostic.diagnosticar_respuesta_8100(
            self._respuesta([fila]))
        self.assertEqual(result['columnas_y_tipos']['Codigo'], ['Num'])
        self.assertEqual(result['muestras'][0][1]['valor'], 'prueba')

    def test_errores_omie_no_se_interpretan_como_vacio(self):
        with self.assertRaises(self.diagnostic.Formato8100NoReconocido):
            self.diagnostic.diagnosticar_respuesta_8100(
                self._respuesta([], mensajes=[{'CodigoRespuesta': 'X'}]))

    def test_rechaza_codigo_incorrecto(self):
        with self.assertRaises(self.diagnostic.Formato8100NoReconocido):
            self.diagnostic.diagnosticar_respuesta_8100(
                self._respuesta([], codigo=8101))

    def test_rechaza_fila_ausente(self):
        with self.assertRaises(self.diagnostic.Formato8100NoReconocido):
            self.diagnostic.diagnosticar_respuesta_8100({'CodConsulta': 8100})

    def test_rechaza_fila_no_lista(self):
        with self.assertRaises(self.diagnostic.Formato8100NoReconocido):
            self.diagnostic.diagnosticar_respuesta_8100(
                self._respuesta(filas={'Num': 1}))

    def test_muestras_limitadas_pero_todas_las_columnas(self):
        filas = [{'_value_1': [{'Txt': {'n': 'A%d' % i, 'v': 'x'}}]}
                 for i in range(5)]
        result = self.diagnostic.diagnosticar_respuesta_8100(
            self._respuesta(filas))
        self.assertEqual(len(result['muestras']), 3)
        self.assertIn('A4', result['columnas_y_tipos'])

    def test_pasa_por_controlador_una_vez_sin_reintentos(self):
        class FakeClient(object):
            def __init__(self, respuesta):
                self.respuesta = respuesta
                self.recibidos = []
            def ServicioEjecucionConsultaEncolumnada(self, **kwargs):
                self.recibidos.append(kwargs)
                return self.respuesta
        client = FakeClient(self._respuesta())
        model = self.module.GiscedataOmieSiomQueryExecution()
        invocaciones = []
        def controlar(cr, uid, codigo, llamada, **kw):
            invocaciones.append((codigo, kw.get('reintentos')))
            return llamada()
        model.ejecutar_consulta = controlar
        result = model.diagnosticar_8100(object(), 1, client=client)
        self.assertEqual(result['total_filas'], 0)
        self.assertEqual(invocaciones, [(8100, 0)])
        self.assertEqual(client.recibidos, [{'MensajeEjecucionConsulta': {
            'CodConsulta': '8100', 'Parametros': {'_value_1': []}}}])

    def test_rechaza_rpc_no_administrativo_antes_del_soap(self):
        model = self.module.GiscedataOmieSiomQueryExecution()
        with self.assertRaises(ValueError):
            model.diagnosticar_8100(object(), 7)


if __name__ == '__main__':
    unittest.main()
