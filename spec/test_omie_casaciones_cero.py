# -*- coding: utf-8 -*-
"""Casaciones: ceros, descripciones opcionales y respuestas sin periodos."""
from __future__ import absolute_import

import importlib
import os
import sys
import types
import unittest

APP = os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                   'giscedata_omie_api'))
if APP not in sys.path:
    sys.path.insert(0, APP)
from utils import (parse_pbc_reponse, parse_pbf_reponse,
                   parse_phf_reponse, parse_phfc_reponse)


def fila(period='1', measure='0.0', field='Potencia', desc='H1Q1', clase=None):
    valores = [
        {'Num': {'n': 'Periodo', 'v': period}},
        {'Num': {'n': field, 'v': measure}},
    ]
    if desc is not False:
        valores.append({'Txt': {'n': 'Descripción', 'v': desc}})
    if clase is not None:
        valores.append({'Txt': {'n': 'TipoOferta', 'v': clase}})
    return {'_value_1': valores}


class CasacionesParserTests(unittest.TestCase):
    def test_cero_potencia_con_descripcion_vacia_o_ausente(self):
        for fn in (parse_pbc_reponse, parse_pbf_reponse,
                   parse_phf_reponse, parse_phfc_reponse):
            field = 'PotenciaTotal' if fn is parse_pbf_reponse else 'Potencia'
            for desc in ('', None, False):
                payload = {'Fila': [fila(field=field, desc=desc, clase='C')]}
                resultado = fn(payload, 'P')
                if fn is parse_phf_reponse:
                    resultado, _ = resultado
                self.assertEqual(len(resultado), 1, (fn.__name__, desc))
                self.assertEqual(resultado[0]['ctn'], 0.0)
                self.assertEqual(resultado[0]['desc'], '')

    def test_cero_energia_conservado_y_campo_ausente_no_inventado(self):
        for fn in (parse_pbc_reponse, parse_pbf_reponse,
                   parse_phf_reponse, parse_phfc_reponse):
            field = 'EnergiaTotal' if fn is parse_pbf_reponse else 'Energia'
            payload = {'Fila': [fila(measure=0.0, field=field, clase='V')]}
            resultado = fn(payload, 'E')
            if fn is parse_phf_reponse:
                resultado, _ = resultado
            self.assertEqual(resultado[0]['ctn'], 0.0)

            payload = {'Fila': [fila(measure=None, field=field, clase='V')]}
            resultado = fn(payload, 'E')
            if fn is parse_phf_reponse:
                resultado, _ = resultado
            self.assertEqual(resultado, [])

    def test_fila_sin_medida_o_periodo_no_se_incluye(self):
        for fn in (parse_pbc_reponse, parse_pbf_reponse,
                   parse_phf_reponse, parse_phfc_reponse):
            field = 'PotenciaTotal' if fn is parse_pbf_reponse else 'Potencia'
            for period, measure in ((None, '1.0'), ('1', None)):
                resultado = fn({'Fila': [fila(period=period, measure=measure,
                                               field=field, clase='C')]}, 'P')
                if fn is parse_phf_reponse:
                    resultado, _ = resultado
                self.assertEqual(resultado, [])

    def test_phfc_sigue_requiriendo_tipo_oferta(self):
        self.assertEqual(parse_phfc_reponse(
            {'Fila': [fila(desc='', clase=None)]}, 'P'), [])

    def test_magnitud_no_solicitada_no_cuenta_como_valor_valido(self):
        self.assertEqual(parse_pbc_reponse(
            {'Fila': [fila(field='Energia', measure=1.0)]}, 'P'), [])


class SinFilasNoPersistenciaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ejecutar modelos OpenERP sin servidor ni acceso a OMIE.
        names = ['giscedata_omie_api',
                 'giscedata_omie_api.giscedata_omie_oferta',
                 'giscedata_omie_api.giscedata_omie_casacion',
                 'osv', 'omie', 'zeep', 'zeep.helpers',
                 'tools', 'tools.translate', 'tools.service_utils']
        cls.originales = dict((name, sys.modules.get(name)) for name in names)
        pkg = types.ModuleType('giscedata_omie_api')
        pkg.__path__ = [APP]
        sys.modules[pkg.__name__] = pkg
        oferta = types.ModuleType('giscedata_omie_api.giscedata_omie_oferta')
        oferta.PERIODO_DIA = []
        oferta.TIPO_MERCADO = []
        oferta.CLASE_OFERTA = []
        oferta.TIPO_NUM_SESION = []
        oferta.UNIDAD_MEDIDA = []
        sys.modules[oferta.__name__] = oferta
        osv = types.ModuleType('osv')
        class FakeFields(object):
            def __getattr__(self, attr):
                return lambda *args, **kwargs: None
        class FakeOsv(object):
            pass
        osv.osv = type('OsV', (), {'osv': FakeOsv, 'except_osv': Exception})
        osv.fields = FakeFields()
        sys.modules['osv'] = osv
        omie = types.ModuleType('omie')
        class Client(object):
            def ServicioEjecucionConsultaEncolumnada(self, **kwargs):
                return None
        omie.ClientOMIE = Client
        sys.modules['omie'] = omie
        zeep = types.ModuleType('zeep')
        zeep.helpers = types.ModuleType('zeep.helpers')
        zeep.helpers.serialize_object = lambda obj: obj
        sys.modules['zeep'] = zeep
        sys.modules['zeep.helpers'] = zeep.helpers
        tools = types.ModuleType('tools')
        tools.__path__ = []
        trans = types.ModuleType('tools.translate')
        trans._ = lambda text: text
        service_utils = types.ModuleType('tools.service_utils')
        class Tracker(object):
            def __init__(self, **kwargs):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def log(self, *args, **kwargs):
                pass
        service_utils.WebServiceTracker = Tracker
        tools.translate = trans
        tools.service_utils = service_utils
        sys.modules['tools'] = tools
        sys.modules['tools.translate'] = trans
        sys.modules['tools.service_utils'] = service_utils
        cls.model = importlib.import_module(
            'giscedata_omie_api.giscedata_omie_casacion')

    @classmethod
    def tearDownClass(cls):
        for name, mod in cls.originales.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod

    def _model(self, cls, response):
        model = cls()
        calls = []
        class Control(object):
            def ejecutar_consulta(self, cr, uid, cod, send, context=None):
                return response
        class Pool(object):
            def get(self, name):
                if name == 'giscedata.omie.siom.query.execution':
                    return Control()
                if name == 'giscedata.omie.oferta':
                    return type('Offer', (), {})()
                if name == 'giscedata.omie.casacion.hora':
                    return type('Hora', (), {})()
                raise AssertionError(name)
        model.pool = Pool()
        model.search = lambda *args, **kwargs: calls.append('search')
        model.create = lambda *args, **kwargs: calls.append('create')
        model.unlink = lambda *args, **kwargs: calls.append('unlink')
        return model, calls

    def test_pbf_y_phf_vacios_no_crean_ni_eliminan(self):
        for sesion in (False, '1'):
            model, calls = self._model(self.model.GiscedataOmieCasacion,
                                       {'Fila': [], 'Respuesta': []})
            params = dict(id_unidad='UNIDAD', fecha_sesion='2026-11-12',
                          num_sesion=sesion, uni_medida='P',
                          tipo_mercado='MD' if sesion is False else 'MI',
                          clase_oferta='C')
            with self.assertRaises(Exception):
                model.get_casation_by_session(None, 1, params)
            self.assertEqual(calls, [])

    def test_phfc_vacio_no_borra_casaciones_anteriores(self):
        model, calls = self._model(self.model.GiscedataOmieCasacionContinua,
                                   {'Fila': [], 'Respuesta': []})
        params = dict(id_unidad='UNIDAD', fecha_ronda='2026-11-12',
                      num_ronda=1, uni_medida='P')
        with self.assertRaises(Exception):
            model.get_phfc_casation(None, 1, params)
        self.assertEqual(calls, [])

    def test_pbc_vacio_no_borra_programas_anteriores(self):
        model, calls = self._model(self.model.GiscedataOmieProgramaBaseCasacion,
                                   {'Fila': [], 'Respuesta': []})
        params = dict(id_unidad='UNIDAD', fecha_ronda='2026-11-12', uni_medida='P')
        with self.assertRaises(Exception):
            model.get_pbc_casation(None, 1, params)
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
