# -*- encoding: utf-8 -*-
import logging
import pooler


def up(cursor, installed_version):
    if not installed_version:
        return

    logger = logging.getLogger('openerp.migration')

    pool = pooler.get_pool(cursor.dbname)

    ##UPDATAR UN MODUL NOU AL CREAR-LO O AFEGIR UNA COLUMNA##
    logger.info("Setting 'ret' column as not required...")
    pool.get('giscedata.omie.oferta.hora')._auto_init(cursor, context={'module': 'giscedata_omie_api'})
    logger.info("Set 'ret' column as not required.")

def down(cursor, installed_version):
    pass


migrate = up
