# -*- encoding: utf-8 -*-
from __future__ import absolute_import
from oopgrade.oopgrade import load_data, load_data_records, load_access_rules_from_model_name
import pooler


def up(cursor, installed_version):
    if not installed_version:
        return

    module_name = 'giscedata_omie_api'

    # Create data models for cassations and wizard
    pool = pooler.get_pool(cursor.dbname)
    pool.get('giscedata.omie.casacion.continua')._auto_init(cursor, context={'module': module_name})
    pool.get('giscedata.omie.programa.casacion')._auto_init(cursor, context={'module': module_name})
    pool.get('wizard.consulta.omie')._auto_init(cursor, context={'module': module_name})

    # Create/update views
    file_name = 'giscedata_omie_casacion_view.xml'
    record_ids = ['giscedata_omie_casacion_tree', 'giscedata_omie_casacion_form',
                  'action_listar_casacions', 'listado_casaciones',
                  'menu_omie_casaciones',
                  'giscedata_omie_casacion_continua_tree', 'giscedata_omie_casacion_continua_form',
                  'action_listar_casacions_continuas', 'listado_casaciones_continuas',
                  'giscedata_omie_programa_casacion_tree', 'giscedata_omie_programa_casacion_form',
                  'action_listar_programa_casacions', 'listado_programa_casaciones']
    load_data_records(cursor, module_name, file_name, record_ids)

    file_name = 'wizard/wizard_consulta_omie_view.xml'
    load_data(cursor, module_name, file_name)

    # Create user rights
    model_ids = ['model_giscedata_omie_casacion_continua',
                 'model_giscedata_omie_programa_casacion',
                 'model_wizard_consulta_omie']
    load_access_rules_from_model_name(cursor, module_name, model_ids)

def down(cursor, installed_version):
    pass


migrate = up
