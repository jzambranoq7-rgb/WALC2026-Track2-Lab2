"""Pruebas SQL reales, solo en una base descartable llamada walc_pruebas.

Se habilitan con PRUEBAS_POSTGRES=1 y PGDATABASE=walc_pruebas.
No usan Pinecone ni modifican la base documental del participante.
"""

import importlib
import json
import os
import sys
import unittest
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
common = importlib.import_module("1-common")
preparacion = importlib.import_module("3-preparar")


@unittest.skipUnless(os.getenv("PRUEBAS_POSTGRES") == "1", "Requiere PostgreSQL de pruebas")
class AlmacenamientoPostgres(unittest.TestCase):
    def setUp(self) -> None:
        """Prepara el corpus exclusivamente en la base dedicada a las pruebas."""
        if os.getenv("PGDATABASE") != "walc_pruebas":
            raise ValueError("Estas pruebas solo pueden usar PGDATABASE=walc_pruebas.")
        ruta_catalogo = common.RAIZ_LABORATORIO / "conocimiento" / "catalogo.json"
        self.catalogo = json.loads(ruta_catalogo.read_text())
        self.fragmentos = preparacion.preparar_fragmentos()
        common.guardar_corpus(self.catalogo, self.fragmentos)

    def test_documentos_y_fragmentos_persisten_con_procedencia(self) -> None:
        """Otra conexión recupera las mismas fuentes y el texto del documento."""
        recuperados = common.cargar_fragmentos()
        self.assertEqual(len(recuperados), len(self.fragmentos))
        with common.conectar_postgres() as conexion:
            documento = conexion.execute(
                "SELECT texto, archivo FROM documentos WHERE documento = %s AND version = %s",
                ("inscripciones", 1),
            ).fetchone()
        self.assertIn("nombre completo", documento["texto"])
        self.assertEqual(documento["archivo"], "inscripciones.pdf")

    def test_recupera_solo_los_ids_solicitados(self) -> None:
        """El ID devuelto por Pinecone permite volver al fragmento y a su PDF."""
        fuente = self.fragmentos[0]
        recuperados = common.cargar_fragmentos([fuente["id"]])
        self.assertEqual(recuperados, [fuente])
        self.assertEqual(common.cargar_fragmentos([]), [])
        self.assertEqual(common.cargar_fragmentos(["'; DROP TABLE documentos; --"]), [])

    def test_escritura_sql_invalida_estado_hasta_confirmar_pinecone(self) -> None:
        """El estado SQL sustituye las huellas sin releer el PDF en cada consulta."""
        namespace = common.obtener_namespace()
        host = "https://prueba.pinecone.io"
        common.registrar_indexacion(namespace, host)
        common.comprobar_indexacion(namespace, host)
        common.guardar_corpus(self.catalogo, self.fragmentos)
        with self.assertRaisesRegex(ValueError, "Falta una carga terminada"):
            common.comprobar_indexacion(namespace, host)

    def test_actualizar_un_documento_conserva_los_demas(self) -> None:
        """Procesar un PDF por ruta no elimina otros documentos de la práctica."""
        documento = self.catalogo[0]
        fragmentos_documento = []
        for fragmento in self.fragmentos:
            if fragmento["metadata"]["documento"] == documento["documento"]:
                fragmentos_documento.append(fragmento)
        common.guardar_corpus([documento], fragmentos_documento)
        self.assertEqual(len(common.cargar_fragmentos()), len(self.fragmentos))
        with common.conectar_postgres() as conexion:
            cantidad = conexion.execute("SELECT count(*) AS total FROM documentos").fetchone()
        self.assertEqual(cantidad["total"], len(self.catalogo))

    def test_guardar_un_fragmento_conserva_los_demas_y_el_documento_completo(self) -> None:
        """Indexar por ID no elimina sus vecinos ni trunca el texto original."""
        datos = preparacion.preparar_ruta(
            common.RAIZ_LABORATORIO / "conocimiento/inscripciones.pdf"
        )
        common.guardar_corpus(datos["documentos"], [datos["fragmentos"][0]])
        self.assertEqual(len(common.cargar_fragmentos()), len(self.fragmentos))
        with common.conectar_postgres() as conexion:
            documento = conexion.execute(
                "SELECT texto FROM documentos WHERE documento = %s AND version = 1",
                ("inscripciones",),
            ).fetchone()
        self.assertEqual(documento["texto"], datos["documentos"][0]["texto"])

    def test_error_de_preparacion_conserva_el_corpus_anterior(self) -> None:
        """Un fallo de clave foránea revierte todos los DELETE e INSERT del paso."""
        fragmento_invalido = {
            "id": "invalido",
            "metadata": {**self.fragmentos[0]["metadata"], "documento": "inexistente"},
        }
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            common.guardar_corpus(self.catalogo, [fragmento_invalido])
        self.assertEqual(len(common.cargar_fragmentos()), len(self.fragmentos))


if __name__ == "__main__":
    unittest.main()
