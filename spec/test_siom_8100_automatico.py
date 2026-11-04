# -*- coding: utf-8 -*-
"""Refresco 8100 y rechazos explicitos; tests offline Python 2.7/3.x."""
from __future__ import absolute_import

import os
import sys
import types
import unittest
from xml.etree import ElementTree

# Reutiliza el entorno de importaciones desacoplado de OpenERP 5 de fase B.
import test_siom_8100_observation as fixtures
ROOT = fixtures.ROOT


class Refresh8100Tests(unittest.TestCase):
    """Utiliza fixtures existentes sin ejecutar dos veces los tests de 8100."""

    @classmethod
    def setUpClass(cls):
        fixtures.FaseB8100Tests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        metodo = fixtures.FaseB8100Tests.tearDownClass
        getattr(metodo, '__func__', getattr(metodo, 'im_func', None))(cls)

    def setUp(self):
        self.record = self.observation.GiscedataOmieSiomExclusionObservation()

    def _control(self):
        control = self.execution.GiscedataOmieSiomQueryExecution()
        enviados, estados, refrescos = [], [], []
        control._reservar = lambda *args, **kw: 25
        control._finalizar = lambda cr, ident, estado, detalle: estados.append(estado)
        control._finalizar_sin_ocultar = (lambda cr, ident, estado, detalle:
                                         estados.append(estado) or True)
        return control, enviados, estados, refrescos

    def _ejecutar(self, control, respuesta, enviados, refrescos, codigo=3004,
                 context=None, reintentos=3):
        def llamada():
            enviados.append(True)
            return respuesta
        return control.ejecutar_consulta(
            None, 1, codigo, llamada, context=context,
            sincronizacion_inicial=False, reintentos=reintentos,
            refrescar_8100=lambda cr: refrescos.append(True) or True)

    def test_respuesta_exclusion_refresca_una_vez_y_no_reintenta(self):
        c, enviados, estados, refrescos = self._control()
        respuesta = {'Respuesta': [
            {'CodigoRespuesta': {'v': '45'},
             'TextoRespuesta': [{'v': 'Consulta bloqueada por intervalo de exclusión'}]}]}
        with self.assertRaises(self.execution.RechazoExclusionOMIE) as atrapado:
            self._ejecutar(c, respuesta, enviados, refrescos)
        self.assertTrue(atrapado.exception.refrescada)
        self.assertEqual(estados, ['rechazada_exclusion'])
        self.assertEqual(len(enviados), 1)
        self.assertEqual(len(refrescos), 1)

    def test_texto_utf8_bytes_rechazo_exclusion(self):
        c, enviados, estados, refrescos = self._control()
        r = {'Respuesta': [{'CodigoRespuesta': {'v': '45'},
                           'TextoRespuesta': {'v': u'período de exclusión'.encode('utf-8')}}]}
        with self.assertRaises(self.execution.RechazoExclusionOMIE) as atrapado:
            self._ejecutar(c, r, enviados, refrescos)
        self.assertEqual(estados, ['rechazada_exclusion'])
        self.assertEqual(len(enviados), 1)
        self.assertEqual(len(refrescos), 1)
        self.assertIn(u'exclusión', self.execution._texto_unicode(atrapado.exception))

    def test_fault_con_bytes_utf8(self):
        c, enviados, estados, refrescos = self._control()
        Fault = type('Fault', (Exception,), {})
        def llamada():
            enviados.append(True)
            raise Fault(u'intervalo de exclusión'.encode('utf-8'))
        with self.assertRaises(self.execution.RechazoExclusionOMIE):
            c.ejecutar_consulta(None, 1, 3004, llamada,
                               sincronizacion_inicial=False,
                               refrescar_8100=lambda cr: refrescos.append(True) or True)
        self.assertEqual(estados, ['rechazada_exclusion'])
        self.assertEqual(len(enviados), 1)
        self.assertEqual(len(refrescos), 1)

    def test_no_reintentar_tras_refresco_fallido(self):
        c, enviados, estados, refrescos = self._control()
        r = {'Respuesta': [{'CodigoRespuesta': {'v': '55'},
                           'TextoRespuesta': {'v': 'periodo de exclusion'}}]}
        def llamada():
            enviados.append(1)
            return r
        def fallo(cr):
            raise RuntimeError('servidor caido')
        with self.assertRaises(self.execution.RechazoExclusionOMIE) as atrapado:
            c.ejecutar_consulta(None, 1, 3004, llamada,
                               sincronizacion_inicial=False, reintentos=2,
                               refrescar_8100=fallo)
        self.assertFalse(atrapado.exception.refrescada)
        self.assertEqual(len(enviados), 1)

    def test_8100_rechazada_no_se_refresca_recursivamente(self):
        c, enviados, estados, refrescos = self._control()
        r = {'Respuesta': [{'CodigoRespuesta': {'v': '33'},
                           'TextoRespuesta': {'v': 'intervalo de exclusión'}}]}
        with self.assertRaises(self.execution.RechazoExclusionOMIE):
            self._ejecutar(c, r, enviados, refrescos, codigo=8100)
        self.assertEqual(len(refrescos), 0)
        self.assertEqual(len(enviados), 1)

    def test_errores_ambiguos_no_se_interpretan_como_exclusion(self):
        c, enviados, estados, refrescos = self._control()
        r = {'Respuesta': [{'CodigoRespuesta': {'v': '99'},
                           'TextoRespuesta': {'v': 'Error genérico de consulta'}}]}
        self.assertEqual(self._ejecutar(c, r, enviados, refrescos), r)
        self.assertEqual(estados, ['respondida'])
        self.assertEqual(len(refrescos), 0)

    def test_codigo_oficial_configurable_y_codigo_cero_no_dispara(self):
        c, enviados, estados, refrescos = self._control()
        r = {'Respuesta': [{'CodigoRespuesta': {'v': '45'},
                           'TextoRespuesta': {'v': 'Error específico'} }]}
        with self.assertRaises(self.execution.RechazoExclusionOMIE):
            self._ejecutar(c, r, enviados, refrescos,
                           context={'siom_codigos_rechazo_exclusion': ('45',)})
        self.assertEqual(len(refrescos), 1)
        c, enviados, estados, refrescos = self._control()
        r = {'Respuesta': [{'CodigoRespuesta': {'v': '0'},
                           'TextoRespuesta': {'v': 'Intervalo de exclusión consultado'} }]}
        self.assertEqual(self._ejecutar(c, r, enviados, refrescos), r)
        self.assertEqual(len(refrescos), 0)

    def test_fault_explicita_sin_reintento(self):
        c, enviados, estados, refrescos = self._control()
        Fault = type('Fault', (Exception,), {})
        def llamada():
            enviados.append(True)
            raise Fault('OMIE: periodo de exclusión de consulta')
        with self.assertRaises(self.execution.RechazoExclusionOMIE):
            c.ejecutar_consulta(None, 1, 3004, llamada,
                               sincronizacion_inicial=False, reintentos=2,
                               refrescar_8100=lambda cr: refrescos.append(True) or False)
        self.assertEqual(estados, ['rechazada_exclusion'])
        self.assertEqual(len(refrescos), 1)
        self.assertEqual(len(enviados), 1)

    def test_rechazo_8100_sin_retry_si_responde_vacia(self):
        c = self.execution.GiscedataOmieSiomQueryExecution()
        class Model(object):
            def sincronizar_8100(self, cr, uid):
                return {'interpretacion': 'vacia'}
        class Pool(object):
            def get(self, name):
                selfname = 'giscedata.omie.siom.exclusion.observation'
                assert name == selfname
                return Model()
        c.pool = Pool()
        self.assertFalse(c._refrescar_8100(None))

    def test_cron_ejecuta_sincronizacion_sin_activar_bloqueo(self):
        llamadas = []
        def sincronizar(cr, uid, context=None):
            llamadas.append(uid)
            return {'interpretacion': 'valida'}
        self.record.sincronizar_8100 = sincronizar
        self.assertTrue(self.record.cron_actualizar_8100(None, 1))
        self.assertEqual(llamadas, [1])

    def test_cron_inactivo_por_defecto_y_sin_rafagas(self):
        path = os.path.join(ROOT, 'giscedata_omie_api',
                            'giscedata_omie_siom_exclusion_cron.xml')
        xml = ElementTree.parse(path).getroot()
        registro = xml.find('.//record')
        campos = dict((campo.attrib['name'], campo.attrib.get('eval', campo.text))
                      for campo in registro.findall('field'))
        self.assertEqual(campos['active'], 'False')
        self.assertEqual(campos['doall'], 'False')
        self.assertEqual(campos['interval_number'], '30')
        self.assertEqual(campos['model'], 'giscedata.omie.siom.exclusion.observation')

    def test_sincronizacion_en_transaccion_independiente_confirma(self):
        class Cursor(object):
            def __init__(self):
                self.calls = []
            def commit(self):
                self.calls.append('commit')
            def rollback(self):
                self.calls.append('rollback')
            def close(self):
                self.calls.append('close')
        dbcr = Cursor()
        class Control(object):
            def _nueva_conexion(self, cr):
                return dbcr
        class Pool(object):
            def get(self, name):
                assert name == 'giscedata.omie.siom.query.execution'
                return Control()
        self.record.pool = Pool()
        self.record.registrar_observacion_8100 = lambda cr, uid, **kw: {
            'interpretacion': 'valida'}
        self.assertEqual(self.record.sincronizar_8100(None, 1)['interpretacion'],
                         'valida')
        self.assertEqual(dbcr.calls, ['commit', 'close'])
        with self.assertRaises(Exception):
            self.record.sincronizar_8100(None, 9)

    def test_sincronizacion_si_falla_revierte_y_cierra(self):
        class Cursor(object):
            def __init__(self): self.calls = []
            def commit(self): self.calls.append('commit')
            def rollback(self): self.calls.append('rollback')
            def close(self): self.calls.append('close')
        dbcr = Cursor()
        class Control(object):
            def _nueva_conexion(self, cr): return dbcr
        class Pool(object):
            def get(self, name): return Control()
        self.record.pool = Pool()
        def fallo(*args, **kw): raise ValueError('mal formato')
        self.record.registrar_observacion_8100 = fallo
        with self.assertRaises(ValueError):
            self.record.sincronizar_8100(None, 1)
        self.assertEqual(dbcr.calls, ['rollback', 'close'])
