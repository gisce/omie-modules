# -*- encoding: utf-8 -*-
from __future__ import absolute_import
from oopgrade.oopgrade import add_columns, column_exists
from tools import config


def up(cursor, installed_version):
    if not installed_version:
        return

    if config.updating_all:
        return

    table_name = 'giscedata_omie_oferta_hora'
    field_name = 'desc'

    if not column_exists(cursor, table_name, field_name):
        # Add desc field to offer hour
        add_columns(
            cursor, {
                table_name: [
                    (field_name, 'VARCHAR(16)')
                ]
            }
        )

        # Set default desc
        cursor.execute('UPDATE giscedata_omie_oferta_hora SET "desc" = per')

def down(cursor, installed_version):
    pass


migrate = up
