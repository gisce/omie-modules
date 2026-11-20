# -*- coding: utf-8 -*-
"""Pruebas offline del asistente de conciliacion de envios SIOM."""
from __future__ import absolute_import

import importlib
import os
import sys
import types
import unittest
from xml.etree import ElementTree

from test_siom_8101_wizard import FakeFields, FakeOsV, FakeWizardMixin

APP = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'giscedata_omie_api'))


class Backend(object):
    def __init__(self):
        self.calls = []

    def conciliar_envio(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if args[1] != 1:
            raise AssertionError('El backend requiere uid=1')
        return True


class Permisos(object):
    allowed = True

    def _puede_actualizar(self, cr, uid, context=None):
        return self.allowed


class Pool(object):
    def __init__(self, backend, permisos):
        self.backend = backend
        self.permisos = permisos

    def get(self, model):
        if model == 'wizard.siom.minimum.time.update':
            return self.permisos
        if model == 'giscedata.omie.siom.service.execution':
            return self.backend
        raise AssertionError(model)


class Envio(object):
    id = 55


class ConciliacionWizardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backup = {}
        names = ('osv', 'tools', 'tools.translate',
                 'giscedata_omie_api', 'giscedata_omie_api.wizard',
                 'giscedata_omie_api.wizard.wizard_siom_service_reconcile')
        for name in names:
            cls.backup[name] = sys.modules.get(name)
        osv_stub = types.ModuleType('osv')
        osv_stub.osv = FakeOsV()
        osv_stub.fields = FakeFields()
        sys.modules['osv'] = osv_stub
        tools_stub = types.ModuleType('tools')
        tools_stub.__path__ = []
        translate_stub = types.ModuleType('tools.translate')
        translate_stub._ = lambda message: message
        sys.modules['tools'] = tools_stub
        sys.modules['tools.translate'] = translate_stub
        pkg = types.ModuleType('giscedata_omie_api')
        pkg.__path__ = [APP]
        sys.modules[pkg.__name__] = pkg
        pkg_wizard = types.ModuleType('giscedata_omie_api.wizard')
        pkg_wizard.__path__ = [os.path.join(APP, 'wizard')]
        sys.modules[pkg_wizard.__name__] = pkg_wizard
        module = importlib.import_module(
            'giscedata_omie_api.wizard.wizard_siom_service_reconcile')
        cls.Wizard = type('Wizard', (FakeWizardMixin,
                                     module.WizardSiomServiceReconcile), {})

    @classmethod
    def tearDownClass(cls):
        for name, original in cls.backup.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    def setUp(self):
        self.backend = Backend()
        self.permisos = Permisos()
        self.wizard = self.Wizard()
        self.wizard.pool = Pool(self.backend, self.permisos)
        self.wizard.record.intento_id = Envio()
        self.wizard.record.comprobado_omie = True
        self.wizard.record.proceso_terminado = True
        self.wizard.record.justificacion = (
            'Respuesta TSD-007286 verificada en OMIE: oferta invalida')

    def call(self):
        return self.wizard.conciliar(None, 45, [99], context={})

    def test_usuario_manager_concilia_envio_55_y_se_audita_su_uid(self):
        self.assertTrue(self.call())
        args, kwargs = self.backend.calls[0]
        self.assertEqual(args[1:3], (1, 55))
        self.assertIn('Usuario ERP 45:', args[3])
        self.assertIn('TSD-007286', args[3])
        self.assertEqual(kwargs, {'proceso_terminado': True})
        self.assertEqual(self.wizard.record.state, 'end')
        with self.assertRaises(Exception):
            self.call()
        self.assertEqual(len(self.backend.calls), 1)

    def test_sin_permiso_o_verificacion_no_llega_al_backend(self):
        self.permisos.allowed = False
        with self.assertRaises(Exception):
            self.call()
        self.permisos.allowed = True
        self.wizard.record.comprobado_omie = False
        with self.assertRaises(Exception):
            self.call()
        self.assertEqual(self.backend.calls, [])

    def test_xml_y_manifest_incluyen_el_asistente(self):
        ElementTree.parse(os.path.join(APP, 'wizard',
            'wizard_siom_service_reconcile_view.xml'))
        ElementTree.parse(os.path.join(APP,
            'giscedata_omie_siom_service_execution_view.xml'))
        with open(os.path.join(APP, '__terp__.py')) as manifest_file:
            manifest = manifest_file.read()
        self.assertIn('wizard_siom_service_reconcile_view.xml', manifest)


if __name__ == '__main__':
    unittest.main()
