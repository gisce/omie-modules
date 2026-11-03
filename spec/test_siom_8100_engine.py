# -*- coding: utf-8 -*-
"""Fase C 8100: pruebas puras sin OpenERP ni OMIE.

Run: python2.7 -m unittest discover -s spec -p 'test_siom_8100*.py' -v
"""
from __future__ import absolute_import

import datetime
import importlib
import os
import sys
import types
import unittest

APP = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'giscedata_omie_api'))


class TzFija(datetime.tzinfo):
    def __init__(self, horas):
        self.horas = horas

    def utcoffset(self, dt):
        return datetime.timedelta(hours=self.horas)

    def dst(self, dt):
        return datetime.timedelta(0)

    def tzname(self, dt):
        return 'UTC%+d' % self.horas


def tramo(inicio, fin):
    return {'inicio_utc': inicio, 'fin_utc': fin}


class TestMotorExclusiones8100(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prev = sys.modules.get('giscedata_omie_api')
        if cls.prev is None:
            paquete = types.ModuleType('giscedata_omie_api')
            paquete.__path__ = [APP]
            sys.modules['giscedata_omie_api'] = paquete
        cls.m = importlib.import_module(
            'giscedata_omie_api.giscedata_omie_siom_exclusion_engine')

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop('giscedata_omie_api.giscedata_omie_siom_exclusion_engine', None)
        if cls.prev is None:
            sys.modules.pop('giscedata_omie_api', None)

    def eval(self, intervalos, instante, fin_inclusivo=False):
        return self.m.evaluar_ventanas_utc(
            intervalos, instante, fin_inclusivo=fin_inclusivo)

    def test_cero_intervalos_no_confiere_permiso(self):
        resultado = self.eval([], '2026-10-28 10:00:00')
        self.assertFalse(resultado['coincide'])
        self.assertTrue(resultado['solo_evaluacion'])
        self.assertEqual(resultado['intervalos_consolidados'], 0)
        self.assertNotIn('permitido', resultado)
        self.assertNotIn('bloqueado', resultado)

    def test_inicio_incluido(self):
        self.assertTrue(self.eval([tramo('2026-10-28 10:00:00', '2026-10-28 11:00:00')],
                                  '2026-10-28 10:00:00')['coincide'])

    def test_antes_no_incluido(self):
        self.assertFalse(self.eval([tramo('2026-10-28 10:00:00', '2026-10-28 11:00:00')],
                                   '2026-10-28 09:59:59')['coincide'])

    def test_fin_exclusivo(self):
        self.assertFalse(self.eval([tramo('2026-10-28 10:00:00', '2026-10-28 11:00:00')],
                                   '2026-10-28 11:00:00')['coincide'])

    def test_fin_inclusivo_configurable(self):
        self.assertTrue(self.eval([tramo('2026-10-28 10:00:00', '2026-10-28 11:00:00')],
                                  '2026-10-28 11:00:00', fin_inclusivo=True)['coincide'])

    def test_frontera_sin_politica_se_rechaza(self):
        with self.assertRaises(self.m.IntervaloExclusionInvalido):
            self.m.evaluar_ventanas_utc([], '2026-10-28 10:00:00')

    def test_frontera_no_acepta_uno_entero(self):
        with self.assertRaises(self.m.IntervaloExclusionInvalido):
            self.m.evaluar_ventanas_utc([], '2026-10-28 10:00:00', fin_inclusivo=1)

    def test_solapadas_se_consolidan(self):
        a = tramo('2026-10-28 10:00:00', '2026-10-28 12:00:00')
        b = tramo('2026-10-28 11:00:00', '2026-10-28 13:00:00')
        x = self.eval([b, a], '2026-10-28 12:30:00')
        self.assertTrue(x['coincide'])
        self.assertEqual(x['intervalos_consolidados'], 1)
        self.assertEqual(x['fin_utc'], datetime.datetime(2026, 10, 28, 13))

    def test_adyacentes_se_consolidan(self):
        a = tramo('2026-10-28 10:00:00', '2026-10-28 11:00:00')
        b = tramo('2026-10-28 11:00:00', '2026-10-28 12:00:00')
        x = self.eval([b, a], '2026-10-28 11:00:00')
        self.assertTrue(x['coincide'])
        self.assertEqual(x['intervalos_consolidados'], 1)
        self.assertEqual(x['fin_utc'], datetime.datetime(2026, 10, 28, 12))

    def test_consolidacion_transitiva(self):
        intervalos = [
            tramo('2026-10-28 12:00:00', '2026-10-28 13:00:00'),
            tramo('2026-10-28 10:00:00', '2026-10-28 11:00:00'),
            tramo('2026-10-28 11:00:00', '2026-10-28 12:00:00'),
        ]
        self.assertEqual(len(self.m.consolidar_intervalos_utc(intervalos)), 1)

    def test_intervalos_disjuntos_no_se_unen(self):
        a = tramo('2026-10-28 09:00:00', '2026-10-28 10:00:00')
        b = tramo('2026-10-28 11:00:00', '2026-10-28 12:00:00')
        self.assertEqual(self.eval([a, b], '2026-10-28 10:30:00')['intervalos_consolidados'], 2)
        self.assertFalse(self.eval([a, b], '2026-10-28 10:30:00')['coincide'])

    def test_ventana_cruza_medianoche(self):
        a = tramo('2026-10-28 23:55:00', '2026-10-29 00:10:00')
        self.assertTrue(self.eval([a], '2026-10-29 00:00:00')['coincide'])
        self.assertFalse(self.eval([a], '2026-10-29 00:10:00')['coincide'])

    def test_cambio_hora_otono_dos_horas_locales_iguales(self):
        # 02:30 CEST (UTC+2) y 02:30 CET (UTC+1) son instantes DISTINTOS.
        una = datetime.datetime(2026, 10, 25, 2, 30, tzinfo=TzFija(2))
        dos = datetime.datetime(2026, 10, 25, 2, 30, tzinfo=TzFija(1))
        self.assertEqual(self.m.normalizar_instante_utc(una),
                         datetime.datetime(2026, 10, 25, 0, 30))
        self.assertEqual(self.m.normalizar_instante_utc(dos),
                         datetime.datetime(2026, 10, 25, 1, 30))
        a = tramo('2026-10-25 00:00:00', '2026-10-25 01:00:00')
        self.assertTrue(self.eval([a], una)['coincide'])
        self.assertFalse(self.eval([a], dos)['coincide'])

    def test_cambio_hora_primavera_con_offsets(self):
        a = datetime.datetime(2026, 3, 29, 1, 30, tzinfo=TzFija(1))
        b = datetime.datetime(2026, 3, 29, 3, 30, tzinfo=TzFija(2))
        self.assertEqual(self.m.normalizar_instante_utc(a),
                         datetime.datetime(2026, 3, 29, 0, 30))
        self.assertEqual(self.m.normalizar_instante_utc(b),
                         datetime.datetime(2026, 3, 29, 1, 30))

    def test_texto_utc_con_z_y_microsegundos(self):
        a = self.m.normalizar_instante_utc('2026-10-28T10:01:02.1Z')
        self.assertEqual(a, datetime.datetime(2026, 10, 28, 10, 1, 2, 100000))

    def test_datetime_naive_se_considera_utc(self):
        a = datetime.datetime(2026, 10, 28, 10, 0)
        self.assertEqual(self.m.normalizar_instante_utc(a), a)

    def test_texto_con_offset_sin_normalizar_se_rechaza(self):
        with self.assertRaises(self.m.IntervaloExclusionInvalido):
            self.m.normalizar_instante_utc('2026-10-28T10:00:00+02:00')

    def test_cadena_invalida_rechazada(self):
        with self.assertRaises(self.m.IntervaloExclusionInvalido):
            self.m.normalizar_instante_utc('2026-02-30 10:00:00')

    def test_inicio_igual_fin_rechazado(self):
        with self.assertRaises(self.m.IntervaloExclusionInvalido):
            self.m.normalizar_intervalos_utc([tramo('2026-10-28 10:00:00', '2026-10-28 10:00:00')])

    def test_fin_anterior_rechazado(self):
        with self.assertRaises(self.m.IntervaloExclusionInvalido):
            self.m.normalizar_intervalos_utc([tramo('2026-10-28 11:00:00', '2026-10-28 10:00:00')])

    def test_fila_incompleta_rechazada(self):
        with self.assertRaises(self.m.IntervaloExclusionInvalido):
            self.m.normalizar_intervalos_utc([{'inicio_utc': '2026-10-28 10:00:00'}])

    def test_columna_extra_rechazada_sin_ignorarla(self):
        with self.assertRaises(self.m.IntervaloExclusionInvalido):
            self.m.normalizar_intervalos_utc([
                {'inicio_utc': '2026-10-28 10:00:00', 'fin_utc': '2026-10-28 11:00:00',
                 'ambito_omie_desconocido': 'x'}])

    def test_fila_invalida_no_se_omite(self):
        a = tramo('2026-10-28 10:00:00', '2026-10-28 11:00:00')
        with self.assertRaises(self.m.IntervaloExclusionInvalido):
            self.eval([a, {}], '2026-10-28 10:30:00')

    def test_demasiados_intervalos_rechazado(self):
        with self.assertRaises(self.m.IntervaloExclusionInvalido):
            self.m.normalizar_intervalos_utc([{}] * (self.m.MAX_INTERVALOS + 1))

    def test_tuplas_de_entrada_aceptadas(self):
        a = tramo('2026-10-28 10:00:00', '2026-10-28 11:00:00')
        self.assertTrue(self.eval((a,), '2026-10-28 10:00:00')['coincide'])

    def test_ninguna_dependencia_de_reloj_sistema(self):
        with open(self.m.__file__, 'r') as f:
            source = f.read()
        self.assertNotIn('datetime.now', source)
        self.assertNotIn('datetime.utcnow', source)

    def test_errores_invalidos_no_se_transforman_en_permiso(self):
        with self.assertRaises(self.m.IntervaloExclusionInvalido):
            self.eval(['basura'], '2026-10-28 10:00:00')


if __name__ == '__main__':
    unittest.main()
