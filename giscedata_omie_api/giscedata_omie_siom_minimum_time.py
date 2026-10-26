# -*- coding: utf-8 -*-
"""Persistencia y sincronizacion de la consulta 8101 (sin aplicar aun cuotas).

No modifica el comportamiento de ServicioAltaOfertasMD/MI ni introduce reintentos.
Una respuesta 8101 sin filas deja intactos los limites anteriores.
"""
from __future__ import absolute_import

from .giscedata_omie_siom_minimum_time_parser import parsear_8101
from datetime import datetime
from osv import osv, fields

def _utc_ahora():
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


class GiscedataOmieSiomMinimumTime(osv.osv):

    _name = 'giscedata.omie.siom.minimum.time'
    _description = 'Tiempos minimos de consulta SIOM publicados en 8101'
    _rec_name = 'titulo'
    _order = 'consulta asc'

    def consultar_tiempos_minimos(self, cursor, uid, client=None, context=None):
        """Consulta SOLO LECTURA a OMIE. Retorna filas normalizadas, no escribe BDD.

        Se permite inyectar client para pruebas offline. Zeep produce OrderedDict.
        """
        if context is None:
            context = {}

        from zeep.helpers import serialize_object

        if client is None:
            from omie import ClientOMIE
            client = ClientOMIE()

        solicitud = {'CodConsulta': '8101', 'Parametros': {'_value_1': []}}

        respuesta = client.ServicioEjecucionConsultaEncolumnada(MensajeEjecucionConsulta=solicitud)

        datos = serialize_object(respuesta)

        return parsear_8101(datos)

    def actualizar_tiempos_minimos(self, cursor, uid, client=None, context=None):
        """Descarga 8101 y actualiza en la transaccion OpenERP del llamador.

        Sin cursor.commit. Respuesta vacia: solo actualiza estado de sincronizacion.
        No borra ni desactiva filas previamente conocidas. Las restricciones
        no deben utilizarse automaticamente hasta comprobar su vigencia.
        Debe invocarse como usuario de servicio privilegiado o desde el wizard
        autorizado. Un ERP gestiona un unico agente y entorno OMIE.
        """
        if context is None:
            context = {}

        estado_obj = self.pool.get('giscedata.omie.siom.minimum.time.sync')

        if uid != 1:
            raise osv.except_osv('Permisos insuficientes',
                                 'La sincronizacion de SIOM requiere el usuario administrador.')

        filas = self.consultar_tiempos_minimos(cursor, uid, context=context, client=client)

        # Serializacion de actualizaciones en esta base de datos (PostgreSQL).
        cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))',
                      ('giscedata_omie_api.8101', 'all'))

        timestamp = _utc_ahora()

        estado_ids = estado_obj.search(cursor, uid, [], context=context)

        nuevas, modificadas = 0, 0

        if filas:
            for fila in filas:
                dominio = [('consulta', '=', fila['consulta'])]
                ids = self.search(cursor, uid, dominio, context=context)
                vals = fila.copy()
                vals.update({'fecha_actualizacion': timestamp})
                if ids:
                    self.write(cursor, uid, ids, vals, context=context)
                    modificadas += 1
                else:
                    self.create(cursor, uid, vals, context=context)
                    nuevas += 1

        vals_estado = {
            'estado': 'con_datos' if filas else 'vacia',
            'fecha_ultimo_intento': timestamp,
            'fecha_ultimo_exito': timestamp,
            'total_filas': len(filas),
        }

        if estado_ids:
            estado_obj.write(cursor, uid, estado_ids, vals_estado, context=context)
        else:
            estado_obj.create(cursor, uid, vals_estado, context=context)

        res = {'estado': vals_estado['estado'],
               'recibidas': len(filas),
               'nuevas': nuevas,
               'actualizadas': modificadas}

        return res

    _columns = {
        'consulta': fields.integer('Codigo de consulta', required=True, readonly=True, select=1),
        'titulo': fields.char('Titulo OMIE', size=256, required=True, readonly=True),
        'tiempo_agente_ms': fields.integer('Tiempo agente (ms)', required=True, readonly=True),
        'tiempo_certificado_ms': fields.integer('Tiempo certificado (ms)', required=True, readonly=True),
        'tipo_acceso': fields.char('Tipo de acceso', size=64, required=True, readonly=True),
        'fecha_actualizacion': fields.datetime('Ultima observacion UTC', readonly=True)
    }
    _sql_constraints = [
        ('omie_8101_codigo_uniq', 'unique(consulta)',
         'El codigo de consulta ya existe.'),
    ]


GiscedataOmieSiomMinimumTime()


class GiscedataOmieSiomMinimumTimeSync(osv.osv):

    _name = 'giscedata.omie.siom.minimum.time.sync'
    _description = 'Estado de la ultima sincronizacion SIOM 8101'
    _rec_name = 'estado'

    _columns = {
        'estado': fields.selection([('con_datos', 'Datos recibidos'), ('vacia', 'Respuesta vacia')],
                                  'Resultado de la ultima consulta', required=True,
                                   readonly=True),
        'fecha_ultimo_intento': fields.datetime('Ultimo intento UTC', readonly=True),
        'fecha_ultimo_exito': fields.datetime('Ultima respuesta valida UTC', readonly=True),
        'total_filas': fields.integer('Filas recibidas', readonly=True)
    }


GiscedataOmieSiomMinimumTimeSync()
