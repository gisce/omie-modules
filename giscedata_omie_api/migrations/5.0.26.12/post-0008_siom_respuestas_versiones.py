# -*- coding: utf-8 -*-
"""10D.2: persistencia independiente de respuestas SOAP y version enviada.

Las filas existentes siguen en sus estados legacy; NO damos por integradas
respuestas previas sin la nueva evidencia durable.
"""
from __future__ import absolute_import

from oopgrade.oopgrade import MigrationHelper
from tools import config, get_current_module


def up(cursor, installed_version):
    if not installed_version or config.updating_all:
        return

    mh = MigrationHelper(cursor, module_name=get_current_module())

    mh.init_model(model_name='giscedata.omie.siom.service.execution')

    mh.update_xml(xml_path='giscedata_omie_siom_service_execution_view.xml')

def down(cursor, installed_version):
    pass


migrate = up
