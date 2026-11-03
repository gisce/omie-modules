# -*- coding: utf-8 -*-
"""Autorizacion y validacion del asistente de conciliacion de consultas."""
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

    def conciliar_reserva(self, *args, **kw):
        self.calls.append((args, kw))
        return True


class Permisos(object):
    allowed = True

    def _puede_actualizar(self, cr, uid, context=None):
        return self.allowed


class Pool(object):
    def __init__(self, backend, permisos):
        self.backend = backend
        self.permisos = permisos

    def get(self, name):
        if name == 'wizard.siom.minimum.time.update':
            return self.permisos
        if name == 'giscedata.omie.siom.query.execution':
            return self.backend
        raise AssertionError(name)


class Registro(object):
    id = 31


class ReconcileWizardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backup = {}
        for key in ('osv', 'giscedata_omie_api', 'giscedata_omie_api.wizard',
                    'giscedata_omie_api.wizard.wizard_siom_query_reconcile'):
            cls.backup[key] = sys.modules.get(key)
        mod = types.ModuleType('osv')
        mod.osv = FakeOsV()
        mod.fields = FakeFields()
        sys.modules['osv'] = mod
        pkg = types.ModuleType('giscedata_omie_api')
        pkg.__path__ = [APP]
        sys.modules[pkg.__name__] = pkg
        pkg_wizard = types.ModuleType('giscedata_omie_api.wizard')
        pkg_wizard.__path__ = [os.path.join(APP, 'wizard')]
        sys.modules[pkg_wizard.__name__] = pkg_wizard
        module = importlib.import_module('giscedata_omie_api.wizard.wizard_siom_query_reconcile')
        cls.Fake = type('Fake', (FakeWizardMixin, module.WizardSiomQueryReconcile), {})

    @classmethod
    def tearDownClass(cls):
        for key, old in cls.backup.items():
            if old is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = old

    def setUp(self):
        self.permisos = Permisos()
        self.backend = Backend()
        self.wizard = self.Fake()
        self.wizard.pool = Pool(self.backend, self.permisos)
        self.wizard.record.intento_id = Registro()
        self.wizard.record.motivo = 'Verificacion externa completada por el administrador'
        self.wizard.record.confirmado = True

    def call(self):
        return self.wizard.conciliar(None, 45, [99], context={})

    def test_solicitante_real_queda_auditado(self):
        self.assertTrue(self.call())
        args, kwargs = self.backend.calls[0]
        self.assertEqual(args[1:4], (1, 31, self.wizard.record.motivo))
        self.assertEqual(kwargs, {'confirmado': True, 'usuario_solicitante': 45})
        self.assertEqual(self.wizard.record.state, 'end')

    def test_deniega_sin_grupo(self):
        self.permisos.allowed = False
        with self.assertRaises(Exception):
            self.call()
        self.assertEqual(self.backend.calls, [])

    def test_deniega_sin_confirmacion(self):
        self.wizard.record.confirmado = False
        with self.assertRaises(Exception):
            self.call()
        self.assertEqual(self.backend.calls, [])

    def test_no_se_repite_tras_cierre(self):
        self.call()
        with self.assertRaises(Exception):
            self.call()
        self.assertEqual(len(self.backend.calls), 1)

    def test_vista_cargable(self):
        ElementTree.parse(os.path.join(APP, 'wizard',
                           'wizard_siom_query_reconcile_view.xml'))


if __name__ == '__main__':
    unittest.main()
