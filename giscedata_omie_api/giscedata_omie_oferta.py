# -*- coding: utf-8 -*-
from __future__ import absolute_import
from osv import osv, fields
from omie import ClientOMIE
from datetime import datetime

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

class GiscedataOmieOferta(osv.osv):

    _name = 'giscedata.omie.oferta'
    _rec_name = 'id_oferta'
    _description = """Representa Ofertas o Ejecuciones de Contratos Bilaterales Físicos."""

    _columns = {
        'id_mensaje': fields.char(
            "ID Mensaje", size=64,
            help="Código que identifica un elemento de forma única dentro del documento.", required=True
        ),
        'ver_mensaje': fields.integer(
            "Número Versión Mensaje", help="Número de versión de un mensaje", required=False
        ),
        'fecha_mensaje': fields.datetime(
            "Fecha Mensaje",
            help="Fecha y hora de generación de los datos para el mensaje (no de envío del mensaje en sí)",
            required=False
        ),
        'id_remitente': fields.char(
            "ID Remitente", size=16,
            help="Tipo que identifica un remitente, como código de agente, código EIC, etc", required=True
        ),
        # Oferta
        'id_oferta': fields.char(
            "ID Oferta", size=16,
            help="Identificativo de la oferta dentro del fichero, definido por quien "
                 "envía el fichero (único por mensaje)", required=True
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
        # CondEco
        'termino_fijo': fields.integer("Término Fijo", size=9, help="Término fijo"),
        'termino_variable': fields.float("Término Variable", digits=(12, 3), help="Término variable"),
        # CondTec
        #Gradiente
        'grad_parada': fields.float("Gradiente de Parada", digits=(6, 1), help="Gradiente de Parada", required=True),
        'grad_arranque': fields.float("Gradiente de Arranque", digits=(6, 1), help="Gradiente de Arranque", required=True),
        'grad_bajada': fields.float("Gradiente de Bajada", digits=(6, 1), help="Gradiente de Bajada", required=True),
        'grad_subida': fields.float("Gradiente de Subida", digits=(6, 1), help="Gradiente de Subida", required=True),
        'uni_energia': fields.selection(UNIDAD_ENERGIA, "Unidad de Energía", help="MWh/kWh", required=True),
        'uni_monetaria': fields.selection(UNIDAD_MONETARIA, "Unidad Monetaria", help="cEURO/EURO", required=True),
        'uni_precio': fields.selection(
            UNIDAD_PRECIOS, 'Unidad de Precio', help="cEURO/kWh, cEURO/MWh, EURO/MWh", required=True
        ),
        #'uni_gradiente' SIEMPRE VALE 'MW/Min'
        'comentario_oferta': fields.char(
            "Comentario de la Oferta", size=30, help="Comentario de la oferta", required=False
        ),
    }

    defaults = {
        'uni_energia': lambda *a: 'MWh',
        'uni_monetaria': lambda *a: 'EURO',
    }


GiscedataOmieOferta()


class GiscedataOmieOfertaConsulta(osv.osv):

    _name = 'giscedata.omie.oferta.consulta'
    _rec_name = 'codigo'
    _description = """Representa una consulta de oferta con código y versión (opcional)."""

    _columns = {
        'codigo': fields.integer("Código", size=6, required=True),
        'version': fields.integer("Versión", size=6, required=False),
    }


GiscedataOmieOfertaConsulta()


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
        'ctn': fields.float("Energía de la Oferta", digits=(8, 3), help="Energía de la oferta, sin signo",
                            required=True),
        'prc': fields.float("Precio de la Oferta", digits=(8, 3), required=True),
        'oferta_id': fields.many2one('giscedata.omie.oferta', 'ID Oferta'),
    }


GiscedataOmieOfertaBloque()

class GiscedataOmieOfertaPeticion(osv.osv):

    _name = 'giscedata.omie.oferta.peticion'
    _rec_name = 'oferta_id'
    _description = """Histórico de peticiones y respectivas respuestas de OMIE"""

    _columns = {
        'id_mensaje': fields.text(
            'Mensaje Petición', help="Identificación del mensaje (libre para el creador del mensaje)",
            required=True, readonly=True),
        'fecha_mensaje': fields.datetime(
            "Fecha Petición",
            help="Fecha y hora de generación de los datos para el mensaje (no de envío del mensaje en sí)",
            required=True, readonly=True
        ),
        'id_remitente': fields.char(
            "ID Remitente", size=16,
            help="Código del Agente que envía la respuesta (OMEL)", required=True, readonly=True
        ),
        'id_mensaje_origen': fields.text(
            'Mensaje Origen Petición',
            help="Identificación del mensaje que se envió (libre para el creador del mensaje)",
            required=True, readonly=True
        ),
        'ver_mensaje_origen': fields.integer(
            'Versión Mensaje',
            help="Versión del mensaje que se envió (libre para el creador del mensaje)", required=False, readonly=True
        ),
        'id_remitente_origen': fields.char(
            'ID Remitente Origen', size=16,
            help="Código del Agente que envió el mensaje", required=True, readonly=True
        ),
        # Respuesta
        'codigo_respuesta': fields.char(
            'Código Respuesta', size=16, help="Código de la respuesta", required=True, readonly=True
        ),
        'texto_respuesta': fields.text(
            'Texto Respuesta', help="Textos descriptivos de la respuesta", required=False, readonly=True
        ),
        # ResumenOfertas
        'num_ofertas_procesadas': fields.integer(
            'Núm. Ofertas Procesadas', help="Número total de ofertas procesadas", required=True, readonly=True
        ),
        'num_ofertas_correctas': fields.integer(
            'Núm. Ofertas Correctas', help="Número total de ofertas correctas", required=True, readonly=True
        ),
        # RespuestaSerie
        'oferta_id': fields.many2one(
            'giscedata.omie.oferta', "Oferta",
            help="ID de las oferta asociada a esta petición", required=True, readonly=True
        ),
        # Unidad
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
        # CodTransaccion
        'codigo': fields.integer("Código", size=6, required=True),
        'version': fields.integer("Versión", size=6, required=False),
    }
    #TODO 'Respuesta' (codigoRespuesta i TextoRespuesta) es repeteix. Podria tenir tambe encapsulat codigo i version


GiscedataOmieOfertaPeticion()


class GiscedataOmieOferta(osv.osv):

    _name = 'giscedata.omie.oferta'
    _inherit = 'giscedata.omie.oferta'

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
                "Ctn": bloque_vals.get('ctn'),
                "Prc": bloque_vals.get('prc')
            }
            list_bloques.append(dicc_bloque)
            i += 1

        # TODO: la fecha_mensaje fare que sigui readonly i només s'emplenarà quan s'hagi enviat la oferta amb datetime.today()

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
                'CondEco': {
                    'TerminoFijo': oferta_vals_filtered.get('termino_fijo', 0),
                    'TerminoVariable': oferta_vals_filtered.get('termino_variable', 0.0)
                },
                'CondTec': {
                    'Gradientes': {
                        'Parada': oferta_vals_filtered.get('grad_parada'),
                        'Arranque': oferta_vals_filtered.get('grad_arranque'),
                        'Bajada': oferta_vals_filtered.get('grad_bajada'),
                        'Subida': oferta_vals_filtered.get('grad_subida')
                    }
                },
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

    def respuesta_oferta_dicc(self, cursor, uid, respuesta_oferta_dicc, context=None):
        if context is None:
            context = {}

        texto_respuesta = respuesta_oferta_dicc.get('RespuestaSerie', {}).get('Respuesta', {}).get('TextoRespuesta', False)
        if texto_respuesta:
            texto_respuesta = texto_respuesta[0]

        peticion_dicc = {
            'id_mensaje': respuesta_oferta_dicc.get('IdMensaje', False),
            'fecha_mensaje': respuesta_oferta_dicc.get('FechaMensaje', False),
            'id_remitente': respuesta_oferta_dicc.get('IdRemitente', False),
            'id_mensaje_origen': respuesta_oferta_dicc.get('IdMensajeOrigen', False),
            'ver_mensaje_origen': respuesta_oferta_dicc.get('VerMensajeOrigen', False),
            'id_remitente_origen': respuesta_oferta_dicc.get('IdRemitenteOrigen', False),
            'codigo_respuesta': respuesta_oferta_dicc.get('Respuesta', {}).get('CodigoRespuesta', False),
            'texto_respuesta': respuesta_oferta_dicc.get('Respuesta', {}).get('TextoRespuesta', False),
            'num_ofertas_procesadas': respuesta_oferta_dicc.get('ResumenOfertas', {}).get('NumOfertasProcesadas', {}).get('v', False),
            'num_ofertas_correctas': respuesta_oferta_dicc.get('ResumenOfertas', {}).get('NumOfertasCorrectas', {}).get('v', False),
            'oferta_id': respuesta_oferta_dicc.get('RespuestaSerie', {}).get('IdOferta', {}).get('v', False),
            'codigo': respuesta_oferta_dicc.get('RespuestaSerie', {}).get('CodTransaccion', {}).get('codigo', False),
            'version': respuesta_oferta_dicc.get('RespuestaSerie', {}).get('CodTransaccion', {}).get('version', False),
            #'codigo_respuesta': respuesta_oferta_dicc.get('RespuestaSerie', {}).get('Respuesta', {}).get('CodigoRespuesta', {}).get('v', False),
            #'texto_respuesta': texto_respuesta,
            'ver_transaccion': respuesta_oferta_dicc.get('RespuestaSerie', {}).get('IdOferta', {}).get('v', False),
            'id_unidad': respuesta_oferta_dicc.get('RespuestaSerie', {}).get('CodTransaccion', {}).get('v', False),
            'cod_min_unidad': respuesta_oferta_dicc.get('RespuestaSerie', {}).get('CodTransaccion', {}).get('codMin', False),
            'area_unidad': respuesta_oferta_dicc.get('RespuestaSerie', {}).get('CodTransaccion', {}).get('area', False),
            'tipo_unidad': respuesta_oferta_dicc.get('RespuestaSerie', {}).get('CodTransaccion', {}).get('tipo', False),
        }


    def crear_peticion_oferta(self, cursor, uid, oferta_id, respuesta_oferta_dicc, context=None):
        if context is None:
            context = {}

        peticion_obj = self.pool.get('giscedata.omie.oferta.peticion')

        peticion_dicc = self.respuesta_oferta_dicc(cursor, uid, respuesta_oferta_dicc, context=context)
        peticion_dicc.update({'oferta_id': oferta_id})
        peticion_obj.create(cursor, uid, peticion_dicc, context=context)

    def delete_null_fields(self, cursor, uid, oferta_dicc, context=None):
        if context is None:
            context = {}
        res = {x: y for x, y in oferta_dicc.items() if y}
        return res

    def enviar_oferta(self, cursor, uid, ids, context=None):
        if context is None:
            context = {}

        for oferta_id in ids:

            oferta_dicc = self.mensaje_oferta_md_dicc(cursor, uid, oferta_id, context=context)


            client = ClientOMIE(
                crt_path='/home/aorellana/proyectos/OMIE/omie-base/omie/data/omie.cert',
                crt_key='/home/aorellana/proyectos/OMIE/omie-base/omie/data/omie.key'
            )

            # Crear una petició associada a aquesta oferta
            # La petició s'emplenarà amb el que ens retorni la petició
            # Si salta una excepció farem saltar un raise

            try:
                respuesta_oferta_dicc = client.ServicioAltaOfertasMD(MensajeOfertasMD=oferta_dicc)
                self.crear_peticion_oferta(cursor, uid, oferta_id, respuesta_oferta_dicc, context=context)
            except Exception as e:
                raise osv.except_osv('Error:', e)


    _columns = {
        # Blq
        'bloque_ids': fields.one2many('giscedata.omie.oferta.bloque', 'oferta_id', "Bloques de Oferta"),
        # Peticiones
        'peticion_ids': fields.one2many(
            'giscedata.omie.oferta.peticion', 'oferta_id', "Peticiones de Oferta", readonly=True
        ),
    }


GiscedataOmieOferta()
