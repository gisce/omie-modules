# -*- coding: utf-8 -*-
"""Control sincrono SIOM ENCOL, con registro durable en PostgreSQL.

La reserva se confirma ANTES de la llamada SOAP en otra transaccion.
No altera la transaccion de negocio que pasa OpenERP.
Reintenta SOLO rechazos explicitos de frecuencia para consultas de lectura.
Una respuesta recibida NO implica necesariamente exito funcional OMIE.

Se limita a consultas ENCOL; los envios MD/IDA requieren su propia politica.
"""
from __future__ import absolute_import

from datetime import timedelta
from osv import osv, fields
from tools.translate import _
import logging
import re
import time

_logger = logging.getLogger(__name__)


class TiempoMinimoNoCumplido(Exception):
    """No se ha llamado a OMIE: aun no ha transcurrido el tiempo minimo."""

    def __init__(self, consulta, disponible_en, espera_segundos):
        self.consulta = consulta
        self.disponible_en = disponible_en
        self.espera_segundos = espera_segundos
        Exception.__init__(self, 'Consulta %s: esperar %.3f segundos (hasta %s UTC)' % (
            consulta, espera_segundos, disponible_en.strftime('%Y-%m-%d %H:%M:%S.%f')
        ))


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
except NameError:  # Python 3
    text_type = str

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


class GiscedataOmieSiomQueryExecution(osv.osv):

    _name = 'giscedata.omie.siom.query.execution'
    _description = 'Intentos de consulta SIOM (registro persistente independiente)'
    _order = 'fecha_intento desc, id desc'
    _rec_name = 'consulta'

    def _nueva_conexion(self, cr):
        """OpenERP 5: la base actual comparte el registro, no la transacción."""
        from pooler import get_db
        return get_db(cr.dbname).cursor()

    def _reservar(self, cr, uid, consulta, exigir_configuracion=False, margen_ms=500):
        """Transaccion corta: lock -> leer -> comprobar -> insertar -> commit.

        No conservar bloqueos de PostgreSQL durante las llamadas a OMIE.
        El momento de intento es el reloj PostgreSQL, no el del worker.
        """
        if isinstance(consulta, bool):
            raise ValueError('Codigo de consulta invalido')
        try:
            codigo = int(consulta)
        except (TypeError, ValueError, OverflowError):
            raise ValueError('Codigo de consulta invalido')
        if codigo <= 0 or codigo > 2147483647 or unicode_code_invalid(consulta, codigo):
            raise ValueError('Codigo de consulta invalido')
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
                limite = 0  # No equivale a una afirmacion de OMIE: configurada=False.
            dbcr.execute("SELECT clock_timestamp() AT TIME ZONE 'UTC'")
            ahora = dbcr.fetchone()[0]
            dbcr.execute('''
                SELECT fecha_intento
                  FROM giscedata_omie_siom_query_execution
                 WHERE consulta = %s
                 ORDER BY fecha_intento DESC, id DESC LIMIT 1
            ''', (codigo,))
            anterior = dbcr.fetchone()
            if anterior and configurada:
                instante_previo = anterior[0]
                # Margen operativo: reserva local anterior a la recepcion OMIE.
                permitido = instante_previo + timedelta(
                    milliseconds=limite + max(0, margen_ms) if limite > 0 else 0)
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
                  '8101 conocida' if configurada else 'Sin datos 8101; sin garantia de cadencia'))
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

    def _refrescar_8101(self, cr):
        """Transaccion independiente: la sincronizacion sobrevive a rollback ERP.

        La propia consulta 8101 pasa por ejecutar_consulta; nunca se refresca
        recursivamente a causa de un rechazo de la 8101.
        """
        dbcr = self._nueva_conexion(cr)
        try:
            model = self.pool.get('giscedata.omie.siom.minimum.time')
            model.actualizar_tiempos_minimos(dbcr, 1)
            dbcr.commit()
            return True
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

    def _consultar_datos_8100(self, cr, uid, context=None, client=None):
        """ENCOL 8100 via auditoría/cadencia; una única llamada, sin reintentos."""
        if uid != 1:
            raise ValueError('Solo el administrador puede consultar la 8100')
        if context is None:
            context = {}
        if client is None:
            from omie import ClientOMIE
            client = ClientOMIE()
        solicitud = {'CodConsulta': '8100', 'Parametros': {'_value_1': []}}
        respuesta = self.ejecutar_consulta(
            cr, uid, 8100,
            lambda: client.ServicioEjecucionConsultaEncolumnada(
                MensajeEjecucionConsulta=solicitud),
            context=context, reintentos=0)
        from zeep.helpers import serialize_object
        return serialize_object(respuesta)

    def diagnosticar_8100(self, cr, uid, context=None, client=None):
        """Inspección sin escritura local ni bloqueos preventivos."""
        datos = self._consultar_datos_8100(
            cr, uid, context=context, client=client)
        from giscedata_omie_api.giscedata_omie_siom_exclusion_diagnostic import diagnosticar_respuesta_8100
        return diagnosticar_respuesta_8100(datos)

    def ejecutar_consulta(self, cr, uid, codigo_consulta, llamada, context=None,
                          exigir_configuracion=False, reintentos=1,
                          espera_maxima_segundos=10.0, margen_ms=500,
                          codigos_frecuencia=None, dormir=None,
                          refrescar_8101=None):
        """Ejecuta ENCOL; solo reintenta rechazo explicito de frecuencia.

        No duerme si la espera supera el presupuesto. Nunca reintenta timeouts.
        El intento fallido queda registrado y reinicia el contador.
        `dormir` y `refrescar_8101` inyectables para pruebas unitarias.
        """
        if not callable(llamada):
            raise ValueError('llamada debe ser callable')
        if (reintentos < 0 or reintentos > 3 or espera_maxima_segundos < 0 or
                margen_ms < 0):
            raise ValueError('Politica de reintentos invalida')
        dormir = dormir or time.sleep
        contexto = context or {}
        if codigos_frecuencia is None:
            codigos_frecuencia = contexto.get('siom_codigos_rechazo_frecuencia', ())
        hubo_rechazo = False
        ultimo_detalle = ''
        total_dormido = 0.0
        for numero in range(reintentos + 1):
            try:
                intento = self._reservar(cr, uid, codigo_consulta,
                                         exigir_configuracion=exigir_configuracion,
                                         margen_ms=margen_ms)
            except TiempoMinimoNoCumplido as exc:
                if not hubo_rechazo:
                    raise
                # La excepcion ya incluye el margen de recepcion, no duplicarlo.
                restante = exc.espera_segundos + 0.01
                if (numero >= reintentos + 1 or
                        restante + total_dormido > espera_maxima_segundos):
                    raise RechazoFrecuenciaOMIE(codigo_consulta,
                                                '%s. Proximo intento UTC: %s' %
                                                (ultimo_detalle, exc.disponible_en))
                dormir(restante)
                total_dormido += restante
                intento = self._reservar(cr, uid, codigo_consulta,
                                         exigir_configuracion=exigir_configuracion,
                                         margen_ms=margen_ms)
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
            if str(codigo_consulta) == '8101':
                raise RechazoFrecuenciaOMIE(codigo_consulta,
                                            '%s (no refrescar 8101 recursivamente)' % ultimo_detalle)
            if numero >= reintentos:
                raise RechazoFrecuenciaOMIE(codigo_consulta, ultimo_detalle)
            refrescar = refrescar_8101 or self._refrescar_8101
            refrescar(cr)
            # Sin un tiempo conocido y positivo, no sabemos cuando reintentar.
            limite = self._limite_conocido(cr, int(codigo_consulta))
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
        ], 'Estado del intento', required=True, readonly=True),
        'detalle': fields.char('Diagnóstico local', size=256, readonly=True)
    }

def unicode_code_invalid(original, code):
    """Evitar truncar decimales al convertir, compatible con Python 2.7."""
    try:
        return str(original).strip() != str(code)
    except Exception:
        return True


GiscedataOmieSiomQueryExecution()
