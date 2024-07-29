# -*- encoding: utf-8 -*-
import logging
import pooler
from oopgrade.oopgrade import load_data, load_data_records


def up(cursor, installed_version):
    if not installed_version:
        return

    logger = logging.getLogger('openerp.migration')

    logger.info("Creating pooler")
    pool = pooler.get_pool(cursor.dbname)

    ##UPDATAR UN MODUL NOU AL CREAR-LO O AFEGIR UNA COLUMNA##
    logger.info("Creating table: giscedata.omie.oferta")
    pool.get("giscedata.omie.oferta")._auto_init(cursor, context={'module': 'giscedata_omie_api'})
    logger.info("Table created succesfully.")

    ##UPDATAR UN MODUL NOU AL CREAR-LO O AFEGIR UNA COLUMNA##
    logger.info("Creating table: wizard.llenar.horas.oferta")
    pool.get("wizard.llenar.horas.oferta")._auto_init(cursor, context={'module': 'giscedata_omie_api'})
    logger.info("Table created succesfully.")

    ##UPDATAR UN MODUL NOU AL CREAR-LO O AFEGIR UNA COLUMNA##
    logger.info("Creating table: giscedata.omie.oferta.hora")
    pool.get("giscedata.omie.oferta.hora")._auto_init(cursor, context={'module': 'giscedata_omie_api'})
    logger.info("Table created succesfully.")

    ##UPATAR UN XML SENCER##
    logger.info("Updating XML giscedata_omie_oferta_view.xml")
    load_data(
        cursor, 'giscedata_omie_api', 'wizard/wizard_llenar_horas_oferta_view.xml', idref=None, mode='update'
    )
    logger.info("XMLs succesfully updated.")

    ##UPATAR UN XML SENCER##
    logger.info("Updating XML giscedata_omie_oferta_view.xml")
    load_data(
        cursor, 'giscedata_omie_api', 'giscedata_omie_oferta_view.xml', idref=None, mode='update'
    )
    logger.info("XMLs succesfully updated.")

    logger.info("Updating access CSV")
    load_data(
        cursor, 'giscedata_omie_api', 'security/ir.model.access.csv', idref=None, mode='update'
    )
    logger.info("CSV succesfully updated.")

def down(cursor, installed_version):
    pass


migrate = up