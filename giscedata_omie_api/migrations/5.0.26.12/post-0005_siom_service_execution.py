# -*- coding: utf-8 -*-
from __future__ import absolute_import

from oopgrade.oopgrade import MigrationHelper
from tools import get_current_module


def up(cursor, installed_version):
    if not installed_version:
        return

    mh = MigrationHelper(cursor, module_name=get_current_module())

    mh.init_model(model_name='giscedata.omie.siom.service.execution')

    mh.update_xml(xml_path='giscedata_omie_siom_service_execution_view.xml')

    mh.update_access_csv(model_ids=['model_giscedata_omie_siom_service_execution'])

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS giscedata_omie_siom_service_pending_idx
        ON giscedata_omie_siom_service_execution (servicio, estado, id)
    ''')

def down(cursor, installed_version):
    pass


migrate = up
