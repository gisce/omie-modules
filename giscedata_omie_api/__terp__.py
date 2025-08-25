# -*- coding: utf-8 -*-
{
  "name": "OMIE API",
  "description": """Este módulo implementa los menús e instala la libreria para poder interactuar con la API de OMIE""",
  "version": "0-dev",
  "author": "Adrià Orellana",
  "category": "Master",
  "depends": [],
  "init_xml": [],
  "demo_xml": [],
  "update_xml": [
    'giscedata_omie_oferta_view.xml',
    'giscedata_omie_casacion_view.xml',
    'wizard/wizard_llenar_horas_oferta_view.xml',
    'wizard/wizard_consulta_fecha_hora_view.xml',
    'wizard/wizard_consulta_sesiones_view.xml',
    'wizard/wizard_consulta_datos_usuario_view.xml',
    'wizard/wizard_consulta_omie_view.xml',
    'security/giscedata_omie_oferta_security.xml',
    'security/ir.model.access.csv',
  ],
  "active": False,
  "installable": True
}
