# -*- coding: utf-8 -*-
from __future__ import absolute_import
from oopgrade.oopgrade import MigrationHelper
from tools import config, get_current_module


def up(cursor, installed_version):
    if not installed_version or config.updating_all:
        return

    mh = MigrationHelper(cursor, module_name=get_current_module())

    model_names = ('giscedata.omie.siom.minimum.time',
                   'giscedata.omie.siom.minimum.time.sync')
    for model_name in model_names:
        mh.init_model(model_name=model_name)

    mh.update_xml(xml_path='giscedata_omie_siom_minimum_time_view.xml')

    mh.update_access_csv(model_ids=[
        'model_giscedata_omie_siom_minimum_time',
        'model_giscedata_omie_siom_minimum_time_sync',
    ])

def down(cursor, installed_version):
    pass


migrate = up
