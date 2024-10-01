# -*- encoding: utf-8 -*-
import logging
import pooler
from oopgrade.oopgrade import load_data, load_data_records
from tools import config


def up(cursor, installed_version):
    if not installed_version:
        return

    if config.updating_all:
        return

    logger = logging.getLogger('openerp.migration')

    logger.info("Creating pooler")
    pool = pooler.get_pool(cursor.dbname)

    ##UPDATAR UN MODUL NOU AL CREAR-LO O AFEGIR UNA COLUMNA##
    logger.info("Creating table: 'wizard.llenar.horas.oferta")
    pool.get("wizard.llenar.horas.oferta")._auto_init(cursor, context={
        'module': 'giscedata_omie_api'})
    logger.info("Table created succesfully.")

    ##UPDATAR UNA PART DE L'XML (POSAR LA ID)##
    logger.info("Updating XMLs")
    list_of_records = [
        "view_wizard_llenar_horas_oferta_form",
    ]
    load_data_records(
        cursor, 'giscedata_omie_api', 'wizard/wizard_llenar_horas_oferta_view.xml', list_of_records,
        mode='update'
    )
    logger.info("XMLs succesfully updated.")

def down(cursor, installed_version):
    pass


migrate = up