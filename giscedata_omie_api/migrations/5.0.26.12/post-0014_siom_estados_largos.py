# -*- coding: utf-8 -*-
"""Ampliar campos estado: algunos estados SIOM superan VARCHAR(16)."""
from __future__ import absolute_import


def up(cursor, installed_version):
    if not installed_version:
        return
    cursor.execute('''
        ALTER TABLE giscedata_omie_siom_service_execution
            ALTER COLUMN estado TYPE varchar(32)
    ''')
    cursor.execute('''
        ALTER TABLE giscedata_omie_siom_query_execution
            ALTER COLUMN estado TYPE varchar(32)
    ''')


def down(cursor, installed_version):
    pass


migrate = up
