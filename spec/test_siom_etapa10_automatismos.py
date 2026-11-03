# -*- coding: utf-8 -*-
"""10D.4: batch offline sin OMIE/OpenERP, compatible Py2.7 y Py3."""
from __future__ import absolute_import

import os
import sys
import unittest

APP = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'giscedata_omie_api'))
if APP not in sys.path:
    sys.path.insert(0, APP)
from siom_automatismos import ejecutar_lote, EstadoOfertaNoConfirmado


class FakeCursor(object):
    def __init__(self):
        self.sql = []
        self.fail_sql = None
    def execute(self, sql):
        self.sql.append(sql)
        if self.fail_sql and sql.startswith(self.fail_sql):
            raise IOError('Cursor en error')


class AutomatismosTests(unittest.TestCase):
    def setUp(self):
        self.cr = FakeCursor()
        self.enviados = []
        self.estados = {}
        self.fail_en_oferta = None
        self.errores = {}

    def enviar(self, oferta_id):
        self.enviados.append(oferta_id)
        if oferta_id in self.errores:
            raise self.errores[oferta_id]

    def estado(self, oferta_id):
        return self.estados.get(oferta_id, 'enviada')

    def lote(self, ids):
        return ejecutar_lote(self.cr, ids, self.enviar, self.estado)

    def test_envio_de_varias_ofertas(self):
        r = self.lote([1, 2, 3])
        self.assertEqual(self.enviados, [1, 2, 3])
        self.assertEqual(r['resultado'], 'completado')
        self.assertEqual(r['totales']['enviada'], 3)
        self.assertIn('Ejecucion:', r['texto_correo'])
        self.assertEqual(len(self.cr.sql), 6)
        self.assertFalse(any(x.startswith('COMMIT') for x in self.cr.sql))

    def test_envio_con_rechazo_omie_sigue_siguiente(self):
        self.estados[1] = 'enviada_error'
        r = self.lote([1, 2])
        self.assertEqual(r['resultado'], 'completado_con_rechazos')
        self.assertEqual(r['totales']['enviada_error'], 1)
        self.assertEqual(self.enviados, [1, 2])
        self.assertEqual([v['estado'] for v in r['ofertas']],
                         ['enviada_error', 'enviada'])

    def test_fallo_soap_marca_incierta_y_no_envia_siguientes(self):
        self.errores[2] = IOError('SOAP timeout')
        r = self.lote([1, 2, 3, 4])
        self.assertEqual(self.enviados, [1, 2])
        self.assertEqual([v['estado'] for v in r['ofertas']],
                         ['enviada', 'no_confirmada', 'pendiente', 'pendiente'])
        self.assertEqual(r['resultado'], 'con_incidencias')
        self.assertEqual(r['totales']['pendiente'], 2)
        self.assertIn('No reenviar automaticamente', r['texto_correo'])
        self.assertEqual(self.cr.sql[-2:],
                         ['ROLLBACK TO SAVEPOINT siom_auto_1',
                          'RELEASE SAVEPOINT siom_auto_1'])

    def test_bloqueo_en_primera_termina_informe(self):
        class EnvioOMIEPendiente(Exception):
            pass
        self.errores[1] = EnvioOMIEPendiente('Anterior en enviando')
        r = self.lote([1, 2, 3])
        self.assertEqual(self.enviados, [1])
        self.assertEqual(r['totales']['pendiente'], 2)
        self.assertIn('EnvioOMIEPendiente', r['ofertas'][0]['detalle'])
        self.assertIn('OMIE SIOM', r['asunto_correo'])

    def test_error_validacion_no_aborta_todo_el_erp(self):
        self.errores[2] = ValueError('Campo ausente')
        r = self.lote([1, 2, 3])
        self.assertEqual(self.enviados, [1, 2])
        self.assertEqual(r['ofertas'][2]['estado'], 'pendiente')

    def test_estado_desconocido_detiene_el_lote(self):
        self.estados[1] = ''
        r = self.lote([1, 2])
        self.assertEqual([v['estado'] for v in r['ofertas']],
                         ['no_confirmada', 'pendiente'])
        self.assertEqual(self.enviados, [1])
        self.assertIn('EstadoOfertaNoConfirmado', r['ofertas'][0]['detalle'])

    def test_bloqueo_verificado_distingue_no_enviada_de_incierta(self):
        class EnvioOMIEPendiente(Exception):
            pass
        self.errores[1] = EnvioOMIEPendiente('Envio anterior pendiente')
        r = ejecutar_lote(
            self.cr, [1, 2], self.enviar, self.estado,
            es_bloqueo=lambda exc: isinstance(exc, EnvioOMIEPendiente))
        self.assertEqual([v['estado'] for v in r['ofertas']],
                         ['bloqueada', 'pendiente'])
        self.assertEqual(r['totales']['no_confirmada'], 0)
        self.assertIn('Bloqueadas antes del SOAP: 1', r['texto_correo'])

    def test_error_lectura_local_se_trata_como_incierto(self):
        def fallar(_):
            raise RuntimeError('DB no confirmada')
        r = ejecutar_lote(self.cr, [1, 2], self.enviar, fallar)
        self.assertEqual(self.enviados, [1])
        self.assertEqual(r['totales']['no_confirmada'], 1)

    def test_no_hay_commit_automatico_y_los_savepoints_estan_balanceados(self):
        self.errores[2] = RuntimeError('fallo')
        self.lote([1, 2, 3])
        self.assertEqual(self.cr.sql, [
            'SAVEPOINT siom_auto_0', 'RELEASE SAVEPOINT siom_auto_0',
            'SAVEPOINT siom_auto_1', 'ROLLBACK TO SAVEPOINT siom_auto_1',
            'RELEASE SAVEPOINT siom_auto_1'])

    def test_error_rollback_savepoint_no_se_oculta(self):
        self.cr.fail_sql = 'ROLLBACK TO SAVEPOINT'
        self.errores[1] = IOError('SOAP timeout')
        with self.assertRaises(IOError):
            self.lote([1, 2])

    def test_duplicados_rechazados_antes_de_comunicar(self):
        with self.assertRaises(ValueError):
            self.lote([1, 1])
        self.assertEqual(self.enviados, [])
        self.assertEqual(self.cr.sql, [])

    def test_identificadores_invalidos_no_invocan_soap(self):
        for ids in ([0], [-3], [True], ['1'], None):
            with self.assertRaises(ValueError):
                self.lote(ids)
        self.assertEqual(self.enviados, [])

    def test_entero_individual_y_lote_vacio(self):
        self.assertEqual(self.lote(1)['totales']['enviada'], 1)
        self.assertEqual(self.lote([])['ofertas'], [])

    def test_excepcion_utf8_no_rompe_informe_python2(self):
        self.errores[1] = ValueError(b'Conexi\xc3\xb3n')
        r = self.lote([1])
        self.assertIn('ValueError', r['ofertas'][0]['detalle'])
        self.assertIn(u'Conexi\xf3n', r['ofertas'][0]['detalle'])
        self.assertEqual(r['resultado'], 'con_incidencias')


if __name__ == '__main__':
    unittest.main()
