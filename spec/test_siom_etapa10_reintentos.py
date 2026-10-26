# -*- coding: utf-8 -*-
"""Etapa 10A: rechazo explicito, reinicio contador, 8101 y reintentos."""
from __future__ import absolute_import

import unittest
from datetime import timedelta
import test_siom_control_ejecucion as _legacy

import sys
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


class ReintentosTests(unittest.TestCase):
    # Reutiliza el FakePostgreSQL sin duplicar los tests de la etapa anterior.
    @classmethod
    def setUpClass(cls):
        _legacy.ControlTests.setUpClass()
        cls.module = _legacy.ControlTests.module

    @classmethod
    def tearDownClass(cls):
        _legacy.ControlTests.tearDownClass()

    def setUp(self):
        self.db = _legacy.FakeStore()
        self.business = _legacy.FakeBusinessCursor()
        self.model = self.module.GiscedataOmieSiomQueryExecution()
        self.model._nueva_conexion = lambda cr: self.db.cursor()
        self.soap_calls = 0

    def ejecutar(self, codigo=5222, **kwargs):
        def llamada():
            self.soap_calls += 1
            return {'Respuesta': []}
        return self.model.ejecutar_consulta(self.business, 7, codigo,
                                           llamada, **kwargs)

    def test_reconoce_rechazo_en_respuesta(self):
        respuesta = {'Respuesta': [
            {'CodigoRespuesta': {'v': 'M-PRUEBA'},
             'TextoRespuesta': [u'No se ha respetado el tiempo mínimo entre consultas']}]}
        self.assertTrue(self.module._rechazo_en_respuesta(respuesta))

    def test_no_clasifica_error_generico(self):
        respuesta = {'Respuesta': [
            {'CodigoRespuesta': {'v': 'M-NO-DISPONIBLE'},
             'TextoRespuesta': ['La casacion no esta disponible']}]}
        self.assertIsNone(self.module._rechazo_en_respuesta(respuesta))

    def test_no_clasifica_respuesta_correcta(self):
        respuesta = {'Respuesta': [
            {'CodigoRespuesta': {'v': '0'},
             'TextoRespuesta': ['El tiempo minimo se ha cumplido']}]}
        self.assertIsNone(self.module._rechazo_en_respuesta(respuesta))

    def test_codigo_explicito_de_homologacion(self):
        respuesta = {'Respuesta': [{'CodigoRespuesta': {'v': 'OMIE-TEST-LIMIT'}}]}
        self.assertTrue(self.module._rechazo_en_respuesta(
            respuesta, ['OMIE-TEST-LIMIT']))

    def test_excepcion_timeout_no_reintentable(self):
        class Timeout(Exception):
            pass
        self.assertIsNone(self.module._rechazo_en_excepcion(Timeout('timeout')))

    def test_http_429_es_rechazo_explicito(self):
        class Response(object):
            status_code = 429
        class HttpError(Exception):
            response = Response()
        self.assertEqual(self.module._rechazo_en_excepcion(HttpError()), 'HTTP 429')

    def test_rechazo_sin_limite_conocido_no_reintenta(self):
        veces = [0]
        def consulta():
            veces[0] += 1
            return {'Respuesta': [{'CodigoRespuesta': {'v': 'X'},
                                    'TextoRespuesta': ['Too many requests']}]}
        with self.assertRaises(self.module.RechazoFrecuenciaOMIE):
            self.model.ejecutar_consulta(
                self.business, 7, 5222, consulta,
                refrescar_8101=lambda cr: False)
        self.assertEqual(veces[0], 1)
        self.assertEqual(self.db.attempts[-1]['estado'], 'rechazada_frecuencia')

    def test_rechazo_refresca_y_reintenta_tras_contador_reiniciado(self):
        self.db.limits[5222] = (1000, 2000)
        veces = [0]
        refrescos = [0]
        def consulta():
            veces[0] += 1
            if veces[0] == 1:
                return {'Respuesta': [{'CodigoRespuesta': {'v': 'X'},
                                       'TextoRespuesta': ['Tiempo minimo excedido']}]}
            return {'Respuesta': []}
        def refrescar(cr):
            refrescos[0] += 1
            self.db.limits[5222] = (3000, 4000)
            return True
        def dormir(segundos):
            self.db.time += timedelta(seconds=segundos)
        res = self.model.ejecutar_consulta(
            self.business, 7, 5222, consulta,
            refrescar_8101=refrescar, dormir=dormir,
            margen_ms=500, espera_maxima_segundos=8)
        self.assertEqual(res, {'Respuesta': []})
        self.assertEqual(veces[0], 2)
        self.assertEqual(refrescos[0], 1)
        self.assertEqual([r['estado'] for r in self.db.attempts],
                         ['rechazada_frecuencia', 'respondida'])
        self.assertGreaterEqual((self.db.attempts[1]['fecha_intento'] -
                                self.db.attempts[0]['fecha_intento']).total_seconds(), 4.5)

    def test_rechazo_espera_superior_presupuesto_no_reintenta(self):
        self.db.limits[5222] = (60000, 30000)
        veces = [0]
        def consulta():
            veces[0] += 1
            return {'Respuesta': [{'CodigoRespuesta': {'v': 'LIMIT'},
                                    'TextoRespuesta': ['Rate limit exceeded']}]}
        with self.assertRaises(self.module.RechazoFrecuenciaOMIE):
            self.model.ejecutar_consulta(
                self.business, 7, 5222, consulta,
                refrescar_8101=lambda cr: True,
                espera_maxima_segundos=10)
        self.assertEqual(veces[0], 1)

    def test_rechazo_8101_no_refresca_recursivamente(self):
        def consulta():
            return {'Respuesta': [{'CodigoRespuesta': {'v': 'LIMIT'},
                                    'TextoRespuesta': ['Rate limit exceeded']}]}
        with self.assertRaises(self.module.RechazoFrecuenciaOMIE):
            self.model.ejecutar_consulta(self.business, 1, 8101, consulta,
                                        refrescar_8101=lambda cr: self.fail('recursion'))

    def test_timeout_sigue_incierta_y_no_reintenta(self):
        calls = [0]
        def llamada():
            calls[0] += 1
            raise IOError('connection reset')
        with self.assertRaises(IOError):
            self.model.ejecutar_consulta(self.business, 7, 5222, llamada)
        self.assertEqual(calls, [1])
        self.assertEqual(self.db.attempts[0]['estado'], 'incierta')

    def test_margen_500ms_impide_adelantarse(self):
        self.db.limits[5222] = (1000, 500)
        self.ejecutar(margen_ms=500)
        self.db.time += timedelta(milliseconds=1000)
        with self.assertRaises(self.module.TiempoMinimoNoCumplido):
            self.ejecutar(margen_ms=500)
        self.db.time += timedelta(milliseconds=501)
        self.ejecutar(margen_ms=500)


    # 10D.3: fallos al interpretar la respuesta SIN perder auditoria.

    def test_10d3_parseo_respuesta_fallido_deja_incierta(self):
        analizar = self.module._rechazo_en_respuesta
        llamadas = [0]
        def llamada():
            llamadas[0] += 1
            return {'Respuesta': []}
        def fallar(*args, **kwargs):
            raise ValueError('respuesta inesperada')
        self.module._rechazo_en_respuesta = fallar
        try:
            with self.assertRaises(ValueError):
                self.model.ejecutar_consulta(
                    self.business, 7, 5222, llamada, reintentos=2)
        finally:
            self.module._rechazo_en_respuesta = analizar
        self.assertEqual(llamadas, [1])
        self.assertEqual(len(self.db.attempts), 1)
        self.assertEqual(self.db.attempts[0]['estado'], 'incierta')
        self.assertIn('ValueError', self.db.attempts[0]['detalle'])
        self.assertIsNotNone(self.db.attempts[0]['fecha_fin'])
        self.assertFalse(self.business.called)

    def test_10d3_parseo_no_oculta_excepcion_si_falla_auditoria(self):
        analizar = self.module._rechazo_en_respuesta
        finalizar = self.model._finalizar
        def fallar(*args, **kwargs):
            raise UnicodeError('respuesta no decodificable')
        def fallo_registro(*args, **kwargs):
            raise IOError('Base de datos no disponible')
        self.module._rechazo_en_respuesta = fallar
        self.model._finalizar = fallo_registro
        try:
            with self.assertRaises(UnicodeError) as err:
                self.model.ejecutar_consulta(
                    self.business, 7, 5222, lambda: {'Respuesta': []},
                    reintentos=2)
            self.assertIn('respuesta no decodificable', str(err.exception))
        finally:
            self.module._rechazo_en_respuesta = analizar
            self.model._finalizar = finalizar
        # La caida de PostgreSQL impide confirmar el estado; no se
        # llama a SOAP otra vez ni se finge un resultado 'respondida'.
        self.assertEqual(len(self.db.attempts), 1)
        self.assertEqual(self.db.attempts[0]['estado'], 'reservada')

    def test_10d3_interprete_excepcion_soap_falla_preserva_error(self):
        analizar = self.module._rechazo_en_excepcion
        llamadas = [0]
        def soap():
            llamadas[0] += 1
            raise IOError('SOAP interrumpido')
        def fallo_analisis(*args):
            raise ValueError('Fault ilegible')
        self.module._rechazo_en_excepcion = fallo_analisis
        try:
            with self.assertRaises(IOError) as err:
                self.model.ejecutar_consulta(
                    self.business, 7, 5222, soap, reintentos=2)
            self.assertIn('SOAP interrumpido', str(err.exception))
        finally:
            self.module._rechazo_en_excepcion = analizar
        self.assertEqual(llamadas, [1])
        self.assertEqual(self.db.attempts[0]['estado'], 'incierta')

    def test_10d3_rechazo_explicito_sin_auditoria_no_reintenta(self):
        interpretar = self.module._rechazo_en_excepcion
        finalizar = self.model._finalizar
        veces = [0]
        def soap():
            veces[0] += 1
            raise IOError('Fault original')
        def fallo_registro(*args, **kwargs):
            raise RuntimeError('No se pudo registrar el rechazo')
        self.module._rechazo_en_excepcion = lambda exc: 'HTTP 429'
        self.model._finalizar = fallo_registro
        try:
            with self.assertRaises(IOError) as err:
                self.model.ejecutar_consulta(
                    self.business, 7, 5222, soap, reintentos=2)
            self.assertIn('Fault original', str(err.exception))
        finally:
            self.module._rechazo_en_excepcion = interpretar
            self.model._finalizar = finalizar
        self.assertEqual(veces, [1])
        self.assertEqual(self.db.attempts[0]['estado'], 'reservada')

    def test_10d3_interrupcion_al_interpretar_no_deja_reservada(self):
        analizar = self.module._rechazo_en_respuesta
        def interrumpir(*args, **kwargs):
            raise KeyboardInterrupt()
        self.module._rechazo_en_respuesta = interrumpir
        try:
            with self.assertRaises(KeyboardInterrupt):
                self.model.ejecutar_consulta(
                    self.business, 7, 5222, lambda: {'Respuesta': []})
        finally:
            self.module._rechazo_en_respuesta = analizar
        self.assertEqual(self.db.attempts[0]['estado'], 'incierta')

    def test_10d3_parseo_fallido_sigue_contando_para_cadencia(self):
        self.db.limits[5222] = (5000, 3000)
        analizar = self.module._rechazo_en_respuesta
        self.module._rechazo_en_respuesta = lambda *args, **kwargs: (_ for _ in ()).throw(ValueError('mal'))
        try:
            with self.assertRaises(ValueError):
                self.model.ejecutar_consulta(
                    self.business, 7, 5222, lambda: {'Respuesta': []},
                    margen_ms=0)
        finally:
            self.module._rechazo_en_respuesta = analizar
        with self.assertRaises(self.module.TiempoMinimoNoCumplido):
            self.model.ejecutar_consulta(
                self.business, 7, 5222, lambda: self.fail('SOAP prematuro'),
                margen_ms=0)
        self.assertEqual(len(self.db.attempts), 1)



if __name__ == '__main__':
    unittest.main()
