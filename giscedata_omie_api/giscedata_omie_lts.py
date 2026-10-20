# -*- coding: utf-8 -*-
"""Modelos de seguimiento del mercado continuo LTS (etapa 11A).

Solo representacion de datos. NO se emiten ofertas, no hay jobs RQ,
ni comunicacion directa con LTSWorker u OMIE desde OpenERP.

Los campos monetarios/cantidades se conservan como texto decimal para
no introducir redondeos binarios al importar JSON. Los timestamps de
OMIE se preservan como texto ISO8601 para conservar su offset.
"""
from __future__ import absolute_import

from osv import osv, fields


ORDER_SIDE = [('C', 'Compra'), ('V', 'Venta')]

SYNC_STATUS = [
    ('unknown', 'Sin verificar'),
    ('synchronized', 'Sincronizada'),
    ('stale', 'Desactualizada'),
]

OPERATION_TYPE = [
    ('NewOrder', 'Alta'),
    ('ModifyOrder', 'Modificacion'),
    ('CancelOrder', 'Cancelacion'),
    ('ActivateOrder', 'Activacion'),
]

# Estado del seguimiento interno, NO equivalente al estado de OMIE.
OPERATION_STATUS = [
    ('requested', 'Solicitada en ERP (no enviada)'),
    ('prepared', 'Preparada en diario seguro'),
    ('acked_unconfirmed', 'ACK recibido, sin confirmar ejecucion'),
    ('uncertain', 'Resultado incierto'),
    ('resolved_manually', 'Resuelta con evidencia'),
]


class GiscedataOmieLTSOrder(osv.osv):
    _name = 'giscedata.omie.lts.order'
    _description = 'Orden del mercado continuo OMIE LTS (seguimiento)'
    _rec_name = 'record_key'
    _order = 'id desc'

    _columns = {
        'record_key': fields.char('Clave interna estable', size=200, required=True,
                                  select=1, readonly=True,
                                  help='Identificador de sincronizacion, no necesariamente un orderID de OMIE.'),
        'app_id': fields.char('AppID', size=128, required=True, select=1, readonly=True),
        'agent_id': fields.char('Agente OMIE', size=64, required=True, select=1, readonly=True),
        'zone': fields.char('Zona', size=32, required=True, select=1, readonly=True),
        'contract_id': fields.char('Contrato OMIE', size=32, select=1, readonly=True),
        'omie_order_id': fields.char('OrderID OMIE', size=32, select=1, readonly=True),
        'omie_order_id_ini': fields.char('OrderID inicial', size=32, readonly=True),
        'omie_order_id_orig': fields.char('OrderID anterior', size=32, readonly=True),
        'client_order_id': fields.char('ClientOrderID', size=200, select=1, readonly=True),
        'unit': fields.char('Unidad', size=64, readonly=True),
        'side': fields.selection(ORDER_SIDE, 'Compra / Venta', readonly=True),
        'omie_status': fields.char('Estado OMIE', size=32, readonly=True,
                                   help='Valor original status de OrderInfo (ACTI, IACT, HIBE...).'),
        'omie_action': fields.char('Ultima accion OMIE', size=32, readonly=True),
        'price': fields.char('Precio (decimal)', size=64, readonly=True),
        'initial_qty': fields.char('Cantidad inicial (decimal)', size=64, readonly=True),
        'remaining_qty': fields.char('Cantidad restante (decimal)', size=64, readonly=True),
        'omie_timestamp': fields.char('Fecha/hora OMIE (ISO8601)', size=64, readonly=True),
        'sync_status': fields.selection(SYNC_STATUS, 'Estado de sincronizacion',
                                        required=True, readonly=True),
        'last_seen_at': fields.datetime('Ultima observacion UTC', readonly=True),
        'raw_message': fields.text('Ultimo mensaje OMIE (JSON)', readonly=True),
        'operation_ids': fields.one2many('giscedata.omie.lts.operation', 'order_id',
                                         'Operaciones asociadas', readonly=True),
    }
    _defaults = {'sync_status': lambda *a: 'unknown'}
    _sql_constraints = [
        ('lts_order_key_uniq', 'unique(app_id,agent_id,zone,record_key)',
         'La clave de orden LTS ya existe para esta identidad y zona.'),
    ]


GiscedataOmieLTSOrder()


class GiscedataOmieLTSOperation(osv.osv):
    _name = 'giscedata.omie.lts.operation'
    _description = 'Intento de operacion Management de OMIE LTS'
    _rec_name = 'operation_id'
    _order = 'id desc'

    _columns = {
        'operation_id': fields.char('ID de intento', size=200, required=True,
                                    select=1, readonly=True,
                                    help='Identificador inmutable vinculado al diario SQLite.'),
        'app_id': fields.char('AppID', size=128, required=True, select=1, readonly=True),
        'agent_id': fields.char('Agente OMIE', size=64, required=True, select=1, readonly=True),
        'zone': fields.char('Zona', size=32, select=1, readonly=True),
        'order_id': fields.many2one('giscedata.omie.lts.order', 'Orden relacionada',
                                    ondelete='set null', readonly=True),
        'operation_type': fields.selection(OPERATION_TYPE, 'Tipo de solicitud',
                                           required=True, readonly=True),
        'state': fields.selection(OPERATION_STATUS, 'Estado local', required=True,
                                  readonly=True),
        'rq_job_id': fields.char('Trabajo RQ', size=128, select=1, readonly=True),
        'requested_by': fields.many2one('res.users', 'Usuario solicitante',
                                        ondelete='set null', readonly=True),
        'client_message_id': fields.char('ClientMessageId', size=200, readonly=True),
        'request_payload': fields.text('Peticion original (JSON sin credenciales)',
                                       readonly=True),
        'ack_payload': fields.text('ACK (JSON)', readonly=True),
        'evidence': fields.text('Evidencias de reconciliacion (JSON)', readonly=True),
        'resolution_note': fields.text('Justificacion de resolucion', readonly=True),
        'created_utc': fields.char('Fecha creacion UTC (ISO8601)', size=64,
                                   readonly=True),
        'updated_utc': fields.char('Fecha actualizacion UTC (ISO8601)', size=64,
                                   readonly=True),
    }
    _defaults = {'state': lambda *a: 'requested'}
    _sql_constraints = [
        ('lts_operation_id_uniq', 'unique(app_id,agent_id,operation_id)',
         'Ya existe un intento con este identificador para esta identidad.'),
    ]


GiscedataOmieLTSOperation()


class GiscedataOmieLTSTrade(osv.osv):
    _name = 'giscedata.omie.lts.trade'
    _description = 'Transaccion del mercado continuo OMIE LTS'
    _rec_name = 'omie_trade_id'
    _order = 'id desc'

    _columns = {
        'omie_trade_id': fields.char('TradeID OMIE', size=32, required=True,
                                     select=1, readonly=True),
        'app_id': fields.char('AppID', size=128, required=True, select=1, readonly=True),
        'agent_id': fields.char('Agente OMIE', size=64, required=True, select=1, readonly=True),
        'zone': fields.char('Zona (si se conoce)', size=32, readonly=True),
        'contract_id': fields.char('Contrato OMIE', size=32, select=1, readonly=True),
        'buy_order_id': fields.char('OrderID compra', size=32, readonly=True),
        'sell_order_id': fields.char('OrderID venta', size=32, readonly=True),
        'qty': fields.char('Cantidad (decimal)', size=64, readonly=True),
        'price': fields.char('Precio (decimal)', size=64, readonly=True),
        'omie_timestamp': fields.char('Fecha/hora OMIE (ISO8601)', size=64, readonly=True),
        'last_seen_at': fields.datetime('Ultima observacion UTC', readonly=True),
        'raw_message': fields.text('Ultimo mensaje OMIE (JSON)', readonly=True),
    }
    _sql_constraints = [
        ('lts_trade_id_uniq', 'unique(app_id,agent_id,omie_trade_id)',
         'Ya existe esta transaccion LTS para la identidad indicada.'),
    ]


GiscedataOmieLTSTrade()
