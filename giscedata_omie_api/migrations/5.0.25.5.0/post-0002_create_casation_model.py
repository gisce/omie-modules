# -*- encoding: utf-8 -*-
from __future__ import absolute_import
from oopgrade.oopgrade import load_data
from tools import config
import pooler


def up(cursor, installed_version):
    if not installed_version:
        return

    if config.updating_all:
        return

    # Create data model
    pool = pooler.get_pool(cursor.dbname)
    pool.get('giscedata.omie.casacion')._auto_init(cursor, context={'module': 'giscedata_omie_api'})

    # Create views
    load_data(cursor, 'giscedata_omie_api', 'giscedata_omie_casacion_view.xml')

    # Reload wizard views to update order in menu
    load_data(cursor, 'giscedata_omie_api', 'wizard/wizard_consulta_datos_usuario_view.xml')
    load_data(cursor, 'giscedata_omie_api', 'wizard/wizard_consulta_fecha_hora_view.xml')
    load_data(cursor, 'giscedata_omie_api', 'wizard/wizard_consulta_sesiones_view.xml')

def down(cursor, installed_version):
    pass


migrate = up
