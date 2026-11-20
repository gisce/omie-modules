# -*- coding: utf-8 -*-
"""Modelos, vistas, wizard y ACL para observaciones SIOM 8100 (no bloqueos)."""
from __future__ import absolute_import
from oopgrade.oopgrade import MigrationHelper
from tools import config, get_current_module


def up(cursor, installed_version):
    if not installed_version or config.updating_all:
        return
    mh = MigrationHelper(cursor, module_name=get_current_module())
    for nombre in ('giscedata.omie.siom.exclusion.observation',
                   'wizard.siom.exclusion.observation'):
        mh.init_model(model_name=nombre)
    mh.update_xml(xml_path='giscedata_omie_siom_exclusion_observation_view.xml')
    mh.update_xml(xml_path='wizard/wizard_siom_exclusion_observation_view.xml')
    mh.update_access_csv(model_ids=[
        'model_giscedata_omie_siom_exclusion_observation',
        'model_wizard_siom_exclusion_observation',
    ])


def down(cursor, installed_version):
    pass


migrate = up
