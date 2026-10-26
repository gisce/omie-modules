# -*- coding: utf-8 -*-
"""Auditoria de servicios SIOM no ENCOL y serializacion de envios MD/MI.

Sin Redis: reserva PostgreSQL durable y lock corto compartido MD/MI.
El estado incierto BLOQUEA siguientes envios hasta conciliacion manual.
"""
from __future__ import absolute_import

from osv import osv, fields
from tools.translate import _


SERVICIOS_OFERTAS = ('ServicioAltaOfertasMD', 'ServicioAltaOfertasMI')


class EnvioOMIEPendiente(Exception):
    """Ya hay un fichero enviado cuya respuesta no consta de forma fiable."""


class GiscedataOmieSiomServiceExecution(osv.osv):

    _name = 'giscedata.omie.siom.service.execution'
    _description = 'Invocaciones de servicios SIOM y envios MD/MI'
    _order = 'fecha_intento desc, id desc'
    _rec_name = 'servicio'

    def _nueva_conexion(self, cr):
        from pooler import get_db
        return get_db(cr.dbname).cursor()

    def _reservar(self, cr, uid, servicio, oferta_id=None):
        if not servicio or len(servicio) > 100:
            raise ValueError('Nombre de servicio SIOM invalido')
        if oferta_id is not None and servicio not in SERVICIOS_OFERTAS:
            raise ValueError('oferta_id solo permitido en altas de ofertas')
        if servicio in SERVICIOS_OFERTAS and not oferta_id:
            raise ValueError('Los envios de ofertas requieren oferta_id')
        dbcr = self._nueva_conexion(cr)
        try:
            if servicio in SERVICIOS_OFERTAS:
                # Un solo fichero MD o MI pendiente por agente, no por servicio.
                # La aplicacion/ERP representa un unico agente y certificado.
                dbcr.execute('SELECT pg_advisory_xact_lock(hashtext(%s), %s)',
                             ('giscedata_omie_api.siom.ofertas', 1))
                dbcr.execute('''
                    SELECT id, servicio, estado
                      FROM giscedata_omie_siom_service_execution
                     WHERE servicio IN ('ServicioAltaOfertasMD', 'ServicioAltaOfertasMI')
                       AND estado IN ('reservada', 'incierta')
                     ORDER BY id DESC LIMIT 1
                ''')
                anterior = dbcr.fetchone()
                if anterior:
                    raise EnvioOMIEPendiente(
                        'No se ha enviado nada: el intento SIOM #%s (%s) esta %s. '
                        'Comprobar la respuesta en OMIE antes de continuar.' % anterior)
            dbcr.execute('''
                INSERT INTO giscedata_omie_siom_service_execution
                    (servicio, oferta_id, usuario_id, fecha_intento, estado, detalle)
                VALUES (%s, %s, %s, clock_timestamp() AT TIME ZONE 'UTC',
                        'reservada', 'Reserva persistida antes de invocar SOAP')
                RETURNING id
            ''', (servicio, oferta_id, uid))
            execution_id = dbcr.fetchone()[0]
            dbcr.commit()
            return execution_id
        except BaseException:
            dbcr.rollback()
            raise
        finally:
            dbcr.close()

    def _finalizar(self, cr, execution_id, estado, detalle):
        if estado not in ('respondida', 'incierta'):
            raise ValueError('Estado de finalizacion invalido')
        dbcr = self._nueva_conexion(cr)
        try:
            dbcr.execute('''
                UPDATE giscedata_omie_siom_service_execution
                   SET estado=%s, detalle=%s,
                       fecha_fin=clock_timestamp() AT TIME ZONE 'UTC'
                 WHERE id=%s AND estado='reservada'
            ''', (estado, detalle[:256], execution_id))
            if dbcr.rowcount != 1:
                raise ValueError('Estado de servicio no reservado: %s' % execution_id)
            dbcr.commit()
        except BaseException:
            dbcr.rollback()
            raise
        finally:
            dbcr.close()

    def ejecutar_servicio(self, cr, uid, servicio, llamada, oferta_id=None):
        """La confirmacion SOAP libera el carril de oferta, no su aceptacion.

        No se reintenta NUNCA una oferta: transporte/SOAP Fault ambiguo deja
        reserva en estado incierto y bloquea siguientes envios hasta conciliar.
        """
        if not callable(llamada):
            raise ValueError('llamada debe ser callable')
        execution_id = self._reservar(cr, uid, servicio, oferta_id=oferta_id)
        try:
            respuesta = llamada()
        except BaseException as exc:
            try:
                self._finalizar(cr, execution_id, 'incierta',
                               'Excepcion en SOAP: %s' % type(exc).__name__)
            except Exception:
                pass
            raise
        self._finalizar(cr, execution_id, 'respondida',
                       'Respuesta SOAP recibida; validar resultado funcional')
        return respuesta

    def conciliar_envio(self, cr, uid, execution_id, justificacion):
        """Solo administrador, con comprobacion humana del estado en OMIE.

        Registrar fecha y motivo sin borrar la auditoria. Este metodo no
        verifica con OMIE: no usarlo sin comprobacion externa documentada.
        """
        if uid != 1:
            raise osv.except_osv('Acceso denegado', 'Solo un administrador puede conciliar envios SIOM.')
        if not justificacion or len(justificacion.strip()) < 15:
            raise ValueError('Indique la comprobacion en OMIE (15 caracteres minimo)')
        dbcr = self._nueva_conexion(cr)
        try:
            dbcr.execute('SELECT pg_advisory_xact_lock(hashtext(%s), %s)',
                         ('giscedata_omie_api.siom.ofertas', 1))
            dbcr.execute('''
                UPDATE giscedata_omie_siom_service_execution
                   SET estado='reconciliada', detalle=%s,
                       fecha_fin=clock_timestamp() AT TIME ZONE 'UTC'
                 WHERE id=%s AND estado='incierta'
                   AND servicio IN ('ServicioAltaOfertasMD', 'ServicioAltaOfertasMI')
            ''', ('Conciliacion manual: ' + justificacion[:230], execution_id))
            if dbcr.rowcount != 1:
                raise ValueError('No existe un envio incierto conciliable con ese id')
            dbcr.commit()
        except BaseException:
            dbcr.rollback()
            raise
        finally:
            dbcr.close()
        return True

    _columns = {
        'servicio': fields.char('Servicio WS', size=100, required=True, readonly=True),
        # Entero, NO many2one: la oferta puede no estar confirmada en la
        # transaccion ERP y un FK aqui bloquearia la reserva independiente.
        'oferta_id': fields.integer('ID de oferta origen', readonly=True),
        'usuario_id': fields.many2one('res.users', 'Usuario', readonly=True),
        'fecha_intento': fields.datetime('Peticion UTC', required=True, readonly=True),
        'fecha_fin': fields.datetime('Finalizacion UTC', readonly=True),
        'estado': fields.selection([
            ('reservada', 'Peticion en curso'),
            ('respondida', 'SOAP respondido'),
            ('incierta', 'Resultado incierto: necesita conciliacion'),
            ('reconciliada', 'Conciliacion manual documentada'),
        ], 'Estado', required=True, readonly=True),
        'detalle': fields.char('Diagnostico', size=256, readonly=True),
    }


GiscedataOmieSiomServiceExecution()
