# -*- coding: utf-8 -*-
from __future__ import absolute_import

from oopgrade.oopgrade import MigrationHelper
from tools import get_current_module


def up(cursor, installed_version):
    if not installed_version:
        return

    mh = MigrationHelper(cursor, module_name=get_current_module())
    mh.init_model(model_name='giscedata.omie.siom.query.execution')
    mh.init_model(model_name='wizard.siom.query.reconcile')
    mh.update_xml(xml_path='giscedata_omie_siom_query_execution_view.xml')
    mh.update_xml(xml_path='wizard/wizard_siom_query_reconcile_view.xml')
    mh.update_access_csv(model_ids=['model_wizard_siom_query_reconcile'])


def down(cursor, installed_version):
    pass


migrate = up
