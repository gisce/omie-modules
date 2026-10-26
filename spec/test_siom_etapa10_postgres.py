# -*- coding: utf-8 -*-
"""Integracion real PostgreSQL: SOLO BBDD DE PRUEBAS DESCARTABLE.

Activar con SIOM_PG_TEST_DSN (psycopg2). Esquema dedicado aleatorio; nunca
usar contra una BBDD productiva. Tests se omiten sin la dependencia/DSN.
"""
from __future__ import absolute_import

import importlib
import os
import sys
import threading
import types
import unittest
import uuid

from mock import Mock
from types import ModuleType
# Simulamos el módulo tools que proporciona GISCE-ERP.
tools_mock = ModuleType('tools')
tools_mock.__path__ = []  # Permite tratarlo como paquete
tools_mock.config = Mock()

# Simulamos tools.translate.
translate_mock = ModuleType('tools.translate')
translate_mock._ = lambda text: text

# Registramos ambos módulos.
tools_mock.translate = translate_mock

sys.modules['tools'] = tools_mock
sys.modules['tools.translate'] = translate_mock

from test_siom_control_ejecucion import FakeFields, FakeOsV, FakeBusinessCursor

APP = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'giscedata_omie_api'))
DSN = os.environ.get('SIOM_PG_TEST_DSN')
try:
    import psycopg2
except ImportError:
    psycopg2 = None


class PostgreSQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DSN or psycopg2 is None:
            raise unittest.SkipTest('PostgreSQL real requiere SIOM_PG_TEST_DSN y psycopg2')
        # Exigir declaracion explicita de BBDD descartable.
        if os.environ.get('SIOM_PG_DISPOSABLE') != 'YES':
            raise unittest.SkipTest('Requiere SIOM_PG_DISPOSABLE=YES para crear un esquema temporal')
        cls.schema = 'siom_test_' + uuid.uuid4().hex[:12]
        cls.root = psycopg2.connect(DSN)
        cls.root.autocommit = True
        cr = cls.root.cursor()
        cr.execute('CREATE SCHEMA ' + cls.schema)
        cr.execute('''CREATE TABLE %s.giscedata_omie_siom_minimum_time
                      (consulta integer primary key, tiempo_agente_ms integer,
                       tiempo_certificado_ms integer)''' % cls.schema)
        cr.execute('''CREATE TABLE %s.giscedata_omie_siom_query_execution
                     (id serial primary key, consulta integer, usuario_id integer,
                      fecha_intento timestamp, fecha_fin timestamp,
                      limite_ms integer, configurada boolean,
                      estado varchar(64), detalle varchar(256))''' % cls.schema)
        cr.execute('''CREATE TABLE %s.giscedata_omie_siom_service_execution
                     (id serial primary key, servicio varchar(100), oferta_id integer,
                      usuario_id integer, fecha_intento timestamp, fecha_fin timestamp,
                      estado varchar(64), detalle varchar(256))''' % cls.schema)
        cr.close()
        cls.backup = {}
        for k in ('osv', 'giscedata_omie_api',
                  'giscedata_omie_api.giscedata_omie_siom_query_execution',
                  'giscedata_omie_api.giscedata_omie_siom_service_execution'):
            cls.backup[k] = sys.modules.get(k)
        mod = types.ModuleType('osv')
        mod.osv = type('OSV', (), {'osv': FakeOsV})
        mod.fields = FakeFields()
        sys.modules['osv'] = mod
        pkg = types.ModuleType('giscedata_omie_api')
        pkg.__path__ = [APP]
        sys.modules[pkg.__name__] = pkg
        cls.consultas = importlib.import_module(
            'giscedata_omie_api.giscedata_omie_siom_query_execution')
        cls.servicios = importlib.import_module(
            'giscedata_omie_api.giscedata_omie_siom_service_execution')

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'root'):
            cr = cls.root.cursor()
            cr.execute('DROP SCHEMA ' + cls.schema + ' CASCADE')
            cr.close()
            cls.root.close()
        if hasattr(cls, 'backup'):
            for k, old in cls.backup.items():
                if old is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = old

    def setUp(self):
        self.business = FakeBusinessCursor()
        self.ofertas = self.servicios.GiscedataOmieSiomServiceExecution()
        self.ofertas._nueva_conexion = lambda cr: psycopg2.connect(
            DSN, options='-c search_path=%s' % self.schema).cursor()
        # Real cursors need their connection committed: wrapper below.
        self.ofertas._nueva_conexion = lambda cr: PgCursor(
            psycopg2.connect(DSN, options='-c search_path=%s' % self.schema))
        self.control = self.consultas.GiscedataOmieSiomQueryExecution()
        self.control._nueva_conexion = self.ofertas._nueva_conexion
        conn = self.root.cursor()
        conn.execute('TRUNCATE TABLE %s.giscedata_omie_siom_query_execution RESTART IDENTITY' % self.schema)
        conn.execute('TRUNCATE TABLE %s.giscedata_omie_siom_service_execution RESTART IDENTITY' % self.schema)
        conn.execute('TRUNCATE TABLE %s.giscedata_omie_siom_minimum_time' % self.schema)
        conn.close()

    def test_consulta_reserva_confirma_independientemente(self):
        cr = self.root.cursor()
        cr.execute('''INSERT INTO %s.giscedata_omie_siom_minimum_time
                      VALUES (5222, 60000, 30000)''' % self.schema)
        cr.close()
        self.control.ejecutar_consulta(self.business, 7, 5222, lambda: {'Respuesta': []})
        with self.assertRaises(self.consultas.TiempoMinimoNoCumplido):
            self.control.ejecutar_consulta(self.business, 7, 5222, lambda: True)
        cr = self.root.cursor()
        cr.execute('SELECT count(*) FROM %s.giscedata_omie_siom_query_execution' % self.schema)
        self.assertEqual(cr.fetchone()[0], 1)
        cr.close()

    def test_dos_ofertas_en_paralelo_seriadas_realmente(self):
        entrar, soltar = threading.Event(), threading.Event()
        fallos = []
        def lento():
            try:
                def soap():
                    entrar.set()
                    if not soltar.wait(4):
                        raise AssertionError('timeout test')
                    return True
                self.ofertas.ejecutar_servicio(self.business, 7,
                    'ServicioAltaOfertasMD', soap, oferta_id=123)
            except Exception as exc:
                fallos.append(exc)
        hilo = threading.Thread(target=lento)
        hilo.start()
        self.assertTrue(entrar.wait(4))
        try:
            with self.assertRaises(self.servicios.EnvioOMIEPendiente):
                self.ofertas.ejecutar_servicio(self.business, 8,
                    'ServicioAltaOfertasMI', lambda: True, oferta_id=124)
        finally:
            soltar.set()
            hilo.join(4)
        self.assertFalse(hilo.is_alive())
        self.assertFalse(fallos)

    def test_10d1_preparacion_antigua_se_cancela_sin_soap(self):
        ejecucion = self.ofertas._reservar(self.business, 7,
            'ServicioAltaOfertasMD', oferta_id=100)
        cur = self.root.cursor()
        cur.execute("UPDATE %s.giscedata_omie_siom_service_execution "
                    "SET fecha_intento=fecha_intento - interval '10 minutes' "
                    "WHERE id=%%s" % self.schema, (ejecucion,))
        cur.close()
        self.assertEqual(self.ofertas.recuperar_envios_pendientes(
            self.business, 7), 1)
        with self.assertRaises(self.servicios.EnvioOMIEPendiente):
            self.ofertas._iniciar_envio(self.business, ejecucion)
        cur = self.root.cursor()
        cur.execute('SELECT estado FROM %s.giscedata_omie_siom_service_execution'
                    ' WHERE id=%%s' % self.schema, (ejecucion,))
        self.assertEqual(cur.fetchone()[0], 'cancelada')
        cur.close()
        self.assertTrue(self.ofertas.ejecutar_servicio(
            self.business, 7, 'ServicioAltaOfertasMI', lambda: True,
            oferta_id=101))

    def test_10d1_envio_iniciado_no_se_recupera_por_tiempo(self):
        ejecucion = self.ofertas._reservar(self.business, 7,
            'ServicioAltaOfertasMD', oferta_id=100)
        self.ofertas._iniciar_envio(self.business, ejecucion)
        cur = self.root.cursor()
        cur.execute("UPDATE %s.giscedata_omie_siom_service_execution "
                    "SET fecha_intento=fecha_intento - interval '10 hours' "
                    "WHERE id=%%s" % self.schema, (ejecucion,))
        cur.close()
        self.assertEqual(self.ofertas.recuperar_envios_pendientes(
            self.business, 7), 0)
        with self.assertRaises(self.servicios.EnvioOMIEPendiente):
            self.ofertas._reservar(self.business, 8,
                'ServicioAltaOfertasMI', oferta_id=101)

    def test_10d1_cancelacion_y_promocion_compiten_atomicamente(self):
        ejecucion = self.ofertas._reservar(self.business, 7,
            'ServicioAltaOfertasMD', oferta_id=100)
        cur = self.root.cursor()
        cur.execute("UPDATE %s.giscedata_omie_siom_service_execution "
                    "SET fecha_intento=fecha_intento - interval '10 minutes' "
                    "WHERE id=%%s" % self.schema, (ejecucion,))
        cur.close()
        empezar = threading.Event()
        acciones = []
        fallos = []
        def intentar_enviar():
            try:
                empezar.wait(3)
                self.ofertas._iniciar_envio(self.business, ejecucion)
                acciones.append('enviando')
            except self.servicios.EnvioOMIEPendiente:
                acciones.append('cancelada')
            except Exception as exc:
                fallos.append(exc)
        def intentar_cancelar():
            try:
                empezar.wait(3)
                self.ofertas.recuperar_envios_pendientes(self.business, 7)
            except Exception as exc:
                fallos.append(exc)
        t1 = threading.Thread(target=intentar_enviar)
        t2 = threading.Thread(target=intentar_cancelar)
        t1.start()
        t2.start()
        empezar.set()
        t1.join(5)
        t2.join(5)
        self.assertFalse(t1.is_alive() or t2.is_alive())
        self.assertFalse(fallos)
        cur = self.root.cursor()
        cur.execute('SELECT estado FROM %s.giscedata_omie_siom_service_execution'
                    ' WHERE id=%%s' % self.schema, (ejecucion,))
        estado = cur.fetchone()[0]
        cur.close()
        self.assertIn(estado, ('enviando', 'cancelada'))
        self.assertEqual(acciones, [estado])

    def test_10d1_auditoria_sobrevive_rollback_del_negocio(self):
        negocio = PgCursor(psycopg2.connect(
            DSN, options='-c search_path=%s' % self.schema))
        try:
            negocio.execute('SELECT 1')
            self.assertTrue(self.ofertas.ejecutar_servicio(
                negocio, 7, 'ServicioAltaOfertasMD', lambda: True,
                oferta_id=100))
            negocio.rollback()
        finally:
            negocio.close()
        cur = self.root.cursor()
        cur.execute('SELECT estado FROM %s.giscedata_omie_siom_service_execution'
                    ' ORDER BY id DESC LIMIT 1' % self.schema)
        self.assertEqual(cur.fetchone()[0], 'respondida')
        cur.close()


class PgCursor(object):
    """Proxy compatible con API OpenERP: commit, rollback y close sobre conexion."""
    def __init__(self, conn):
        self.conn = conn
        self.cur = conn.cursor()
    def execute(self, *args, **kw):
        return self.cur.execute(*args, **kw)
    def fetchone(self):
        return self.cur.fetchone()
    @property
    def rowcount(self):
        return self.cur.rowcount
    def commit(self):
        self.conn.commit()
    def rollback(self):
        self.conn.rollback()
    def close(self):
        self.cur.close()
        self.conn.close()


if __name__ == '__main__':
    unittest.main()
