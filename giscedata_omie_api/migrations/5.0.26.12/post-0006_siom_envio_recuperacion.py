# -*- coding: utf-8 -*-
"""10D.1: actualizar metadatos y tratar reservas legacy de forma conservadora.

Las reservas antiguas NO distinguian si el SOAP habia comenzado: convertirlas
siempre en inciertas (nunca en preparadas recuperables automaticamente).
"""
from __future__ import absolute_import

from oopgrade.oopgrade import MigrationHelper
from tools import get_current_module


def up(cursor, installed_version):
    if not installed_version:
        return
    mh = MigrationHelper(cursor, module_name=get_current_module())
    mh.init_model(model_name='giscedata.omie.siom.service.execution')
    mh.update_xml(xml_path='giscedata_omie_siom_service_execution_view.xml')
    cursor.execute('''
        UPDATE giscedata_omie_siom_service_execution
           SET estado='incierta',
               detalle='Reserva anterior a 10D.1: inicio SOAP desconocido'
         WHERE estado='reservada'
           AND servicio IN ('ServicioAltaOfertasMD', 'ServicioAltaOfertasMI')
    ''')


def down(cursor, installed_version):
    pass


migrate = up
