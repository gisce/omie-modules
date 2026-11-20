# -*- coding: utf-8 -*-
"""Ampliar observaciones 8100 con parseo normalizado, sin activar bloqueos."""
from __future__ import absolute_import

from oopgrade.oopgrade import MigrationHelper
from tools import get_current_module


def up(cursor, installed_version):
    if not installed_version:
        return
    mh = MigrationHelper(cursor, module_name=get_current_module())
    mh.init_model(model_name='giscedata.omie.siom.exclusion.observation')
    mh.update_xml(xml_path='giscedata_omie_siom_exclusion_observation_view.xml')


def down(cursor, installed_version):
    pass


migrate = up
