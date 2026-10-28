# -*- coding: utf-8 -*-
"""Historial de respuestas SIOM 8100: SOLO observación, no exclusiones activas.

No hay reglas de bloqueo hasta validar contrato de columnas, huso horario,
semántica de las ventanas y vigencia con una respuesta real de OMIE.
"""
from __future__ import absolute_import

from datetime import datetime
from osv import osv, fields
from tools.translate import _

from giscedata_omie_api.giscedata_omie_siom_exclusion_observation_parser import (
    preparar_observacion_8100)


class GiscedataOmieSiomExclusionObservation(osv.osv):
    _name = 'giscedata.omie.siom.exclusion.observation'
    _description = 'Historial de observaciones SIOM 8100 (sin reglas activas)'
    _rec_name = 'fecha_consulta'
    _order = 'fecha_consulta desc, id desc'

    def registrar_observacion_8100(self, cursor, uid, context=None, client=None):
        """Una sola consulta ENCOL auditada, después guardar evidencia sin COMMIT.

        Si la respuesta es inválida no guarda nada. Respuesta vacía: guardar
        un nuevo evento histórico, NO borrar ningún registro previo.
        Solo uid=1, o bien wizard Manager que delega tras validar permisos.
        """
        if uid != 1:
            raise osv.except_osv('Permisos insuficientes',
                                 _('La observación SIOM 8100 exige administrador.'))
        if context is None:
            context = {}
        controlador = self.pool.get('giscedata.omie.siom.query.execution')
        datos = controlador._consultar_datos_8100(
            cursor, uid, context=context, client=client)
        valores = preparar_observacion_8100(datos)
        valores['fecha_consulta'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        observacion_id = self.create(cursor, uid, valores, context=context)
        return {
            'observacion_id': observacion_id,
            'estado': valores['estado'],
            'total_filas': valores['total_filas'],
            'huella_sha256': valores['huella_sha256'],
            'reglas_activadas': False,
        }

    _columns = {
        'fecha_consulta': fields.datetime('Consulta UTC', required=True,
                                          readonly=True, timezone='UTC'),
        'estado': fields.selection([
            ('vacia', 'Sin filas'), ('con_datos', 'Filas recibidas')],
            'Resultado', required=True, readonly=True),
        'total_filas': fields.integer('Número de filas', readonly=True),
        'columnas_json': fields.text('Columnas y tipos (JSON)', readonly=True),
        'muestras_json': fields.text('Muestras (JSON)', readonly=True),
        'respuesta_json': fields.text('Evidencia ENCOL original (JSON)', readonly=True),
        'huella_sha256': fields.char('SHA-256 evidencia', size=64, readonly=True),
    }


GiscedataOmieSiomExclusionObservation()
