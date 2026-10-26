# -*- coding: utf-8 -*-
"""10D.2: test funcional de envio MI sobre ORM/Zeep simulados (Py2/Py3)."""
from __future__ import absolute_import

import importlib
import os
import sys
import types
import unittest

from test_siom_control_ejecucion import FakeFields, FakeOsV

APP = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'giscedata_omie_api'))


class Cursor(object):
    def __init__(self, events):
        self.events = events
        self.sql = []
    def execute(self, sql, args=()):
        self.events.append('sql')
        self.sql.append((sql, args))
    def fetchone(self):
        return (7,)  # Maximo NumOferta ya registrado para agente/unidad/sesion


class OfertaFake(object):
    def __init__(self, events):
        self.events = events
        self.writes = []
    def mensaje_oferta_mi_dicc(self, cursor, uid, oferta_id, context=None):
        self.events.append('mensaje')
        return {
            'IdMensaje': 'OF-12', 'VerMensaje': 1,
            'IdRemitente': 'AGENTE',
            'Oferta': {
                'IdUnidad': {'v': 'UNIDAD'}, 'NumOferta': 1,
                'Validez': {'TipoMercado': 'MI',
                            'Sesion': {'fecha': '2026-10-27', 'num': '1'}},
            },
        }
    def search(self, cursor, uid, domain, context=None):
        self.events.append('search')
        return [11]
    def read(self, cursor, uid, ids, columns, context=None):
        self.events.append('read')
        return [{'ver_mensaje': 4}]
    def write(self, cursor, uid, ids, values, context=None):
        self.events.append('write')
        self.writes.append((ids, values))
        return True


class ServiceFake(object):
    def __init__(self):
        self.metadata = []
    def ultimos_identificadores(self, *args):
        return (4, 7)
    def ejecutar_servicio(self, cr, uid, servicio, llamada, **kwargs):
        self.metadata.append((servicio, kwargs))
        return llamada()


class OfertasVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.originals = {}
        for k in ('osv', 'omie', 'zeep', 'giscedata_omie_api',
                  'giscedata_omie_api.giscedata_omie_oferta',
                  'giscedata_omie_api.utils'):
            cls.originals[k] = sys.modules.get(k)
        osv_module = types.ModuleType('osv')
        osv_module.osv = type('OSV', (), {'osv': FakeOsV})
        osv_module.fields = FakeFields()
        sys.modules['osv'] = osv_module
        omie = types.ModuleType('omie')
        class ClientOMIE(object):
            def ServicioAltaOfertasMI(self, MensajeOfertasMI):
                cls.soap_message = MensajeOfertasMI
                return {'Respuesta': [], 'ResumenOfertas': {'NumOfertasCorrectas': {'v': 1}}}
        omie.ClientOMIE = ClientOMIE
        sys.modules['omie'] = omie
        zeep = types.ModuleType('zeep')
        zeep.helpers = type('Helpers', (), {'serialize_object': staticmethod(lambda obj: obj)})
        sys.modules['zeep'] = zeep
        pkg = types.ModuleType('giscedata_omie_api')
        pkg.__path__ = [APP]
        sys.modules['giscedata_omie_api'] = pkg
        cls.module = importlib.import_module('giscedata_omie_api.giscedata_omie_oferta')

    @classmethod
    def tearDownClass(cls):
        for key, previous in cls.originals.items():
            if previous is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = previous

    def setUp(self):
        self.events = []
        self.cr = Cursor(self.events)
        self.oferta = OfertaFake(self.events)
        self.servicio = ServiceFake()
        self.model = self.module.GiscedataOmieOfertaExtend()
        self.model.pool = type('Pool', (), {'get': lambda _, name:
            self.servicio if name == 'giscedata.omie.siom.service.execution'
            else self.oferta})()
        self.model.read = lambda cr, uid, id, fields: {'tipo_mercado': 'MI'}
        self.model.crear_respuesta_oferta = lambda *args, **kwargs: {
            'num_ofertas_correctas': '1', 'id_mensaje_respuesta': 'RESP-12',
            'codigo_respuesta': '0'}
        self.model.update_origen = lambda *args, **kwargs: True

    def test_version_y_num_oferta_se_calculan_bajo_lock_y_se_guardan(self):
        self.model.enviar_oferta(self.cr, 7, [12])
        self.assertIn('pg_advisory_xact_lock', self.cr.sql[0][0])
        self.assertEqual(self.cr.sql[0][1][1], 2)
        self.assertEqual(self.events[0], 'sql')  # lock antes de leer y buscar
        self.assertEqual(self.events[1], 'mensaje')
        self.assertEqual(self.events[2], 'search')
        self.assertEqual(self.soap_message['VerMensaje'], 5)
        self.assertEqual(self.soap_message['Oferta']['NumOferta'], 8)
        self.assertEqual(self.oferta.writes[0][1]['ver_mensaje'], 5)
        self.assertEqual(self.servicio.metadata[0][0], 'ServicioAltaOfertasMI')
        self.assertEqual(self.servicio.metadata[0][1]['metadatos']['version'], 5)
        self.assertEqual(self.servicio.metadata[0][1]['metadatos']['num_oferta'], 8)
        self.assertTrue(self.servicio.metadata[0][1]['permitir_pendientes_propias'])


if __name__ == '__main__':
    unittest.main()
