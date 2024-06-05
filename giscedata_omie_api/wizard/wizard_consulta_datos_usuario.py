# -*- coding: utf-8 -*-
from __future__ import absolute_import
from osv import osv, fields
from omie import ClientOMIE
from zeep import helpers


class GiscedataPermisosUsuario(osv.osv_memory):

    _name = 'giscedata.permisos.usuario'
    _description = """Clase auxiliar para visualización de wizard"""

    _columns = {
        'codigo': fields.char('Código', size=128),
        'perfil': fields.char('Perfil', size=128),
        'wiz_id': fields.many2one('wizard.consulta.datos.usuario', 'Wizard'),
    }


GiscedataPermisosUsuario()


class WizardConsultaDatosUsuario(osv.osv_memory):

    _name = 'wizard.consulta.datos.usuario'
    _description = """Este servicio permite consultar los datos del Usuario"""

    def consulta_datos_usuario(self, cursor, uid, ids, context=None):
        if context is None:
            context = {}

        permiso_usuario_obj = self.pool.get('giscedata.permisos.usuario')
        wiz_id = ids[0]
        ctx = context.copy()
        ctx.update({'prefetch': False})
        wiz_brw = self.browse(cursor, uid, wiz_id, context=ctx)

        client = ClientOMIE(
            crt_path='/home/aorellana/proyectos/OMIE/omie-base/omie/data/omie.cert',
            crt_key='/home/aorellana/proyectos/OMIE/omie-base/omie/data/omie.key'
        )
        try:
            result = client.ServicioConsultaDatosUsuario()
            res_serialized = helpers.serialize_object(result)
            write_vals_wiz = {
                'cod_agente': res_serialized.get('IdAgente').get('CodAgente').get('v'),
                'des_agente': res_serialized.get('IdAgente').get('DesAgente').get('v'),
                'perfil_agente': res_serialized.get('IdAgente').get('PerfilAgente').get('v'),
                'cod_tarjeta': res_serialized.get('DatosTarjeta').get('CodTarjeta').get('v'),
                'perfil_tarjeta': res_serialized.get('DatosTarjeta').get('PerfilTarjeta').get('v'),
                'nombre_titular': res_serialized.get('DatosTarjeta').get('DatosTitular').get('Nombre').get('v'),
                'apellidos_titular': res_serialized.get('DatosTarjeta').get('DatosTitular').get('Apellidos').get('v'),
                'email': res_serialized.get('DatosTarjeta').get('DatosTitular').get('EMail').get('v'),
                'fecha_alta': res_serialized.get('DatosTarjeta').get('Validez').get('FechaAlta').get('v').strftime("%d-%m-%Y"),
                'fecha_baja': res_serialized.get('DatosTarjeta').get('Validez').get('FechaBaja').get('v').strftime("%d-%m-%Y"),
            }
            permiso_dicc = res_serialized.get('DatosTarjeta').get('Permisos').get('Permiso'),
            for permiso in permiso_dicc[0]:
                create_vals_permiso = {
                    'codigo': permiso.get('cod'),
                    'perfil': permiso.get('perfil'),
                    'wiz_id': wiz_id,
                }
                permiso_usuario_obj.create(cursor, uid, create_vals_permiso, context=context)
            write_vals_wiz.update({'state': 'end'})
            wiz_brw.write(write_vals_wiz)
        except Exception as e:
            wiz_brw.write({'state': 'error'})


    _columns = {
        'state': fields.selection([('init', 'init'), ('end', 'end'), ('error', 'error')], 'Estat'),
        'cod_agente': fields.char('Código Agente', size=32),
        'des_agente': fields.char('Descripción Agente', size=128),
        'perfil_agente': fields.char('Perfil Agente', size=32),
        'cod_tarjeta': fields.char('Código Tarjeta', size=64),
        'perfil_tarjeta': fields.char('Perfil Tarjeta', size=64),
        'nombre_titular': fields.char('Nombre', size=128),
        'apellidos_titular': fields.char('Apellidos', size=128),
        'email': fields.char('Email', size=128),
        'fecha_alta': fields.char('Fecha Alta', size=128),
        'fecha_baja': fields.char('Fecha Baja', size=128),
        'permisos_ids': fields.one2many('giscedata.permisos.usuario', 'wiz_id', 'Permisos Usuario'),
    }

    _defaults = {
        'state': lambda *a: 'init',
    }


WizardConsultaDatosUsuario()
