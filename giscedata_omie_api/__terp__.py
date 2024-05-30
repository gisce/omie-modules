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
    'security/giscedata_omie_oferta_security.xml',
    'security/ir.model.access.csv',
    'giscedata_omie_oferta_view.xml',
    'wizard/wizard_llenar_bloques_oferta_view.xml',
    'wizard/wizard_consulta_fecha_hora_view.xml',
  ],
  "active": False,
  "installable": True
}
