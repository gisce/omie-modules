# -*- coding: utf-8 -*-
from __future__ import absolute_import
from oopgrade.oopgrade import MigrationHelper
from tools import config, get_current_module


def up(cursor, installed_version):
    if not installed_version or config.updating_all:
        return

    module_name = get_current_module()
    mh = MigrationHelper(cursor, module_name=module_name)

    models = ('giscedata.omie.lts.order',
              'giscedata.omie.lts.operation',
              'giscedata.omie.lts.trade')
    for model_name in models:
        mh.init_model(model_name=model_name)

    mh.update_xml(xml_path='security/giscedata_omie_lts_security.xml')

    mh.update_xml(xml_path='giscedata_omie_lts_view.xml')

    model_ids = ['model_giscedata_omie_lts_order',
                 'model_giscedata_omie_lts_operation',
                 'model_giscedata_omie_lts_trade']
    mh.update_access_csv(model_ids=model_ids)

def down(cursor, installed_version):
    pass


migrate = up
