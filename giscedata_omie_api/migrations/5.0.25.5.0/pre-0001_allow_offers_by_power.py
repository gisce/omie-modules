# -*- encoding: utf-8 -*-
from __future__ import absolute_import
from oopgrade.oopgrade import add_columns, column_exists
from tools import config


def up(cursor, installed_version):
    if not installed_version:
        return

    if config.updating_all:
        return

    table_name = 'giscedata_omie_oferta'
    field_name = 'uni_medida'

    if not column_exists(cursor, table_name, field_name):
        # Add uni_medida field to offer
        add_columns(
            cursor, {
                table_name: [
                    (field_name, 'VARCHAR(16)')
                ]
            }
        )

        # Set default uni_medida
        cursor.execute("UPDATE giscedata_omie_oferta SET uni_medida = 'E'")

def down(cursor, installed_version):
    pass


migrate = up
