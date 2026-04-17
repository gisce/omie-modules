# -*- encoding: utf-8 -*-
from __future__ import absolute_import
from oopgrade.oopgrade import MigrationHelper
from tools import config


def up(cursor, installed_version):
    if not installed_version or config.updating_all:
        return

    module_name = 'giscedata_omie_api'
    mh = MigrationHelper(cursor, module_name=module_name)

    model_names = ['giscedata.omie.casacion',
                   'giscedata.omie.casacion.continua',
                   'giscedata.omie.programa.casacion']
    for model_name in model_names:
        mh.init_model(model_name=model_name)

    xml_path = 'giscedata_omie_casacion_view.xml'
    record_ids = ['giscedata_omie_casacion_form',
                  'giscedata_omie_casacion_continua_form',
                  'giscedata_omie_programa_casacion_form']
    mh.update_xml_records(xml_path=xml_path, update_record_ids=record_ids)

def down(cursor, installed_version):
    pass


migrate = up
