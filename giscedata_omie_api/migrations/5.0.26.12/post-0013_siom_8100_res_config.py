# -*- coding: utf-8 -*-
"""Parametros configurables 8100; preservar cambios posteriores del ERP."""
from __future__ import absolute_import

from oopgrade.oopgrade import MigrationHelper
from tools import get_current_module


def up(cursor, installed_version):
    if not installed_version:
        return
    mh = MigrationHelper(cursor, module_name=get_current_module())
    mh.update_xml(xml_path='giscedata_omie_data.xml')


def down(cursor, installed_version):
    pass


migrate = up
