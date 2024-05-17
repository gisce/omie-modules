# -*- coding: utf-8 -*-
from __future__ import absolute_import
from osv import osv, fields

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
                 "envía el fichero (único por mensaje)"
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
        'fecha_sesion': fields.datetime(
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
        'termino_variable': fields.float("Término Variable", digits=(9, 3), help="Término variable"),
        # CondTec
        #Gradiente
        'parada': fields.float("Gradiente de Parada", digits=(5, 1), help="Gradiente de Parada", required=True),
        'arranque': fields.float("Gradiente de Arranque", digits=(5, 1), help="Gradiente de Arranque", required=True),
        'bajada': fields.float("Gradiente de Bajada", digits=(5, 1), help="Gradiente de Bajada", required=True),
        'subida': fields.float("Gradiente de Subida", digits=(5, 1), help="Gradiente de Subida", required=True),
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
    _description = """Representa una consulta de oferta con código y versión (opcional)."""

    _columns = {
        'codigo': fields.integer("Código", size=6, required=True),
        'version': fields.integer("Versión", size=6, required=False),
    }


GiscedataOmieOfertaConsulta()


class GiscedataOmieOfertaBloque(osv.osv):

    _name = 'giscedata.omie.oferta.bloque'
    _description = """Representa una oferta por hora de un dia concreto."""

    _columns = {
        'num': fields.integer("Número de Bloque", required=True),
        'div': fields.selection(SI_NO, "Es divisible", required=True),
        'ret': fields.selection(SI_NO, "Es retirable", required=True),
        'Per': fields.selection(
            PERIODO_DIA, "Periodo horario del día",
            help="Seleccionar el periodo del día para el que quiere hacer la oferta", required=True),
        'ctn': fields.float("Energía de la Oferta", digits=(5, 3), help="Energía de la oferta, sin signo",
                            required=True),
        'prc': fields.float("Precio de la Oferta", digits=(5, 3), required=True),
        'oferta_id': fields.many2one('giscedata.omie.oferta', 'ID Oferta', required=True),
    }


GiscedataOmieOfertaBloque()

class GiscedataOmieOfertaPeticion(osv.osv):

    _name = 'giscedata.omie.oferta.peticion'
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
        'codigo_respuesta': fields.char(
            'Código Respuesta', size=16, help="Código de la respuesta", required=True, readonly=True
        ),
        'texto_respuesta': fields.text(
            'Texto Respuesta', help="Textos descriptivos de la respuesta", required=False, readonly=True
        ),
        'num_ofertas_procesadas': fields.integer(
            'Núm. Ofertas Procesadas', help="Número total de ofertas procesadas", required=True, readonly=True
        ),
        'num_ofertas_correctas': fields.integer(
            'Núm. Ofertas Correctas', help="Número total de ofertas correctas", required=True, readonly=True
        ),
        'oferta_id': fields.many2one(
            'giscedata.omie.oferta', "Oferta",
            help="ID de las oferta asociada a esta petición", required=True, readonly=True
        ),
        'cod_transaccion': fields.integer(
            "Código de la transacción", size=10,
            help="Código y versión de una transacción (oferta, ejecución, declaración)", required=True, readonly=True
        ),
        'ver_transaccion': fields.integer(
            "Versión de la transacción", size=3, help="Versión de la transacción", required=False, readonly=True
        ),
    }


GiscedataOmieOfertaPeticion()


class GiscedataOmieOferta(osv.osv):

    _name = 'giscedata.omie.oferta'
    _inherit = 'giscedata.omie.oferta'

    _columns = {
        # Blq
        'bloque_ids': fields.one2many('giscedata.omie.oferta.bloque', 'oferta_id', "Bloques de Oferta", required=True),
        # Peticiones
        'peticion_ids': fields.one2many(
            'giscedata.omie.oferta.peticion', 'oferta_id', "Peticiones de Oferta", readonly=True
        ),
    }


GiscedataOmieOferta()
