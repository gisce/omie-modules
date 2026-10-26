# -*- coding: utf-8 -*-
from __future__ import absolute_import

from oopgrade.oopgrade import MigrationHelper
from tools import config, get_current_module


def up(cursor, installed_version):
    if not installed_version or config.updating_all:
        return

    mh = MigrationHelper(cursor, module_name=get_current_module())

    mh.init_model(model_name='wizard.siom.minimum.time.update')

    mh.update_xml(xml_path='wizard/wizard_siom_minimum_time_view.xml')

    mh.update_access_csv(model_ids=['model_wizard_siom_minimum_time_update'])

def down(cursor, installed_version):
    pass


migrate = up
