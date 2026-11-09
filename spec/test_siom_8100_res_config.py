# -*- coding: utf-8 -*-
"""Datos iniciales 8100 y declaracion de migracion ERP."""
from __future__ import absolute_import

import os
import unittest
from xml.etree import ElementTree

APP = os.path.join(os.path.dirname(__file__), '..', 'giscedata_omie_api')


class ResConfig8100Tests(unittest.TestCase):
    def test_xml_configuracion_y_valores_por_defecto(self):
        path = os.path.join(APP, 'giscedata_omie_data.xml')
        raiz = ElementTree.parse(path).getroot()
        self.assertEqual(raiz.find('data').attrib['noupdate'], '1')
        valores = {}
        for registro in raiz.findall('.//record'):
            self.assertEqual(registro.attrib['model'], 'res.config')
            campos = dict((x.attrib['name'], x.text)
                          for x in registro.findall('field'))
            valores[campos['name']] = campos['value']
        self.assertEqual(valores, {
            'siom_8100_apply': '0',
            'siom_8100_timezone': 'UTC+01:00',
            'siom_8100_max_age_seconds': '3600',
        })

    def test_manifest_y_migracion_cargan_datos(self):
        with open(os.path.join(APP, '__terp__.py'), 'r') as entrada:
            self.assertIn("'giscedata_omie_data.xml'", entrada.read())
        ruta = os.path.join(APP, 'migrations', '5.0.26.12',
                            'post-0013_siom_8100_res_config.py')
        with open(ruta, 'r') as entrada:
            self.assertIn("mh.update_xml(xml_path='giscedata_omie_data.xml')",
                          entrada.read())


if __name__ == '__main__':
    unittest.main()
