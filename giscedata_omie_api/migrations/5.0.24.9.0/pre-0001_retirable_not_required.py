# -*- encoding: utf-8 -*-
import logging


def up(cursor, installed_version):
    if not installed_version:
        return

    logger = logging.getLogger('openerp.migration')

    logger.info("Setting 'ret' column as not required...")
    cursor.execute('ALTER TABLE IF EXISTS giscedata_omie_oferta_hora ALTER COLUMN ret DROP NOT NULL')
    logger.info("Set 'ret' column as not required.")


def down(cursor, installed_version):
    pass


migrate = up
