# -*- coding: utf-8 -*-
from __future__ import absolute_import

from oopgrade.oopgrade import MigrationHelper
from tools import get_current_module


def up(cursor, installed_version):
    if not installed_version:
        return

    mh = MigrationHelper(cursor, module_name=get_current_module())

    xml_paths = ('wizard/wizard_consulta_datos_usuario_view.xml',
                 'wizard/wizard_consulta_fecha_hora_view.xml',
                 'wizard/wizard_consulta_sesiones_view.xml',
                 'wizard/wizard_consulta_omie_view.xml',
                 'wizard/wizard_llenar_horas_oferta_view.xml')

    for xml_path in xml_paths:
        mh.update_xml(xml_path=xml_path)

def down(cursor, installed_version):
    pass


migrate = up
