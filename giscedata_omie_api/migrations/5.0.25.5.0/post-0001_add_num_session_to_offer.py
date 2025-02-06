# -*- encoding: utf-8 -*-
from __future__ import absolute_import
from oopgrade.oopgrade import load_data_records
from tools import config
import pooler


def up(cursor, installed_version):
    if not installed_version:
        return

    if config.updating_all:
        return

    # Update data model
    pool = pooler.get_pool(cursor.dbname)
    pool.get('giscedata.omie.oferta')._auto_init(cursor, context={'module': 'giscedata_omie_api'})

    # Update views
    record_ids = ['giscedata_omie_oferta_form', 'giscedata_omie_oferta_form', 'listado_ofertas']
    load_data_records(cursor, 'giscedata_omie_api', 'giscedata_omie_oferta_view.xml', record_ids)

def down(cursor, installed_version):
    pass


migrate = up
