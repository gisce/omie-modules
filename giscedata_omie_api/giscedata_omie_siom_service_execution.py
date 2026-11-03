# -*- coding: utf-8 -*-
"""Auditoria de servicios SIOM y serializacion conservadora de ofertas MD/MI.

Los envios se preparan y se marcan como 'enviando' en transacciones
independientes, antes de invocar SOAP. Una reserva 'preparada' caducada puede
cancelarse de forma segura: su antiguo propietario ya no podra promoverla a
'enviando', puesto que ambas operaciones compiten por el mismo bloqueo PG.

NO se recuperan automaticamente envios 'enviando' o 'incierta': pueden haber
llegado a OMIE. Nunca se reintentan automaticamente las ofertas.
"""
from __future__ import absolute_import

import json
import logging

from osv import osv, fields
from tools.translate import _


_logger = logging.getLogger(__name__)

SERVICIOS_OFERTAS = ('ServicioAltaOfertasMD', 'ServicioAltaOfertasMI')
# Una preparacion normal dura milisegundos; este limite evita cancelar
# preparaciones activas ante pequenas pausas de proceso. No es un lease SOAP.
PREPARADA_CADUCIDAD_SEGUNDOS = 60
# Solo para permitir que el administrador DOCUMENTE la conciliacion de un
# posible proceso muerto; no implica que el envio no haya llegado a OMIE.
CONCILIACION_ANTIGUEDAD_SEGUNDOS = 300


class EnvioOMIEPendiente(Exception):
    """Existe un envio anterior pendiente o una reserva cancelada."""


class GiscedataOmieSiomServiceExecution(osv.osv):

    _name = 'giscedata.omie.siom.service.execution'
    _description = 'Invocaciones de servicios SIOM y envios MD/MI'
    _order = 'fecha_intento desc, id desc'
    _rec_name = 'servicio'

    def _nueva_conexion(self, cr):
        from pooler import get_db
        return get_db(cr.dbname).cursor()

    def _bloquear_carril_ofertas(self, dbcr):
        dbcr.execute('SELECT pg_advisory_xact_lock(hashtext(%s), %s)',
                     ('giscedata_omie_api.siom.ofertas', 1))

    def _cancelar_preparadas_caducadas(self, dbcr):
        """Solo bajo el lock de ofertas. CAS impide enviar tras cancelar.

        No inferimos que un proceso haya muerto: simplemente invalidamos
        reservas aun NO promovidas a 'enviando'. La promocion requiere el
        mismo lock y comprueba el estado antes de permitir cualquier SOAP.
        """
        dbcr.execute('''
            UPDATE giscedata_omie_siom_service_execution
               SET estado='cancelada',
                   detalle='Preparacion caducada: anulada antes del envio SOAP',
                   fecha_fin=clock_timestamp() AT TIME ZONE 'UTC'
             WHERE servicio IN ('ServicioAltaOfertasMD', 'ServicioAltaOfertasMI')
               AND estado='preparada'
               AND fecha_intento <= (clock_timestamp() AT TIME ZONE 'UTC')
                                    - (%s * interval '1 second')
        ''', (PREPARADA_CADUCIDAD_SEGUNDOS,))
        return dbcr.rowcount

    def recuperar_envios_pendientes(self, cr, uid):
        """Recupera EXCLUSIVAMENTE preparaciones caducadas (no SOAP).

        Puede invocarse desde el automatismo, aunque _reservar ya la ejecuta
        de forma atomica antes de comprobar si hay otro envio pendiente.
        Devuelve el numero de reservas anuladas, nunca reenvia ofertas.
        """
        dbcr = self._nueva_conexion(cr)
        try:
            self._bloquear_carril_ofertas(dbcr)
            canceladas = self._cancelar_preparadas_caducadas(dbcr)
            dbcr.commit()
            return canceladas
        except BaseException:
            dbcr.rollback()
            raise
        finally:
            dbcr.close()

    def ultimos_identificadores(self, cr, tipo_mercado, agente,
                               fecha_sesion, unidad, num_sesion=None):
        """Mayor version y NumOferta de la auditoria DURABLE, lectura fresca.

        Debe llamarse manteniendo el advisory lock del NEGOCIO. Usar un
        cursor independiente evita snapshots viejos del cursor principal
        en instalaciones que no utilicen aislamiento READ COMMITTED.
        Los registros preparados/cancelados nunca han iniciado SOAP.
        """
        if tipo_mercado not in ('MD', 'MI'):
            raise ValueError('Mercado no soportado')
        dbcr = self._nueva_conexion(cr)
        try:
            dbcr.execute('''
                SELECT MAX(version_enviada), MAX(num_oferta_enviado)
                  FROM giscedata_omie_siom_service_execution
                 WHERE servicio=%s
                   AND id_remitente=%s AND fecha_sesion=%s
                   AND id_unidad=%s AND num_sesion IS NOT DISTINCT FROM %s
                   AND estado NOT IN ('preparada', 'cancelada')
            ''', (
                'ServicioAltaOfertasMD' if tipo_mercado == 'MD'
                else 'ServicioAltaOfertasMI',
                agente, fecha_sesion, unidad, num_sesion))
            fila = dbcr.fetchone() or (None, None)
            dbcr.commit()
            return fila
        except BaseException:
            dbcr.rollback()
            raise
        finally:
            dbcr.close()

    def _resolver_respuestas_pendientes(self, cr, dbcr, permitir_local=False):
        """Comprueba la integracion SOLO con evidencia persistida en el ERP.

        Una respuesta SOAP no demuestra commit del cursor de negocio. No se
        libera una respuesta pendiente si la oferta no tiene el ID de respuesta
        y la version enviada. La inspeccion local solo permite continuar a la
        MISMA transaccion que mantiene el lock de versiones; no confirma nada.
        """
        dbcr.execute('''
            SELECT id, oferta_id, version_enviada, id_respuesta
              FROM giscedata_omie_siom_service_execution
             WHERE servicio IN ('ServicioAltaOfertasMD', 'ServicioAltaOfertasMI')
               AND estado='respondida_pendiente'
             ORDER BY id ASC
        ''')
        pendientes = dbcr.fetchall()
        for execution_id, oferta_id, version, id_respuesta in pendientes:
            if not id_respuesta or version is None or not oferta_id:
                raise EnvioOMIEPendiente(
                    'Respuesta SIOM #%s sin identificadores suficientes para '
                    'comprobar la integracion ERP.' % execution_id)
            consulta = '''
                SELECT ver_mensaje, id_mensaje_respuesta, state
                  FROM giscedata_omie_oferta WHERE id=%s
            '''
            dbcr.execute(consulta, (oferta_id,))
            confirmada = self._oferta_coincide(dbcr.fetchone(), version, id_respuesta)
            if confirmada:
                dbcr.execute('''
                    UPDATE giscedata_omie_siom_service_execution
                       SET estado='integrada'
                     WHERE id=%s AND estado='respondida_pendiente'
                ''', (execution_id,))
                if dbcr.rowcount != 1:
                    raise EnvioOMIEPendiente('La integracion SIOM ha cambiado')
                continue
            if permitir_local:
                # Solo se permite dentro del mismo cursor de negocio (tras
                # adquirir el advisory lock de versiones en enviar_oferta).
                cr.execute(consulta, (oferta_id,))
                if self._oferta_coincide(cr.fetchone(), version, id_respuesta):
                    continue
            raise EnvioOMIEPendiente(
                'La respuesta SIOM #%s no esta confirmada en el ERP. '
                'No se envia una nueva oferta hasta conciliarla.' % execution_id)

    @staticmethod
    def _oferta_coincide(fila, version, id_respuesta):
        if not fila or fila[0] is None or not fila[1]:
            return False
        return (int(fila[0]) == int(version) and
                str(fila[1]) == str(id_respuesta) and
                fila[2] in ('enviada', 'enviada_error'))

    def _reservar(self, cr, uid, servicio, oferta_id=None, metadatos=None,
                 permitir_pendientes_propias=False):
        if not servicio or len(servicio) > 100:
            raise ValueError('Nombre de servicio SIOM invalido')
        if oferta_id is not None and servicio not in SERVICIOS_OFERTAS:
            raise ValueError('oferta_id solo permitido en altas de ofertas')
        if servicio in SERVICIOS_OFERTAS and not oferta_id:
            raise ValueError('Los envios de ofertas requieren oferta_id')
        dbcr = self._nueva_conexion(cr)
        try:
            if servicio in SERVICIOS_OFERTAS:
                self._bloquear_carril_ofertas(dbcr)
                self._cancelar_preparadas_caducadas(dbcr)
                self._resolver_respuestas_pendientes(
                    cr, dbcr, permitir_local=permitir_pendientes_propias)
                dbcr.execute('''
                    SELECT id, servicio, estado
                      FROM giscedata_omie_siom_service_execution
                     WHERE servicio IN ('ServicioAltaOfertasMD', 'ServicioAltaOfertasMI')
                       AND estado IN ('preparada', 'enviando', 'incierta', 'reservada')
                     ORDER BY id DESC LIMIT 1
                ''')
                anterior = dbcr.fetchone()
                if anterior:
                    raise EnvioOMIEPendiente(
                        'No se ha enviado nada: el intento SIOM #%s (%s) esta %s. '
                        'Verificar el envio anterior antes de continuar.' % anterior)
            # Los servicios no-oferta siguen registrandose, sin carril MD/MI.
            estado = ('preparada' if servicio in SERVICIOS_OFERTAS
                      else 'enviando')
            detalle = ('Reserva anterior a SOAP' if servicio in SERVICIOS_OFERTAS
                       else 'Servicio SIOM iniciado')
            if metadatos is not None:
                dbcr.execute('''
                    INSERT INTO giscedata_omie_siom_service_execution
                        (servicio, oferta_id, usuario_id, fecha_intento, estado,
                         detalle, id_mensaje_enviado, version_enviada, num_oferta_enviado,
                         id_remitente, fecha_sesion, id_unidad, num_sesion)
                    VALUES (%s, %s, %s, clock_timestamp() AT TIME ZONE 'UTC',
                            %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                ''', (servicio, oferta_id, uid, estado, detalle,
                      metadatos.get('id_mensaje'), metadatos.get('version'),
                      metadatos.get('num_oferta'), metadatos.get('id_remitente'),
                      metadatos.get('fecha_sesion'), metadatos.get('id_unidad'),
                      metadatos.get('num_sesion')))
            else:
                dbcr.execute('''
                    INSERT INTO giscedata_omie_siom_service_execution
                        (servicio, oferta_id, usuario_id, fecha_intento, estado, detalle)
                    VALUES (%s, %s, %s, clock_timestamp() AT TIME ZONE 'UTC',
                            %s, %s) RETURNING id
                ''', (servicio, oferta_id, uid, estado, detalle))
            execution_id = dbcr.fetchone()[0]
            dbcr.commit()
            return execution_id
        except BaseException:
            dbcr.rollback()
            raise
        finally:
            dbcr.close()

    def _iniciar_envio(self, cr, execution_id):
        """Punto de no retorno: confirma 'enviando' ANTES del SOAP.

        Si otra transaccion cancelo la reserva 'preparada', nunca se envia.
        Mantener este orden y el advisory lock compartido con la cancelacion.
        """
        dbcr = self._nueva_conexion(cr)
        try:
            self._bloquear_carril_ofertas(dbcr)
            dbcr.execute('''
                UPDATE giscedata_omie_siom_service_execution
                   SET estado='enviando', detalle='Envio SOAP autorizado'
                 WHERE id=%s AND estado='preparada'
                   AND servicio IN ('ServicioAltaOfertasMD', 'ServicioAltaOfertasMI')
            ''', (execution_id,))
            if dbcr.rowcount != 1:
                raise EnvioOMIEPendiente(
                    'La reserva SIOM #%s ya no esta preparada; '
                    'no se ha invocado SOAP.' % execution_id)
            dbcr.commit()
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
                 WHERE id=%s AND estado='enviando'
            ''', (estado, detalle[:256], execution_id))
            if dbcr.rowcount != 1:
                raise ValueError('Estado de servicio no enviando: %s' % execution_id)
            dbcr.commit()
        except BaseException:
            dbcr.rollback()
            raise
        finally:
            dbcr.close()

    @staticmethod
    def _valor_campo(item):
        if isinstance(item, dict):
            return item.get('v')
        return item

    def _datos_respuesta(self, respuesta):
        """Respuesta Zeep serializada, sin perder el cuerpo del resultado OMIE."""
        from zeep import helpers
        obj = helpers.serialize_object(respuesta)
        payload = json.dumps(obj, ensure_ascii=True, default=str)
        if not isinstance(obj, dict):
            return payload, None, None
        respuesta_id = self._valor_campo(obj.get('IdMensaje'))
        respuesta_general = obj.get('Respuesta') or []
        if isinstance(respuesta_general, dict):
            respuesta_general = [respuesta_general]
        codigo = None
        if respuesta_general and isinstance(respuesta_general[0], dict):
            codigo = self._valor_campo(respuesta_general[0].get('CodigoRespuesta'))
        return payload, respuesta_id, codigo

    def _finalizar_con_respuesta(self, cr, execution_id, respuesta):
        """Confirma JSON y metadatos antes de dejar salir el SOAP del controlador.

        La integracion de negocio NO se marca como confirmada aqui, pues el
        cursor principal todavia puede hacer rollback posteriormente.
        """
        contenido, id_respuesta, codigo = self._datos_respuesta(respuesta)
        dbcr = self._nueva_conexion(cr)
        try:
            dbcr.execute('''
                UPDATE giscedata_omie_siom_service_execution
                   SET estado='respondida_pendiente',
                       respuesta_json=%s, id_respuesta=%s, codigo_respuesta=%s,
                       detalle='SOAP recibido; integracion ERP pendiente de commit',
                       fecha_fin=clock_timestamp() AT TIME ZONE 'UTC'
                 WHERE id=%s AND estado='enviando'
            ''', (contenido, id_respuesta, codigo, execution_id))
            if dbcr.rowcount != 1:
                raise ValueError('Estado de servicio no enviando: %s' % execution_id)
            dbcr.commit()
        except BaseException:
            dbcr.rollback()
            raise
        finally:
            dbcr.close()

    def ejecutar_servicio(self, cr, uid, servicio, llamada, oferta_id=None,
                          metadatos=None, permitir_pendientes_propias=False):
        """Registra el SOAP sin alterar la semantica sincrona del ERP.

        Respuesta SOAP libera el carril; la aceptacion funcional es distinta.
        Timeout o error de transporte de OFERTA = incierta, NUNCA reintento.
        Si la reserva fue cancelada antes de promoverse, no se invoca SOAP.
        """
        if not callable(llamada):
            raise ValueError('llamada debe ser callable')
        execution_id = self._reservar(
            cr, uid, servicio, oferta_id=oferta_id, metadatos=metadatos,
            permitir_pendientes_propias=permitir_pendientes_propias)
        if servicio in SERVICIOS_OFERTAS:
            self._iniciar_envio(cr, execution_id)
        try:
            respuesta = llamada()
        except BaseException as exc:
            try:
                self._finalizar(cr, execution_id, 'incierta',
                               'Excepcion en SOAP: %s' % type(exc).__name__)
            except Exception:
                # Conservar la excepcion original. 'enviando' sigue bloqueando.
                _logger.exception(
                    'No se pudo registrar fallo SOAP SIOM del intento %s',
                    execution_id)
            # Python 2.7 puede relanzar el IOError de auditoria en vez
            # de la excepcion original de SOAP si usamos raise a secas.
            raise exc
        if servicio in SERVICIOS_OFERTAS and metadatos is not None:
            # Si falla parseo/persistencia NO liberar el carril: puede haberse
            # procesado en OMIE y no hay evidencia durable de la respuesta.
            try:
                self._finalizar_con_respuesta(cr, execution_id, respuesta)
            except BaseException as exc:
                try:
                    self._finalizar(cr, execution_id, 'incierta',
                                   'SOAP recibido; fallo al persistir respuesta')
                except Exception:
                    # Sin estado durable, permanece 'enviando' y bloquea
                    # futuros envios MD/MI. No ocultar el error de parseo.
                    _logger.exception(
                        'No se pudo marcar incierta la respuesta SIOM %s',
                        execution_id)
                raise exc
        else:
            self._finalizar(cr, execution_id, 'respondida',
                           'Respuesta SOAP recibida; validar resultado funcional')
        return respuesta

    def conciliar_envio(self, cr, uid, execution_id, justificacion,
                        proceso_terminado=False):
        """Conciliacion humana documentada, SIN consultar automaticamente OMIE.

        'incierta' permite la operacion tradicional. Para 'enviando' o el
        antiguo 'reservada' exigimos declaracion explicita de que el proceso
        anterior ya termino, ademas de antiguedad y comprobacion externa.
        NO se admite conciliar reservas 'preparada': se cancelan por CAS.
        """
        if uid != 1:
            raise osv.except_osv(
                'Acceso denegado', 'Solo un administrador puede conciliar envios SIOM.')
        if not justificacion or len(justificacion.strip()) < 15:
            raise ValueError('Indique la comprobacion en OMIE (15 caracteres minimo)')
        dbcr = self._nueva_conexion(cr)
        try:
            self._bloquear_carril_ofertas(dbcr)
            dbcr.execute('''
                SELECT estado,
                       fecha_intento <= (clock_timestamp() AT TIME ZONE 'UTC')
                                        - (%s * interval '1 second')
                  FROM giscedata_omie_siom_service_execution
                 WHERE id=%s
                   AND servicio IN ('ServicioAltaOfertasMD', 'ServicioAltaOfertasMI')
                 FOR UPDATE
            ''', (CONCILIACION_ANTIGUEDAD_SEGUNDOS, execution_id))
            anterior = dbcr.fetchone()
            if not anterior or anterior[0] not in ('incierta', 'enviando', 'reservada', 'respondida_pendiente'):
                raise ValueError('No existe un envio pendiente conciliable con ese id')
            if anterior[0] != 'incierta':
                if not proceso_terminado:
                    raise ValueError('Confirme que el proceso emisor ya ha terminado')
                if not anterior[1]:
                    raise ValueError('El envio aun es demasiado reciente para conciliar')
            dbcr.execute('''
                UPDATE giscedata_omie_siom_service_execution
                   SET estado='reconciliada', detalle=%s,
                       fecha_fin=clock_timestamp() AT TIME ZONE 'UTC'
                 WHERE id=%s AND estado=%s
                   AND servicio IN ('ServicioAltaOfertasMD', 'ServicioAltaOfertasMI')
            ''', ('Conciliacion manual: ' + justificacion[:230], execution_id, anterior[0]))
            if dbcr.rowcount != 1:
                raise ValueError('El estado del envio cambio durante la conciliacion')
            dbcr.commit()
        except BaseException:
            dbcr.rollback()
            raise
        finally:
            dbcr.close()
        return True

    _columns = {
        'servicio': fields.char('Servicio WS', size=100, required=True, readonly=True),
        # Sin FK: oferta creada en la transaccion ERP todavia no confirmada.
        'oferta_id': fields.integer('ID de oferta origen', readonly=True),
        'usuario_id': fields.many2one('res.users', 'Usuario', readonly=True),
        'fecha_intento': fields.datetime('Peticion UTC', required=True, readonly=True, timezone='UTC'),
        'fecha_fin': fields.datetime('Finalizacion UTC', readonly=True, timezone='UTC'),
        'id_mensaje_enviado': fields.char('ID mensaje enviado', size=64, readonly=True),
        'version_enviada': fields.integer('Version enviada', readonly=True),
        'num_oferta_enviado': fields.integer('Numero oferta MI enviado', readonly=True),
        'id_remitente': fields.char('Agente ofertante', size=16, readonly=True),
        'fecha_sesion': fields.char('Fecha sesion', size=10, readonly=True),
        'id_unidad': fields.char('Unidad', size=16, readonly=True),
        'num_sesion': fields.char('Sesion IDA', size=8, readonly=True),
        'id_respuesta': fields.char('ID mensaje respuesta', size=64, readonly=True),
        'codigo_respuesta': fields.char('Codigo respuesta OMIE', size=64, readonly=True),
        'respuesta_json': fields.text('Respuesta SOAP serializada', readonly=True),
        'estado': fields.selection([
            ('preparada', 'Preparada (SOAP aun no iniciado)'),
            ('enviando', 'Comunicacion SOAP iniciada o incierta'),
            ('respondida', 'SOAP respondido (legacy)'),
            ('respondida_pendiente', 'SOAP recibido; commit ERP pendiente'),
            ('integrada', 'SOAP integrado y comprobado en ERP'),
            ('incierta', 'Resultado incierto: necesita conciliacion'),
            ('cancelada', 'Preparacion cancelada sin SOAP'),
            ('reconciliada', 'Conciliacion manual documentada'),
            # Compatibilidad con registros creados antes de esta version.
            ('reservada', 'Reserva antigua: resultado desconocido'),
        ], 'Estado', required=True, readonly=True),
        'detalle': fields.char('Diagnostico', size=256, readonly=True),
    }


GiscedataOmieSiomServiceExecution()
