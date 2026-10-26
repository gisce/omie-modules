# -*- coding: utf-8 -*-
"""Persistencia y sincronizacion de la consulta 8101 (sin aplicar aun cuotas).

No modifica el comportamiento de ServicioAltaOfertasMD/MI ni introduce reintentos.
Una respuesta 8101 sin filas deja intactos los limites anteriores.
"""
from __future__ import absolute_import

from .giscedata_omie_siom_minimum_time_parser import parsear_8101
from datetime import datetime
from osv import osv, fields

try:
    basestring
except NameError:
    basestring = str


def _utc_ahora():
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


class GiscedataOmieSiomMinimumTime(osv.osv):

    _name = 'giscedata.omie.siom.minimum.time'
    _description = 'Tiempos minimos de consulta SIOM publicados en 8101'
    _rec_name = 'titulo'
    _order = 'consulta asc'

    _columns = {
        'scope': fields.char('Ambito de consulta / certificado',
                             size=128, required=True, select=1, readonly=True,
                             help='Clave de configuracion local. No contiene certificados ni secretos.'),
        'consulta': fields.integer('Codigo de consulta', required=True, readonly=True, select=1),
        'titulo': fields.char('Titulo OMIE', size=256, required=True, readonly=True),
        'tiempo_agente_ms': fields.integer('Tiempo agente (ms)', required=True, readonly=True),
        'tiempo_certificado_ms': fields.integer('Tiempo certificado (ms)', required=True, readonly=True),
        'tipo_acceso': fields.char('Tipo de acceso', size=64, required=True, readonly=True),
        'fecha_actualizacion': fields.datetime('Ultima observacion UTC', readonly=True)
    }

    _sql_constraints = [
        ('omie_8101_scope_codigo_uniq', 'unique(scope, consulta)',
         'El codigo de consulta ya existe para este ambito.'),
    ]

    def consultar_tiempos_minimos(self, cursor, uid, context=None, client=None):
        """Consulta SOLO LECTURA a OMIE. Retorna filas normalizadas, no escribe BDD.

        Se permite inyectar client para pruebas offline. Zeep produce OrderedDict.
        """
        from zeep.helpers import serialize_object
        if client is None:
            from omie import ClientOMIE
            client = ClientOMIE()
        solicitud = {'CodConsulta': '8101', 'Parametros': {'_value_1': []}}
        respuesta = client.ServicioEjecucionConsultaEncolumnada(MensajeEjecucionConsulta=solicitud)
        datos = serialize_object(respuesta)
        return parsear_8101(datos)

    def actualizar_tiempos_minimos(self, cursor, uid, context=None, client=None, scope='default'):
        """Descarga 8101 y actualiza en la transaccion OpenERP del llamador.

        Sin cursor.commit. Respuesta vacia: solo actualiza estado de sincronizacion.
        No borra ni desactiva filas previamente conocidas. Las restricciones
        no deben utilizarse automaticamente hasta comprobar su vigencia.
        Debe invocarse como usuario de servicio privilegiado; no hay boton UI.
        """
        if uid != 1:
            raise osv.except_osv('Permisos insuficientes',
                                 'La sincronizacion de SIOM requiere el usuario administrador.')
        if not isinstance(scope, basestring) or not scope or len(scope) > 128:
            raise ValueError('scope invalido (maximo 128 caracteres)')
        filas = self.consultar_tiempos_minimos(cursor, uid, context=context, client=client)
        # Serializacion entre procesos sobre el mismo ambito (PostgreSQL).
        cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))',
                      ('giscedata_omie_api.8101', scope))
        timestamp = _utc_ahora()
        estado_obj = self.pool.get('giscedata.omie.siom.minimum.time.sync')
        estado_ids = estado_obj.search(cursor, uid, [('scope', '=', scope)], context=context)
        nuevas, modificadas = 0, 0
        if filas:
            for fila in filas:
                dominio = [('scope', '=', scope), ('consulta', '=', fila['consulta'])]
                ids = self.search(cursor, uid, dominio, context=context)
                vals = fila.copy()
                vals.update({'scope': scope, 'fecha_actualizacion': timestamp})
                if ids:
                    self.write(cursor, uid, ids, vals, context=context)
                    modificadas += 1
                else:
                    self.create(cursor, uid, vals, context=context)
                    nuevas += 1
        vals_estado = {
            'scope': scope,
            'estado': 'con_datos' if filas else 'vacia',
            'fecha_ultimo_intento': timestamp,
            'fecha_ultimo_exito': timestamp,
            'total_filas': len(filas),
        }
        if estado_ids:
            estado_obj.write(cursor, uid, estado_ids, vals_estado, context=context)
        else:
            estado_obj.create(cursor, uid, vals_estado, context=context)
        return {'estado': vals_estado['estado'], 'recibidas': len(filas),
                'nuevas': nuevas, 'actualizadas': modificadas, 'scope': scope}


GiscedataOmieSiomMinimumTime()


class GiscedataOmieSiomMinimumTimeSync(osv.osv):
    _name = 'giscedata.omie.siom.minimum.time.sync'
    _description = 'Estado de la ultima sincronizacion SIOM 8101'
    _rec_name = 'scope'

    _columns = {
        'scope': fields.char('Ambito de consulta / certificado',
                             size=128, required=True, readonly=True, select=1),
        'estado': fields.selection([('con_datos', 'Datos recibidos'), ('vacia', 'Respuesta vacia')],
                                  'Resultado de la ultima consulta',
                                   required=True, readonly=True),
        'fecha_ultimo_intento': fields.datetime('Ultimo intento UTC', readonly=True),
        'fecha_ultimo_exito': fields.datetime('Ultima respuesta valida UTC', readonly=True),
        'total_filas': fields.integer('Filas recibidas', readonly=True),
    }
    _sql_constraints = [
        ('omie_8101_scope_sync_uniq', 'unique(scope)',
         'Ya existe un registro de sincronizacion para este ambito.'),
    ]


GiscedataOmieSiomMinimumTimeSync()
