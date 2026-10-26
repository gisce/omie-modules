# -*- coding: utf-8 -*-
"""Tests offline del asistente 8101. Python 2.7 y Python 3.x."""
from __future__ import absolute_import

import importlib
import os
import sys
import types
import unittest
from xml.etree import ElementTree

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MOD = os.path.join(ROOT, 'giscedata_omie_api')
WIZ = os.path.join(MOD, 'wizard')


class FakeFields(object):
    def __getattr__(self, name):
        def build(*args, **kwargs):
            return (name, args, kwargs)
        return build


class FakeModel(object):
    pass


class FakeOsV(object):
    osv_memory = FakeModel
    except_osv = Exception


class FakeGroup(object):
    def __init__(self, group_id):
        self.id = group_id


class FakeUser(object):
    def __init__(self, group_ids):
        self.groups_id = [FakeGroup(g) for g in group_ids]


class FakeUsers(object):
    def __init__(self, groups):
        self.groups = groups
        self.calls = []

    def browse(self, cr, uid, user_id, context=None):
        self.calls.append((uid, user_id))
        return FakeUser(self.groups)

    def simple_browse(self, cr, uid, user_id, context=None):
        if context is None:
            context = {}

        ctx = context.copy()
        ctx['prefetch'] = False
        return self.browse(cr, uid, user_id, context=ctx)


class FakeModelData(object):
    def __init__(self, group_id=42):
        self.group_id = group_id
        self.calls = []

    def get_object_reference(self, cr, uid, module_name, xml_id):
        self.calls.append((uid, module_name, xml_id))
        return ('res.groups', self.group_id)


class FakeMinimum(object):
    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result if result is not None else {
            'estado': 'con_datos', 'recibidas': 2,
            'nuevas': 1, 'actualizadas': 1}
        self.error = error

    def actualizar_tiempos_minimos(self, cr, uid, context=None):
        self.calls.append((uid, context))
        if self.error:
            raise self.error
        result = self.result.copy()
        return result


class FakePool(object):
    def __init__(self, users, data, minimum):
        self.services = {
            'res.users': users,
            'ir.model.data': data,
            'giscedata.omie.siom.minimum.time': minimum,
        }

    def get(self, name):
        return self.services[name]


class FakeRecord(object):
    def __init__(self):
        self.state = 'init'


class FakeWizardMixin(object):
    def __init__(self):
        self.record = FakeRecord()
        self.writes = []

    def browse(self, cr, uid, record_id, context=None):
        return self.record

    def simple_browse(self, cr, uid, user_id, context=None):
        if context is None:
            context = {}

        ctx = context.copy()
        ctx['prefetch'] = False
        return self.browse(cr, uid, user_id, context=ctx)

    def write(self, cr, uid, ids, vals, context=None):
        self.writes.append((uid, ids, vals))
        for key, value in vals.items():
            setattr(self.record, key, value)
        return True


class WizardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = {}
        names = ('osv', 'giscedata_omie_api', 'giscedata_omie_api.wizard',
                 'giscedata_omie_api.wizard.wizard_siom_minimum_time')
        for name in names:
            cls.old[name] = sys.modules.get(name)
        stub = types.ModuleType('osv')
        stub.osv = FakeOsV()
        stub.fields = FakeFields()
        sys.modules['osv'] = stub
        pkg = types.ModuleType('giscedata_omie_api')
        pkg.__path__ = [MOD]
        sys.modules[pkg.__name__] = pkg
        sub = types.ModuleType('giscedata_omie_api.wizard')
        sub.__path__ = [WIZ]
        sys.modules[sub.__name__] = sub
        cls.source = importlib.import_module(
            'giscedata_omie_api.wizard.wizard_siom_minimum_time')
        cls.FakeWizard = type(
            'FakeWizard',
            (FakeWizardMixin, cls.source.WizardSiomMinimumTimeUpdate), {})

    @classmethod
    def tearDownClass(cls):
        for name, value in cls.old.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value

    def setUp(self):
        self.users = FakeUsers([42])
        self.data = FakeModelData()
        self.minimum = FakeMinimum()
        self.wizard = self.FakeWizard()
        self.wizard.pool = FakePool(self.users, self.data, self.minimum)
        self.cr = object()

    def call(self, uid=10, ids=None):
        if ids is None:
            ids = [7]
        return self.wizard.actualizar_desde_omie(
            self.cr, uid, ids, context={'lang': 'es_ES'})

    def test_manager_puede_actualizar_y_escalada_solo_backend(self):
        self.assertTrue(self.call())
        self.assertEqual(self.minimum.calls[0][0], 1)
        self.assertEqual(self.minimum.calls[0][1], {'lang': 'es_ES'})
        self.assertEqual(self.wizard.writes[0][0], 10)
        self.assertEqual(self.data.calls[0][1:],
                         ('giscedata_omie_api', 'group_giscedata_omie_oferta_u'))

    def test_admin_puede_actualizar_sin_buscar_grupo(self):
        self.users.groups = []
        self.assertTrue(self.call(uid=1))
        self.assertFalse(self.data.calls)

    def test_no_manager_no_puede_actualizar(self):
        self.users.groups = []
        with self.assertRaises(Exception):
            self.call(uid=10)
        self.assertFalse(self.minimum.calls)
        self.assertFalse(self.wizard.writes)

    def test_usuario_de_otro_grupo_no_puede_actualizar(self):
        self.users.groups = [999]
        with self.assertRaises(Exception):
            self.call()
        self.assertFalse(self.minimum.calls)

    def test_ejecucion_doble_denegada(self):
        self.call()
        with self.assertRaises(Exception):
            self.call()
        self.assertEqual(len(self.minimum.calls), 1)

    def test_asistente_no_necesita_ambito(self):
        self.call()
        self.assertEqual(self.minimum.calls, [(1, {'lang': 'es_ES'})])
        self.assertNotIn('scope', self.wizard.writes[0][2])

    def test_solo_un_asistente(self):
        with self.assertRaises(Exception):
            self.call(ids=[7, 8])
        self.assertFalse(self.minimum.calls)

    def test_nulos_no_permitidos(self):
        with self.assertRaises(Exception):
            self.call(ids=[])
        self.assertFalse(self.minimum.calls)

    def test_resultados_visibles(self):
        self.call()
        self.assertEqual(self.wizard.record.state, 'done')
        self.assertEqual(self.wizard.record.recibidas, 2)
        self.assertEqual(self.wizard.record.nuevas, 1)
        self.assertEqual(self.wizard.record.actualizadas, 1)
        self.assertIn('actualizados correctamente', self.wizard.record.info)

    def test_respuesta_vacia_es_informativa(self):
        self.minimum.result = {'estado': 'vacia', 'recibidas': 0,
                               'nuevas': 0, 'actualizadas': 0}
        self.call()
        self.assertEqual(self.wizard.record.state, 'done')
        self.assertIn('sin filas', self.wizard.record.info)
        self.assertIn('Se conservan', self.wizard.record.info)

    def test_error_backend_no_se_disfraza_de_exito(self):
        self.minimum.error = RuntimeError('Sin conexion')
        with self.assertRaises(RuntimeError):
            self.call()
        self.assertEqual(self.wizard.record.state, 'init')
        self.assertFalse(self.wizard.writes)

    def test_vista_y_menu_estan_bajo_configuracion_siom(self):
        xml = ElementTree.parse(os.path.join(WIZ, 'wizard_siom_minimum_time_view.xml'))
        actions = xml.findall(".//record[@model='ir.actions.act_window']")
        self.assertEqual(len(actions), 1)
        menu = xml.find(".//menuitem[@id='menu_wizard_siom_minimum_time_update']")
        self.assertEqual(menu.attrib['parent'], 'menu_omie_siom_limits')
        self.assertEqual(menu.attrib['groups'], 'group_giscedata_omie_oferta_u')
        with open(os.path.join(WIZ, 'wizard_siom_minimum_time_view.xml')) as handle:
            self.assertNotIn('scope', handle.read())

    def test_vista_llama_al_metodo_correcto(self):
        xml = ElementTree.parse(os.path.join(WIZ, 'wizard_siom_minimum_time_view.xml'))
        buttons = xml.findall(".//button[@type='object']")
        self.assertEqual([b.attrib['name'] for b in buttons],
                         ['actualizar_desde_omie'])

    def test_migracion_instala_modelo_y_acl(self):
        file_path = os.path.join(MOD, 'migrations', '5.0.26.12',
                                 'post-0003_wizard_siom_minimum_time.py')
        with open(file_path, 'r') as f:
            content = f.read()
        self.assertIn("'wizard.siom.minimum.time.update'", content)
        self.assertIn('mh.update_access_csv', content)
        self.assertIn('wizard/wizard_siom_minimum_time_view.xml', content)


if __name__ == '__main__':
    unittest.main()
