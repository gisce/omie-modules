# -*- coding: utf-8 -*-
"""Control sincrono SIOM ENCOL, con registro durable en PostgreSQL.

La reserva se confirma ANTES de la llamada SOAP en otra transaccion.
No altera la transaccion de negocio que pasa OpenERP.
Reintenta SOLO rechazos explicitos de frecuencia para consultas de lectura.
Una respuesta recibida NO implica necesariamente exito funcional OMIE.

Se limita a consultas ENCOL; los envios MD/IDA requieren su propia politica.
"""
from __future__ import absolute_import

from datetime import datetime, timedelta
from osv import osv, fields
import logging
import re
import time
from tools.translate import _

_logger = logging.getLogger(__name__)

# Proteccion local si OMIE no publica limite para una consulta. No es un
# valor oficial de 8101; los automatismos mantienen su propia cadencia.
MINIMO_LOCAL_SIN_8101_MS = 5000
ANTIGUEDAD_MINIMA_CONCILIACION_SEGUNDOS = 900


def _fecha_pg_utc(valor):
    """psycopg2 devuelve datetime para columnas timestamp; los tests pueden usar texto."""
    if isinstance(valor, datetime):
        return valor
    try:
        return datetime.strptime(valor, '%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        return datetime.strptime(valor, '%Y-%m-%d %H:%M:%S')


class TiempoMinimoNoCumplido(Exception):
    """No se ha llamado a OMIE: aun no ha transcurrido el tiempo minimo."""

    def __init__(self, consulta, disponible_en, espera_segundos):
        self.consulta = consulta
        self.disponible_en = disponible_en
        self.espera_segundos = espera_segundos
        Exception.__init__(self, 'Consulta %s: esperar %.3f segundos (hasta %s UTC)' % (
            consulta, espera_segundos, disponible_en.strftime('%Y-%m-%d %H:%M:%S.%f')
        ))


class ConsultaSIOMPendiente(Exception):
    """La misma consulta todavia tiene una solicitud SOAP en curso."""


class RechazoFrecuenciaOMIE(Exception):
    """OMIE rechazo una consulta por cadencia, no se debe interpretar como datos."""

    def __init__(self, consulta, detalle):
        self.consulta = consulta
        self.detalle = detalle
        Exception.__init__(self, 'OMIE rechazo por frecuencia la consulta %s: %s' %
                           (consulta, detalle))


# Los codigos concretos de rechazo de OMIE aun no estan documentados en nuestro
# entorno. No se consideran rechazos los errores funcionales genericos.
try:
    text_type = unicode
    string_types = (basestring,)
    long_type = long
except NameError:  # Python 3
    text_type = str
    string_types = (str,)
    long_type = int

_FRECUENCIA_TXT = re.compile(
    u'(?:tiempo\\s+m[ií]nimo|intervalo\\s+m[ií]nimo|frecuencia\\s+de\\s+consultas|'
    u'minimum\\s+(?:time|interval)|too\\s+many\\s+requests|rate\\s+limit)', re.I)


def _valor_siOM(value):
    if isinstance(value, dict):
        return value.get('v', value.get('value', ''))
    return value


def _rechazo_en_respuesta(respuesta, codigos=None):
    """Solo inspecciona el elemento Respuesta, no filas de datos ni ofertas.

    Devuelve el diagnostico o None. Se admiten codigos exactos suministrados
    por la configuracion de despliegue al confirmarse los codigos de OMIE.
    """
    if respuesta is None:
        return None
    try:
        from zeep.helpers import serialize_object
        datos = serialize_object(respuesta)
    except (ImportError, AttributeError, TypeError):
        datos = respuesta
    if not isinstance(datos, dict):
        return None
    respuestas = datos.get('Respuesta') or []
    if isinstance(respuestas, dict):
        respuestas = [respuestas]
    for item in respuestas:
        if not isinstance(item, dict):
            continue
        codigo = _valor_siOM(item.get('CodigoRespuesta'))
        codigo = text_type(codigo or '').strip()
        textos = item.get('TextoRespuesta') or []
        if not isinstance(textos, (tuple, list)):
            textos = [textos]
        texto = u' '.join(text_type(_valor_siOM(t) or u'') for t in textos)
        if codigo and codigo in (codigos or ()):
            return 'CodigoRespuesta=%s' % codigo
        # Evitamos reintentar una consulta marcada como correcta (Codigo=0).
        if codigo != '0' and _FRECUENCIA_TXT.search(texto + ' ' + codigo):
            return 'CodigoRespuesta=%s; %s' % (codigo[:64], texto[:150])
    return None


def _rechazo_en_excepcion(exc):
    """Solo un rechazo explicito; no clasificar timeouts ni red como frecuencia."""
    respuesta = getattr(exc, 'response', None)
    if getattr(respuesta, 'status_code', None) == 429:
        return 'HTTP 429'
    # Fault SOAP con codigo o texto expreso, no cualquier error de transporte.
    if exc.__class__.__name__ == 'Fault':
        texto = text_type(exc)
        if _FRECUENCIA_TXT.search(texto):
            return texto[:180]
    return None


class SinConfiguracionTiempoMinimo(Exception):
    """No hay límite 8101 conocido para la consulta (modo estricto)."""


def _codigo_consulta(consulta):
    if isinstance(consulta, bool):
        raise ValueError('Codigo de consulta invalido')
    try:
        codigo = int(consulta)
    except (TypeError, ValueError, OverflowError):
        raise ValueError('Codigo de consulta invalido')
    if codigo <= 0 or codigo > 2147483647 or unicode_code_invalid(consulta, codigo):
        raise ValueError('Codigo de consulta invalido')
    return codigo


class GiscedataOmieSiomQueryExecution(osv.osv):

    _name = 'giscedata.omie.siom.query.execution'
    _description = 'Intentos de consulta SIOM (registro persistente independiente)'
    _order = 'fecha_intento desc, id desc'
    _rec_name = 'consulta'

    def _nueva_conexion(self, cr):
        """OpenERP 5: la base actual comparte el registro, no la transacción."""
        from pooler import get_db
        return get_db(cr.dbname).cursor()

    def _reservar(self, cr, uid, consulta, exigir_configuracion=False, margen_ms=500,
                 minimo_local_ms=MINIMO_LOCAL_SIN_8101_MS):
        """Transaccion corta: lock -> leer -> comprobar -> insertar -> commit.

        No conservar bloqueos de PostgreSQL durante las llamadas a OMIE.
        El momento de intento es el reloj PostgreSQL, no el del worker.
        """
        codigo = _codigo_consulta(consulta)
        if (isinstance(minimo_local_ms, bool) or
                not isinstance(minimo_local_ms, (int, long_type)) or minimo_local_ms < 0):
            raise ValueError('minimo_local_ms invalido')
        dbcr = self._nueva_conexion(cr)
        try:
            # Locks de sesion NO; advisory_xact_lock se libera en commit/rollback.
            dbcr.execute('SELECT pg_advisory_xact_lock(hashtext(%s), %s)',
                         ('giscedata_omie_api.siom.encol', codigo))
            dbcr.execute('''
                SELECT tiempo_agente_ms, tiempo_certificado_ms
                  FROM giscedata_omie_siom_minimum_time
                 WHERE consulta = %s
            ''', (codigo,))
            limite_fila = dbcr.fetchone()
            configurada = limite_fila is not None
            if not configurada and exigir_configuracion:
                raise SinConfiguracionTiempoMinimo(
                    'No hay datos 8101 para consulta %s; no se ha enviado nada' % codigo)
            if configurada:
                agente, certificado = limite_fila
                if agente is None or certificado is None or min(agente, certificado) < 0:
                    raise ValueError('Configuracion 8101 incompleta/invalida para %s' % codigo)
                limite = max(agente, certificado)
            else:
                # Limite LOCAL, sin pretender que OMIE haya comunicado un cero.
                limite = minimo_local_ms
            dbcr.execute("SELECT clock_timestamp() AT TIME ZONE 'UTC'")
            ahora = _fecha_pg_utc(dbcr.fetchone()[0])
            dbcr.execute('''
                SELECT fecha_intento, estado
                  FROM giscedata_omie_siom_query_execution
                 WHERE consulta = %s
                 ORDER BY fecha_intento DESC, id DESC LIMIT 1
            ''', (codigo,))
            anterior = dbcr.fetchone()
            if anterior and anterior[1] == 'reservada':
                raise ConsultaSIOMPendiente(
                    'La consulta SIOM %s tiene una solicitud sin respuesta; '
                    'no se ha enviado otra peticion' % codigo)
            if anterior and (configurada or minimo_local_ms > 0):
                instante_previo = _fecha_pg_utc(anterior[0])
                # Margen operativo: reserva local anterior a la recepcion OMIE.
                permitido = instante_previo + timedelta(
                    milliseconds=(limite + max(0, margen_ms) if configurada and limite > 0
                                  else limite))
                if ahora < permitido:
                    espera = (permitido - ahora).total_seconds()
                    raise TiempoMinimoNoCumplido(codigo, permitido, espera)
            dbcr.execute('''
                INSERT INTO giscedata_omie_siom_query_execution
                    (consulta, usuario_id, fecha_intento, limite_ms, configurada,
                     estado, detalle)
                VALUES (%s, %s, %s, %s, %s, 'reservada', %s)
                RETURNING id
            ''', (codigo, uid, ahora, limite, configurada,
                  '8101 conocida' if configurada else 'Sin 8101; intervalo local %s ms' % limite))
            execution_id = dbcr.fetchone()[0]
            dbcr.commit()  # Intencionadamente independiente de la transaccion ERP.
            return execution_id
        except BaseException:
            dbcr.rollback()
            raise
        finally:
            dbcr.close()

    def _finalizar(self, cr, execution_id, estado, detalle=None):
        """Confirmar el resultado en otro cursor, tambien independientemente."""
        dbcr = self._nueva_conexion(cr)
        try:
            dbcr.execute('''
                UPDATE giscedata_omie_siom_query_execution
                   SET estado = %s, detalle = %s,
                       fecha_fin = clock_timestamp() AT TIME ZONE 'UTC'
                 WHERE id = %s AND estado = 'reservada'
            ''', (estado, detalle, execution_id))
            if dbcr.rowcount != 1:
                raise ValueError('Intento SIOM sin estado reservado: %s' % execution_id)
            dbcr.commit()
        except BaseException:
            dbcr.rollback()
            raise
        finally:
            dbcr.close()

    def _finalizar_sin_ocultar(self, cr, execution_id, estado, detalle):
        """Mejor esfuerzo de auditoria sin sustituir la excepcion original.

        Si falla PostgreSQL, la reserva sigue siendo conservadora: no se
        intenta otro SOAP automaticamente. El error de auditoria va al log.
        """
        try:
            self._finalizar(cr, execution_id, estado, detalle)
            return True
        except Exception:
            _logger.exception(
                'No se pudo registrar el resultado SIOM del intento %s',
                execution_id)
            return False

    def _sincronizar_8101_inicial(self, cr, codigo):
        """Intentar 8101 una sola vez cuando aun no hay historial de consulta.

        El intento de 8101 queda registrado antes del SOAP. Si falla o
        devuelve vacio, la consulta operativa sigue usando intervalo local.
        No volver a lanzarla automaticamente en cada consulta: eso generaria
        trafico innecesario y eventualmente reintentos sin control.
        """
        if str(codigo) == '8101':
            return
        dbcr = self._nueva_conexion(cr)
        try:
            dbcr.execute("""
                SELECT id FROM giscedata_omie_siom_query_execution
                 WHERE consulta = %s LIMIT 1
            """, (8101,))
            hubo_intento = dbcr.fetchone() is not None
        finally:
            dbcr.rollback()
            dbcr.close()
        if not hubo_intento:
            if not self._refrescar_8101(cr):
                _logger.warning('8101 inicial sin limites utilizables; usar control local')

    def conciliar_reserva(self, cr, uid, execution_id, motivo,
                          confirmado=False, usuario_solicitante=None):
        """Cerrar reserva huerfana, solo admin, tras comprobacion externa.

        El lock evita carreras con _reservar, pero no demuestra que el
        worker este muerto ni que OMIE haya terminado. La confirmacion
        administrativa DEBE basarse en una verificacion real.
        """
        if uid != 1:
            raise osv.except_osv('Acceso denegado',
                                 'La conciliacion requiere permisos de administrador.')
        if isinstance(execution_id, bool):
            raise ValueError('Identificador de intento invalido')
        try:
            execution_id = int(execution_id)
        except (TypeError, ValueError, OverflowError):
            raise ValueError('Identificador de intento invalido')
        if execution_id <= 0:
            raise ValueError('Identificador de intento invalido')
        if not confirmado:
            raise ValueError('Debe confirmarse que el worker ya no ejecuta la consulta')
        if (not isinstance(motivo, string_types) or
                len(motivo.strip()) < 15 or len(motivo) > 1000):
            raise ValueError('Indique un motivo de conciliacion (15-1000 caracteres)')
        dbcr = self._nueva_conexion(cr)
        try:
            dbcr.execute("""
                SELECT consulta, estado, fecha_intento
                  FROM giscedata_omie_siom_query_execution WHERE id = %s
            """, (execution_id,))
            fila = dbcr.fetchone()
            if not fila or fila[1] != 'reservada':
                raise ValueError('La reserva no existe o ya esta finalizada')
            codigo = fila[0]
            dbcr.execute('SELECT pg_advisory_xact_lock(hashtext(%s), %s)',
                         ('giscedata_omie_api.siom.encol', codigo))
            dbcr.execute("""
                SELECT estado, fecha_intento
                  FROM giscedata_omie_siom_query_execution WHERE id = %s FOR UPDATE
            """, (execution_id,))
            estado, fecha = dbcr.fetchone()
            if estado != 'reservada':
                raise ValueError('La reserva ha cambiado de estado')
            dbcr.execute("SELECT clock_timestamp() AT TIME ZONE 'UTC'")
            ahora = _fecha_pg_utc(dbcr.fetchone()[0])
            antiguedad = (ahora - _fecha_pg_utc(fecha)).total_seconds()
            if antiguedad < ANTIGUEDAD_MINIMA_CONCILIACION_SEGUNDOS:
                raise ValueError('Reserva demasiado reciente para conciliacion (%s s)' %
                                 ANTIGUEDAD_MINIMA_CONCILIACION_SEGUNDOS)
            dbcr.execute("""
                UPDATE giscedata_omie_siom_query_execution
                   SET estado = 'conciliada',
                       fecha_fin = clock_timestamp() AT TIME ZONE 'UTC',
                       motivo_conciliacion = %s, usuario_conciliacion = %s
                 WHERE id = %s AND estado = 'reservada'
            """, (motivo.strip(), usuario_solicitante or uid, execution_id))
            if dbcr.rowcount != 1:
                raise ValueError('La reserva ha cambiado de estado')
            dbcr.commit()
            _logger.warning('Reserva SIOM %s (consulta %s) conciliada por uid=%s',
                            execution_id, codigo, usuario_solicitante or uid)
            return True
        except BaseException:
            dbcr.rollback()
            raise
        finally:
            dbcr.close()

    def _refrescar_8101(self, cr, codigo=None):
        """Transaccion independiente: la sincronizacion sobrevive a rollback ERP.

        La propia consulta 8101 pasa por ejecutar_consulta; nunca se refresca
        recursivamente a causa de un rechazo de la 8101.
        """
        dbcr = self._nueva_conexion(cr)
        try:
            model = self.pool.get('giscedata.omie.siom.minimum.time')
            resultado = model.actualizar_tiempos_minimos(dbcr, 1)
            dbcr.commit()
            # Una respuesta vacia (o parcial sin el codigo rechazado) no
            # valida limites antiguos para repetir una peticion.
            return (resultado['estado'] == 'con_datos' and
                    (codigo is None or codigo in resultado['consultas_recibidas']))
        except Exception as exc:
            dbcr.rollback()
            _logger.warning('No se pudo actualizar SIOM 8101 tras rechazo: %s',
                            type(exc).__name__)
            return False
        finally:
            dbcr.close()

    def _limite_conocido(self, cr, codigo):
        dbcr = self._nueva_conexion(cr)
        try:
            dbcr.execute("""SELECT tiempo_agente_ms, tiempo_certificado_ms
                             FROM giscedata_omie_siom_minimum_time
                            WHERE consulta = %s""", (codigo,))
            fila = dbcr.fetchone()
            if fila is None:
                return None
            if fila[0] is None or fila[1] is None or min(fila) < 0:
                return None
            return max(fila)
        finally:
            dbcr.close()

    def ejecutar_consulta(self, cr, uid, codigo_consulta, llamada, context=None,
                          exigir_configuracion=False, reintentos=1,
                          espera_maxima_segundos=10.0, margen_ms=500,
                          codigos_frecuencia=None, dormir=None,
                          refrescar_8101=None,
                          minimo_local_ms=MINIMO_LOCAL_SIN_8101_MS,
                          sincronizacion_inicial=True):
        """Ejecuta ENCOL; solo reintenta rechazo explicito de frecuencia.

        No duerme si la espera supera el presupuesto. Nunca reintenta timeouts.
        El intento fallido queda registrado y reinicia el contador.
        `dormir` y `refrescar_8101` inyectables para pruebas unitarias.
        """
        if not callable(llamada):
            raise ValueError('llamada debe ser callable')
        if (reintentos < 0 or reintentos > 3 or espera_maxima_segundos < 0 or
                margen_ms < 0 or isinstance(minimo_local_ms, bool) or
                not isinstance(minimo_local_ms, (int, long_type)) or minimo_local_ms < 0):
            raise ValueError('Politica de reintentos invalida')
        dormir = dormir or time.sleep
        contexto = context or {}
        if codigos_frecuencia is None:
            codigos_frecuencia = contexto.get('siom_codigos_rechazo_frecuencia', ())
        codigo = _codigo_consulta(codigo_consulta)
        if sincronizacion_inicial:
            self._sincronizar_8101_inicial(cr, codigo)
        hubo_rechazo = False
        ultimo_detalle = ''
        total_dormido = 0.0
        for numero in range(reintentos + 1):
            try:
                intento = self._reservar(cr, uid, codigo_consulta,
                                         exigir_configuracion=exigir_configuracion,
                                         margen_ms=margen_ms,
                                         minimo_local_ms=minimo_local_ms)
            except TiempoMinimoNoCumplido as exc:
                if not hubo_rechazo:
                    raise
                # La excepcion ya incluye el margen de recepcion, no duplicarlo.
                restante = exc.espera_segundos + 0.01
                if restante + total_dormido > espera_maxima_segundos:
                    raise RechazoFrecuenciaOMIE(codigo_consulta,
                                                '%s. Proximo intento UTC: %s' %
                                                (ultimo_detalle, exc.disponible_en))
                dormir(restante)
                total_dormido += restante
                intento = self._reservar(cr, uid, codigo_consulta,
                                         exigir_configuracion=exigir_configuracion,
                                         margen_ms=margen_ms,
                                         minimo_local_ms=minimo_local_ms)
            try:
                respuesta = llamada()
            except BaseException as exc:
                # Incluso interpretar una Fault puede fallar. Nunca perder la
                # excepcion SOAP ni dejar la reserva sin un cierre intentado.
                try:
                    frecuencia = _rechazo_en_excepcion(exc)
                except Exception:
                    _logger.exception('Error al interpretar excepcion SOAP SIOM')
                    frecuencia = None
                if frecuencia:
                    if not self._finalizar_sin_ocultar(
                            cr, intento, 'rechazada_frecuencia', frecuencia):
                        # Python 2.7: un raise implicito puede recuperar una
                        # excepcion secundaria; conservar la SOAP original.
                        raise exc
                    ultimo_detalle = frecuencia
                else:
                    self._finalizar_sin_ocultar(
                        cr, intento, 'incierta',
                        'Excepcion local o transporte: %s' % type(exc).__name__)
                    # En Python 2.7, relanzar explicitamente la excepcion
                    # original evita propagar el error de interpretacion.
                    raise exc
            else:
                try:
                    frecuencia = _rechazo_en_respuesta(respuesta, codigos_frecuencia)
                except BaseException as exc:
                    # SOAP respondio, pero no sabemos interpretar el resultado.
                    # La consulta NO se reintenta; la evidencia es incierta.
                    self._finalizar_sin_ocultar(
                        cr, intento, 'incierta',
                        'SOAP recibido; error interpretando respuesta: %s' %
                        type(exc).__name__)
                    raise exc
                self._finalizar(cr, intento,
                               'rechazada_frecuencia' if frecuencia else 'respondida',
                               frecuencia or 'SOAP respondido; verificar Respuesta OMIE')
                if not frecuencia:
                    return respuesta
                ultimo_detalle = frecuencia
            hubo_rechazo = True
            if codigo == 8101:
                raise RechazoFrecuenciaOMIE(codigo_consulta,
                                            '%s (no refrescar 8101 recursivamente)' % ultimo_detalle)
            if numero >= reintentos:
                raise RechazoFrecuenciaOMIE(codigo_consulta, ultimo_detalle)
            if refrescar_8101 is None:
                refrescado = self._refrescar_8101(cr, codigo)
            else:
                refrescado = refrescar_8101(cr)
            if not refrescado:
                raise RechazoFrecuenciaOMIE(
                    codigo_consulta, u'%s. No se ha podido actualizar 8101' % ultimo_detalle)
            # Sin un tiempo conocido y positivo, no sabemos cuando reintentar.
            limite = self._limite_conocido(cr, codigo)
            if not limite:
                raise RechazoFrecuenciaOMIE(
                    codigo_consulta, u'%s. No existe un límite positivo conocido' % ultimo_detalle)
        raise AssertionError('Inalcanzable')

    _columns = {
        'consulta': fields.integer('Código de consulta', required=True, readonly=True, select=1),
        'usuario_id': fields.many2one('res.users', 'Usuario solicitante', readonly=True),
        'fecha_intento': fields.datetime('Reserva / intento UTC', required=True, readonly=True, timezone='UTC'),
        'fecha_fin': fields.datetime('Fin local UTC', readonly=True, timezone='UTC'),
        'limite_ms': fields.integer('Límite aplicado (ms)', readonly=True),
        'configurada': fields.boolean('Existe configuración 8101', readonly=True),
        'estado': fields.selection([
            ('reservada', 'Reservada; resultado pendiente'),
            ('respondida', 'Respuesta SOAP recibida (no implica éxito)'),
            ('incierta', 'Fallo local/transport; resultado incierto'),
            ('rechazada_frecuencia', 'OMIE rechazo por frecuencia'),
            ('conciliada', 'Reserva cerrada manualmente (verificacion externa)'),
        ], 'Estado del intento', required=True, readonly=True),
        'detalle': fields.char('Diagnóstico local', size=256, readonly=True),
        'motivo_conciliacion': fields.text('Motivo de conciliacion', readonly=True),
        'usuario_conciliacion': fields.many2one('res.users', 'Conciliado por', readonly=True)
    }

def unicode_code_invalid(original, code):
    """Evitar truncar decimales al convertir, compatible con Python 2.7."""
    try:
        return str(original).strip() != str(code)
    except Exception:
        return True


GiscedataOmieSiomQueryExecution()
