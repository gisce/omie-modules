# -*- coding: utf-8 -*-
"""Registrar cron 8100, inactivo hasta configurar el agente."""
from __future__ import absolute_import

from oopgrade.oopgrade import MigrationHelper
from tools import get_current_module


def up(cursor, installed_version):
    if not installed_version:
        return
    mh = MigrationHelper(cursor, module_name=get_current_module())
    mh.update_xml(xml_path='giscedata_omie_siom_exclusion_cron.xml')


def down(cursor, installed_version):
    pass


migrate = up
