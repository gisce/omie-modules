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
    pool.get("giscedata.omie.oferta")._auto_init(cursor,context={'module': 'giscedata_omie_api'})
    logger.info("Table created succesfully.")

    ##UPDATAR UN MODUL NOU AL CREAR-LO O AFEGIR UNA COLUMNA##
    logger.info("Creating table: giscedata.omie.oferta.consulta")
    pool.get("giscedata.omie.oferta.consulta")._auto_init(cursor, context={'module': 'giscedata_omie_api'})
    logger.info("Table created succesfully.")

    ##UPDATAR UN MODUL NOU AL CREAR-LO O AFEGIR UNA COLUMNA##
    logger.info("Creating table: giscedata.omie.oferta.bloque")
    pool.get("giscedata.omie.oferta.bloque")._auto_init(cursor, context={'module': 'giscedata_omie_api'})
    logger.info("Table created succesfully.")

    ##UPDATAR UN MODUL NOU AL CREAR-LO O AFEGIR UNA COLUMNA##
    logger.info("Creating table: giscedata.omie.oferta.peticion")
    pool.get("giscedata.omie.oferta.peticion")._auto_init(cursor, context={'module': 'giscedata_omie_api'})
    logger.info("Table created succesfully.")

    ##UPATAR UN XML SENCER##
    logger.info("Updating XML giscedata_omie_api/giscedata_omie_oferta_view.xml")
    load_data(
        cursor, 'giscedata_omie_api', 'giscedata_omie_api/giscedata_omie_oferta_view.xml', idref=None,
        mode='update'
    )
    logger.info("XMLs succesfully updated.")

    logger.info("Updating access CSV")
    load_data(
        cursor, 'giscedata_facturacio_switching', 'security/ir.model.access.csv', idref=None, mode='update'
    )
    logger.info("CSV succesfully updated.")


def down(cursor, installed_version):
    pass


migrate = up