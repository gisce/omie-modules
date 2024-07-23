# -*- coding: utf-8 -*-
from __future__ import absolute_import
from osv import osv, fields
from omie import ClientOMIE
from datetime import datetime
from zeep import helpers

AREA_UNIDAD_SELECTION = [
    ('1', 'España'),
    ('2', 'Portugal'),
    ('3', 'Europa - Interconex Francia'),
    ('4', 'Andorra'),
    ('5', 'Africa - Interconex Marruecos'),
]

TIPO_UNIDAD_SELECTION = [
    ('UO', 'Unidad Ofertante'),
    ('UF', 'Unidad Física'),
    ('RE', 'Régimen Especial'),
    ('CP', 'Unidad de Contratación a Plazo'),
    ('UP', 'Unidad de programación'),
]

TIPO_MERCADO = [
    ('MD', 'Mercado Diario'),
    ('MI', 'Mercado Intradiario'),
]

SI_NO = [
    ('S', 'Si'),
    ('N', 'No'),
]

CLASE_OFERTA = [
    ('C', 'Compra'),
    ('V', 'Venta'),
]

UNIDAD_ENERGIA = [
    ('MWh', 'MWh'),
    ('kWh', 'kWh'),
]

UNIDAD_MONETARIA = [
    ('cEURO', 'cEURO'),
    ('EURO', 'EURO'),
]

UNIDAD_PRECIOS = [
    ('cEURO/kWh', 'cEURO/kWh'),
    ('cEURO/MWh', 'cEURO/MWh'),
    ('EURO/MWh', 'EURO/MWh'),
]

PERIODO_DIA = [
    ('1', '1'),
    ('2', '2'),
    ('3', '3'),
    ('4', '4'),
    ('5', '5'),
    ('6', '6'),
    ('7', '7'),
    ('8', '8'),
    ('9', '9'),
    ('10', '10'),
    ('11', '11'),
    ('12', '12'),
    ('13', '13'),
    ('14', '14'),
    ('15', '15'),
    ('16', '16'),
    ('17', '17'),
    ('18', '18'),
    ('19', '19'),
    ('20', '20'),
    ('21', '21'),
    ('22', '22'),
    ('23', '23'),
    ('24', '24'),
    ('25', '25'),
]

ORIGEN_OFERTA = []


class GiscedataOmieOferta(osv.osv):

    _name = 'giscedata.omie.oferta'
    _rec_name = 'id_oferta'
    _description = """Ofertas o Ejecuciones de Contratos Bilaterales Físicos."""

    def create(self, cursor, uid, vals, context=None):
        if context is None:
            context = {}
        bloque_obj = self.pool.get('giscedata.omie.oferta.bloque')

        oferta_id = super(osv.osv, self).create(cursor, uid, vals, context=context)
        write_vals = {
            'id_mensaje': oferta_id,
            'id_oferta': 'OF' + str(oferta_id)
        }
        self.write(cursor, uid, [oferta_id], write_vals, context=context)
        if not context.get('no_crear_bloques', True):
            bloque_ids = []
            for i in range(1, 26):
                create_vals = {
                    'num': i,
                    'div': 'N',
                    'ret': 'N',
                    'per': str(i),
                    'oferta_id': oferta_id,
                }
                bloque_id = bloque_obj.create(cursor, uid, create_vals, context=context)
                bloque_ids.append(bloque_id)
        return oferta_id

    def default_get(self, cursor, uid, fields, context=None):
        if context is None:
            context = {}

        res = {
            'state': 'no_enviada',
            'uni_energia': 'MWh',
            'uni_monetaria': 'EURO',
            'uni_precio': 'EURO/MWh',
            'grad_parada': 0.0,
            'grad_arranque': 0.0,
            'grad_bajada': 0.0,
            'grad_subida': 0.0,
            'ind_defecto': 'N',
            'area_unidad': '1',
            'tipo_unidad': 'UO',
            'tipo_mercado': 'MD',
        }
        return res

    def _get_origen_selection(self, cursor, uid, context=None):
        if context is None:
            context = {}
        return []

    _columns = {
        'id_mensaje': fields.char(
            "ID Mensaje", size=64,
            help="Código que identifica un elemento de forma única dentro del documento.", readonly=True
        ),
        'ver_mensaje': fields.integer(
            "Número Versión Mensaje", help="Número de versión de un mensaje", required=False
        ),
        'fecha_mensaje': fields.datetime(
            "Fecha Mensaje",
            help="Fecha y hora de generación de los datos para el mensaje (no de envío del mensaje en sí)",
            required=False, readonly=True
        ),
        'id_remitente': fields.char(
            "ID Remitente", size=16,
            help="Tipo que identifica un remitente, como código de agente, código EIC, etc", required=True
        ),
        # Oferta
        'id_oferta': fields.char(
            "ID Oferta", size=16,
            help="Identificativo de la oferta dentro del fichero, definido por quien "
                 "envía el fichero (único por mensaje)", readonly=True
        ),
        # Unidad
        # v
        'id_unidad': fields.char(
            "ID Unidad", size=16, help="Código de unidad ofertante o física.", required=True
        ),
        'cod_min_unidad': fields.char(
            "Código del Ministerio", size=50, help="Código del Ministerio", required=False
        ),
        'area_unidad': fields.selection(
            AREA_UNIDAD_SELECTION, "Área de Unidad",
            help="1: España, 2: Portugal, 3: Europa - Interconex Francia, 4: Andorra, 5: Africa - Interconex Marruecos",
            required=True
        ),
        'tipo_unidad': fields.selection(
            TIPO_UNIDAD_SELECTION, "Tipo de Unidad",
            help="UO: Unidad Ofertante, UF: Unidad Física, RE: Régimen Especial, "
                 "CP: Unidad de Contratación a Plazo, UP: Unidad de programación",
            required=True
        ),
        # Validez
        'tipo_mercado': fields.selection(
            TIPO_MERCADO, "Tipo de Mercado", help="MD: Mercado Diario, MI: Mercado Intradiario", required=True
        ),
        # Sesion
        'fecha_sesion': fields.date(
            "Fecha Sesión", help="Fecha del día que queremos ofertar", required=True
        ),
        'ind_defecto': fields.selection(
            SI_NO, "Oferta por Defecto",
            help="Indica si la Oferta es por Defecto o Normal. "
                 "('S' o 'Y' indican que la oferta es por defecto. 'N' indica que es normal",
            required=True
        ),
        #'tipo_casacion' SIEMPRE VALE 1
        'clase_oferta': fields.selection(CLASE_OFERTA, "Clase de Oferta", help="C: Compra, V: Venta", required=True),
        # CondTec
        #Gradiente
        'grad_parada': fields.float("Gradiente de Parada", digits=(6, 1), help="Gradiente de Parada"),
        'grad_arranque': fields.float("Gradiente de Arranque", digits=(6, 1), help="Gradiente de Arranque"),
        'grad_bajada': fields.float("Gradiente de Bajada", digits=(6, 1), help="Gradiente de Bajada"),
        'grad_subida': fields.float("Gradiente de Subida", digits=(6, 1), help="Gradiente de Subida"),
        'uni_energia': fields.selection(UNIDAD_ENERGIA, "Unidad de Energía", help="MWh/kWh"),
        'uni_monetaria': fields.selection(UNIDAD_MONETARIA, "Unidad Monetaria", help="cEURO/EURO"),
        'uni_precio': fields.selection(
            UNIDAD_PRECIOS, 'Unidad de Precio', help="cEURO/kWh, cEURO/MWh, EURO/MWh",
        ),
        #'uni_gradiente' SIEMPRE VALE 'MW/Min'
        'comentario_oferta': fields.char(
            "Comentario de la Oferta", size=30, help="Comentario de la oferta", required=False
        ),
        'state': fields.selection(
            [('no_enviada', 'No Enviada'), ('enviada', 'Enviada')], 'Estado Envio',
            help="Enviada/No Enviada", readonly=True
        ),
        # RESPUESTA
        'id_mensaje_respuesta': fields.char(
            'Mensaje Petición', help="Identificación del mensaje (libre para el creador del mensaje)", size=64,
            readonly=True),
        'fecha_mensaje_respuesta': fields.char(
            "Fecha Petición", size=32,
            help="Fecha y hora de generación de los datos para el mensaje (no de envío del mensaje en sí)",
            readonly=True
        ),
        'id_remitente_respuesta': fields.char(
            "ID Remitente", size=16,
            help="Código del Agente que envía la respuesta (OMEL)", readonly=True
        ),
        'id_remitente_origen': fields.char(
            'ID Remitente Origen', size=16,
            help="Código del Agente que envió el mensaje", readonly=True
        ),
        # Respuesta
        'codigo_respuesta': fields.char(
            'Código Respuesta', size=16, help="Código de la respuesta", readonly=True
        ),
        'texto_respuesta': fields.text(
            'Texto Respuesta', help="Textos descriptivos de la respuesta", readonly=True
        ),
        # ResumenOfertas
        'num_ofertas_procesadas': fields.char(
            'Núm. Ofertas Procesadas', size=16, help="Número total de ofertas procesadas", readonly=True
        ),
        'num_ofertas_correctas': fields.char(
            'Núm. Ofertas Correctas', size=16, help="Número total de ofertas correctas", readonly=True
        ),
        'origen': fields.reference('Origen', selection=_get_origen_selection, size=128),
    }

    defaults = {
        'uni_energia': lambda *a: 'MWh',
        'uni_monetaria': lambda *a: 'EURO',
        'uni_precio': lambda *a: 'EURO/MWh',
        'state': lambda *a: 'no_enviada',
        'ind_defecto': lambda *a: 'N',
        'grad_parada': lambda *a: 0.0,
        'grad_arranque': lambda *a: 0.0,
        'grad_bajada': lambda *a: 0.0,
        'grad_subida': lambda *a: 0.0,
        'default_values_set': lambda *a: True,
    }


GiscedataOmieOferta()


class GiscedataOmieOfertaBloque(osv.osv):

    _name = 'giscedata.omie.oferta.bloque'
    _rec_name = 'oferta_id'
    _description = """Representa una oferta por hora de un dia concreto."""

    _columns = {
        'num': fields.integer("Número de Bloque"),
        'div': fields.selection(SI_NO, "Es divisible", required=True),
        'ret': fields.selection(SI_NO, "Es retirable", required=True),
        'per': fields.selection(
            PERIODO_DIA, "Periodo horario del día",
            help="Seleccionar el periodo del día para el que quiere hacer la oferta", required=True),
        'ctn': fields.float("Energía de la Oferta", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'prc': fields.float("Precio de la Oferta", digits=(8, 3)),
        'oferta_id': fields.many2one('giscedata.omie.oferta', 'ID Oferta', ondelete='cascade'),
    }


GiscedataOmieOfertaBloque()


class GiscedataOmieOferta(osv.osv):

    _name = 'giscedata.omie.oferta'
    _inherit = 'giscedata.omie.oferta'

    def copy_data(self, cursor, uid, id, default=None, context=None):
        if context is None:
            context = {}
        if default is None:
            default = {}

        default['bloque_ids'] = [(5, 0, 0)]
        default['state'] = 'no_enviada'
        default['id_mensaje_respuesta'] = False
        default['fecha_mensaje_respuesta'] = False
        default['id_remitente_respuesta'] = False
        default['id_remitente_origen'] = False
        default['codigo_respuesta'] = False
        default['texto_respuesta'] = False
        default['num_ofertas_procesadas'] = False
        default['num_ofertas_correctas'] = False

        return super(GiscedataOmieOferta, self).copy_data(cursor, uid, id, default, context)

    def mensaje_oferta_md_dicc(self, cursor, uid, oferta_id, context=None):
        if context is None:
            context = {}

        oferta_obj = self.pool.get('giscedata.omie.oferta')
        bloque_obj = self.pool.get('giscedata.omie.oferta.bloque')

        oferta_vals = oferta_obj.read(cursor, uid, oferta_id, [], context=context)
        oferta_vals_filtered = self.delete_null_fields(cursor, uid, oferta_vals, context=context)

        list_bloques = []
        i = 1
        for bloque_id in oferta_vals_filtered.get('bloque_ids', []):
            bloque_vals = bloque_obj.read(cursor, uid, bloque_id, [], context=context)
            dicc_bloque = {
                "num": i,
                "div": bloque_vals.get('div'),
                "ret": bloque_vals.get('ret'),
                "Per": bloque_vals.get('per'),
                "Ctn": bloque_vals.get('ctn', 0.0),
                "Prc": bloque_vals.get('prc', 0.0)
            }
            list_bloques.append(dicc_bloque)
            i += 1

        oferta_dicc = {
            'IdMensaje': oferta_vals_filtered.get('id_mensaje'),
            'VerMensaje': oferta_vals_filtered.get('ver_mensaje', 1),
            'FechaMensaje': datetime.today().strftime('%Y-%m-%dT%H:%M:%S'),
            'IdRemitente': oferta_vals_filtered.get('id_remitente'),
            'Oferta': {
                'IdOferta': oferta_vals_filtered.get('id_oferta'),
                'IdUnidad': {
                    "v": oferta_vals_filtered.get('id_unidad'),
                    "codMin": oferta_vals_filtered.get('cod_min_unidad', ""),
                    "area": oferta_vals_filtered.get('area_unidad'),
                    "tipo": oferta_vals_filtered.get('tipo_unidad'),
                },
                'Validez': {
                    'TipoMercado': oferta_vals_filtered.get('tipo_mercado'),
                    'Sesion': {
                        'fecha': oferta_vals_filtered.get('fecha_sesion')[:10],
                    },
                    'IndDefecto': oferta_vals_filtered.get('ind_defecto'),
                    'TipoCasacion': 1,  # Siempre vale 1
                },
                'ClaseOferta': oferta_vals_filtered.get('clase_oferta'),
                'UniEnergia': oferta_vals_filtered.get('uni_energia'),
                'UniMonetaria': oferta_vals_filtered.get('uni_monetaria'),
                'UniPrecio': oferta_vals_filtered.get('uni_precio'),
                'UniGradiente': 'MW/min',
                'Comentario': oferta_vals_filtered.get('comentario_oferta', ""),
                'Detalle': {
                    'Blq': list_bloques
                }
            },
        }

        return oferta_dicc

    def respuesta_oferta_dicc(self, cursor, uid, res_oferta_dicc, context=None):
        if context is None:
            context = {}

        texto_respuesta = ''
        list_texto_respuesta = res_oferta_dicc.get('RespuestaSerie', [])
        if list_texto_respuesta:
            list_texto_respuesta = list_texto_respuesta[0].get('Respuesta', [])
            if list_texto_respuesta:
                list_texto_respuesta = list_texto_respuesta[0].get('TextoRespuesta', [])
        for aux in list_texto_respuesta:
            texto_respuesta += aux + '\n'

        codigo_respuesta = res_oferta_dicc.get('Respuesta', [])
        if codigo_respuesta:
            list_texto_respuesta = codigo_respuesta[0].get('TextoRespuesta', [])
            for aux in list_texto_respuesta:
                texto_respuesta += aux + '\n'
            codigo_respuesta = codigo_respuesta[0].get('CodigoRespuesta', {}).get('v', '')
        else:
            codigo_respuesta = ''

        respuesta_dicc = {
            'id_mensaje_respuesta': res_oferta_dicc.get('IdMensaje', {}).get('v', False),
            'fecha_mensaje_respuesta': res_oferta_dicc.get('FechaMensaje', {}).get('v', False),
            'id_remitente_respuesta': res_oferta_dicc.get('IdRemitente', {}).get('v', False),
            'id_remitente_origen': res_oferta_dicc.get('IdRemitenteOrigen', {}).get('v', False),
            'codigo_respuesta': codigo_respuesta,
            'texto_respuesta': texto_respuesta,
            'num_ofertas_procesadas': str(res_oferta_dicc.get('ResumenOfertas', {}).get('NumOfertasProcesadas', {}).get('v', 0)),
            'num_ofertas_correctas': str(res_oferta_dicc.get('ResumenOfertas', {}).get('NumOfertasCorrectas', {}).get('v', 0)),
        }
        return respuesta_dicc


    def crear_respuesta_oferta(self, cursor, uid, oferta_id, respuesta_oferta_dicc, context=None):
        if context is None:
            context = {}

        respuesta_dicc = self.respuesta_oferta_dicc(cursor, uid, respuesta_oferta_dicc, context=context)
        return respuesta_dicc

    def delete_null_fields(self, cursor, uid, oferta_dicc, context=None):
        if context is None:
            context = {}
        res = {x: y for x, y in oferta_dicc.items() if y}
        return res

    def update_origen(self, cursor, uid, oferta_id, context=None):
        if context is None:
            context = {}

        return True

    def enviar_oferta(self, cursor, uid, ids, context=None):
        if context is None:
            context = {}

        oferta_obj = self.pool.get('giscedata.omie.oferta')

        for oferta_id in ids:
            oferta_dicc = oferta_obj.mensaje_oferta_md_dicc(cursor, uid, oferta_id, context=context)
            client = ClientOMIE()
            try:
                res_oferta_zeep = client.ServicioAltaOfertasMD(MensajeOfertasMD=oferta_dicc)
                res_oferta_dicc = helpers.serialize_object(res_oferta_zeep)
                respuesta_dicc = self.crear_respuesta_oferta(cursor, uid, oferta_id, res_oferta_dicc, context=context)
                # Añadir fecha_mensaje y cambiar estado en la oferta enviada
                write_vals = {
                    'fecha_mensaje': datetime.today().strftime('%Y-%m-%d'),
                    'state': 'enviada',
                }
                write_vals.update(respuesta_dicc)
                oferta_obj.write(cursor, uid, [oferta_id], write_vals, context=context)
                self.update_origen(cursor, uid, oferta_id, context=context)
            except Exception as e:
                raise osv.except_osv('Error:', e)


    _columns = {
        # Blq
        'bloque_ids': fields.one2many(
            'giscedata.omie.oferta.bloque', 'oferta_id', "Bloques de Oferta", ondelete='cascade'
        ),
    }


GiscedataOmieOferta()
