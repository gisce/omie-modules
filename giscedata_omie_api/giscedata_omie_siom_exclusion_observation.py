# -*- coding: utf-8 -*-
"""Historial y refresco de intervalos SIOM 8100.

La consulta se puede actualizar sin activar los bloqueos. La zona horaria
sigue pendiente de confirmar con OMIE, y la activacion es explicita.
"""
from __future__ import absolute_import

from datetime import datetime
import logging
from osv import osv, fields
from tools.translate import _

from giscedata_omie_api.giscedata_omie_siom_exclusion_observation_parser import (
    preparar_observacion_8100)

_logger = logging.getLogger(__name__)


class GiscedataOmieSiomExclusionObservation(osv.osv):
    _name = 'giscedata.omie.siom.exclusion.observation'
    _description = 'Observaciones y configuracion 8100 (activacion explicita)'
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
            'interpretacion': valores['interpretacion'],
            'total_filas': valores['total_filas'],
            'huella_sha256': valores['huella_sha256'],
            'reglas_activadas': False,
        }

    def sincronizar_8100(self, cursor, uid, context=None, client=None):
        """Consulta y guarda 8100 con una transaccion independiente y breve.

        Reutilizable por el cron, tras un rechazo explicito y en ejecuciones
        manuales autorizadas. Un fallo no borra snapshots previos; la reserva
        SOAP mantiene su propia auditoria mediante el controlador SIOM.
        """
        if uid != 1:
            raise osv.except_osv('Permisos insuficientes',
                                 _('Solo el administrador puede sincronizar SIOM 8100.'))
        control = self.pool.get('giscedata.omie.siom.query.execution')
        dbcr = control._nueva_conexion(cursor)
        try:
            resultado = self.registrar_observacion_8100(
                dbcr, 1, context=context, client=client)
            dbcr.commit()
            return resultado
        except BaseException:
            dbcr.rollback()
            raise
        finally:
            dbcr.close()

    def cron_actualizar_8100(self, cursor, uid, context=None):
        """Punto de entrada para ir.cron (30 min, sin ponerse al dia en rafaga).

        No depende del huso horario ni activa la aplicacion de ventanas;
        exige que el certificado/AppID y el entorno ya esten configurados.
        """
        resultado = self.sincronizar_8100(cursor, uid, context=context)
        if resultado['interpretacion'] != 'valida':
            _logger.warning('SIOM 8100: sincronizacion sin reglas validas (%s); '
                            'se mantienen las anteriores', resultado['interpretacion'])
        return True

    _columns = {
        'fecha_consulta': fields.datetime('Consulta UTC', required=True,
                                          readonly=True, timezone='UTC'),
        'estado': fields.selection([
            ('vacia', 'Sin filas'), ('con_datos', 'Filas recibidas')],
            'Resultado', required=True, readonly=True),
        'total_filas': fields.integer('Número de filas', readonly=True),
        'interpretacion': fields.selection([
            ('valida', 'Intervalos interpretados'),
            ('vacia', 'Respuesta vacía; reglas anteriores intactas'),
            ('no_interpretable', 'Contrato no reconocido'),
        ], 'Interpretación', readonly=True),
        'intervalos_json': fields.text('Intervalos normalizados (JSON)', readonly=True),
        'error_interpretacion': fields.char('Error de interpretación', size=256,
                                            readonly=True),
        'columnas_json': fields.text('Columnas y tipos (JSON)', readonly=True),
        'muestras_json': fields.text('Muestras (JSON)', readonly=True),
        'respuesta_json': fields.text('Evidencia ENCOL original (JSON)', readonly=True),
        'huella_sha256': fields.char('SHA-256 evidencia', size=64, readonly=True),
    }


GiscedataOmieSiomExclusionObservation()
