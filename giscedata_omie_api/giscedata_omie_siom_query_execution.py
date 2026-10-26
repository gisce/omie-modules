# -*- coding: utf-8 -*-
"""Control sincrono SIOM ENCOL, con registro durable en PostgreSQL.

La reserva se confirma ANTES de la llamada SOAP en otra transaccion.
No altera la transaccion de negocio que pasa OpenERP y nunca reintenta.
Una respuesta recibida NO implica necesariamente éxito funcional OMIE.

Se limita a consultas ENCOL; los envios MD/IDA requieren su propia politica.
"""
from __future__ import absolute_import

from datetime import timedelta
from osv import osv, fields


class TiempoMinimoNoCumplido(Exception):
    """No se ha llamado a OMIE: aun no ha transcurrido el tiempo minimo."""

    def __init__(self, consulta, disponible_en, espera_segundos):
        self.consulta = consulta
        self.disponible_en = disponible_en
        self.espera_segundos = espera_segundos
        Exception.__init__(self, 'Consulta %s: esperar %.3f segundos (hasta %s UTC)' % (
            consulta, espera_segundos, disponible_en.strftime('%Y-%m-%d %H:%M:%S.%f')
        ))


class SinConfiguracionTiempoMinimo(Exception):
    """No hay limite 8101 conocido para la consulta (modo estricto)."""


class GiscedataOmieSiomQueryExecution(osv.osv):

    _name = 'giscedata.omie.siom.query.execution'
    _description = 'Intentos de consulta SIOM (registro persistente independiente)'
    _order = 'fecha_intento desc, id desc'
    _rec_name = 'consulta'

    def _nueva_conexion(self, cr):
        """OpenERP 5: la base actual comparte el registro, no la transaccion."""
        from pooler import get_db
        return get_db(cr.dbname).cursor()

    def _reservar(self, cr, uid, consulta, exigir_configuracion=False):
        """Transaccion corta: lock -> leer -> comprobar -> insertar -> commit.

        No conservar bloqueos de PostgreSQL durante las llamadas a OMIE.
        El momento de intento es el reloj PostgreSQL, no el del worker.
        """
        if isinstance(consulta, bool):
            raise ValueError('Código de consulta invalido')

        try:
            codigo = int(consulta)
        except (TypeError, ValueError, OverflowError):
            raise ValueError('Código de consulta invalido')

        if codigo <= 0 or codigo > 2147483647 or unicode_code_invalid(consulta, codigo):
            raise ValueError('Código de consulta invalido')

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
                permitido = instante_previo + timedelta(milliseconds=limite)
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
                         SET estado = %s, detalle = %s, fecha_fin = clock_timestamp() AT TIME ZONE 'UTC'
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

    def ejecutar_consulta(self, cr, uid, codigo_consulta, llamada, context=None,
                          exigir_configuracion=False):
        """Envuelve una llamada SOAP ENCOL sin cambiar su resultado.

        `llamada` debe ser un callable SIN efectos previos de red; se ejecuta
        solamente tras persistir la reserva. No se ejecuta si hay bloqueo.
        Ante fallo de red queda 'incierta', sin reintento automatico.
        """
        if not callable(llamada):
            raise ValueError('llamada debe ser callable')
        intento = self._reservar(cr, uid, codigo_consulta,
                                 exigir_configuracion=exigir_configuracion)
        try:
            respuesta = llamada()
        except BaseException as exc:
            # No divulgar en BDD cabeceras, contraseñas o contenido SOAP.
            try:
                self._finalizar(cr, intento, 'incierta',
                               'Excepcion local o transporte: %s' % type(exc).__name__)
            except Exception:
                # El registro sigue como 'reservada': no perder la causa original.
                pass
            raise
        self._finalizar(cr, intento, 'respondida', 'SOAP respondido; verificar Respuesta OMIE')
        return respuesta

    _columns = {
        'consulta': fields.integer('Código de consulta', required=True, readonly=True, select=1),
        'usuario_id': fields.many2one('res.users', 'Usuario solicitante', readonly=True),
        'fecha_intento': fields.datetime('Reserva / intento UTC', required=True, readonly=True),
        'fecha_fin': fields.datetime('Fin local UTC', readonly=True),
        'limite_ms': fields.integer('Límite aplicado (ms)', readonly=True),
        'configurada': fields.boolean('Existe configuración 8101', readonly=True),
        'estado': fields.selection([
            ('reservada', 'Reservada; resultado pendiente'),
            ('respondida', 'Respuesta SOAP recibida (no implica éxito)'),
            ('incierta', 'Fallo local/transport; resultado incierto'),
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
