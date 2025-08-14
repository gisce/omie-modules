# -*- encoding: utf-8 -*-
from __future__ import absolute_import
from oopgrade.oopgrade import load_access_rules_from_model_name
from tools import config


def up(cursor, installed_version):
    if not installed_version or config.updating_all:
        return

    module_name = 'giscedata_omie_api'
    model_ids = ['model_giscedata_omie_casacion', 'model_giscedata_omie_casacion_hora']

    load_access_rules_from_model_name(cursor, module_name, model_ids)

def down(cursor, installed_version):
    pass


migrate = up
