"""Pruebas aisladas. Los dobles no sustituyen una consulta real a Pinecone."""

import importlib
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
common = importlib.import_module("1-common")
preparacion = importlib.import_module("3-preparar")
rag = importlib.import_module("6-rag")


class Laboratorio(unittest.TestCase):
    def setUp(self) -> None:
        self.fragmentos = preparacion.preparar_fragmentos()

    def test_corpus_pdf_y_procedencia(self) -> None:
        self.assertGreaterEqual(len(self.fragmentos), 20)
        self.assertEqual(len({f["id"] for f in self.fragmentos}), len(self.fragmentos))
        self.assertEqual(len({f["metadata"]["archivo"] for f in self.fragmentos}), 10)
        for fragmento in self.fragmentos:
            meta = fragmento["metadata"]
            self.assertTrue(meta["archivo"].endswith(".pdf"))
            self.assertGreaterEqual(meta["pagina"], 1)
            self.assertTrue(meta["seccion"])
            self.assertIn(meta["tipo"], {"politica", "procedimiento", "faq"})
            self.assertLessEqual(len(meta["texto"]), 800)
            self.assertNotIn("Material ficticio", meta["texto"])
        textos = " ".join(f["metadata"]["texto"] for f in self.fragmentos)
        self.assertIn("número de seguimiento", textos)
        self.assertIn("tres libros", textos)

    def test_pdf_extrae_paginas(self) -> None:
        ruta = common.RAIZ_LABORATORIO / "conocimiento" / "inscripciones.pdf"
        paginas = list(preparacion.extraer_paginas(ruta))
        self.assertTrue(paginas)
        self.assertIn("nombre completo", " ".join(paginas[0][1].split()))

    def test_constancia_no_inventa_plazo(self) -> None:
        textos = " ".join(f["metadata"]["texto"] for f in self.fragmentos
                          if f["metadata"]["documento"] == "constancias")
        self.assertIn("no establece un plazo", textos)

    def test_horarios_conservan_version_y_vigencia(self) -> None:
        versiones = {f["metadata"]["version"]: f["metadata"] for f in self.fragmentos
                     if f["metadata"]["documento"] == "horario-orientacion"}
        self.assertEqual(set(versiones), {1, 2})
        self.assertIn("15:00", versiones[1]["texto"])
        self.assertIn("16:00", versiones[2]["texto"])
        self.assertEqual(versiones[1]["vigente_hasta"], "2026-09-30")

    def test_corte_recupera_palabras(self) -> None:
        texto = " ".join(["condición importante"] * 60)
        partes = preparacion.dividir_texto(texto, 100)
        self.assertEqual(" ".join(partes), texto)
        self.assertTrue(all(len(parte) <= 100 for parte in partes))

    def test_corte_palabra_larga(self) -> None:
        texto = "a" * 210
        self.assertEqual("".join(preparacion.dividir_texto(texto, 100)), texto)

    def test_namespace_es_el_del_grupo(self) -> None:
        with patch.dict(os.environ, {"PINECONE_NAMESPACE": "grupo-02"}):
            self.assertEqual(common.obtener_namespace(), "grupo-02")

    def test_namespace_invalido_se_rechaza(self) -> None:
        with (
            patch.dict(os.environ, {"PINECONE_NAMESPACE": "otro/grupo"}),
            self.assertRaisesRegex(ValueError, "PINECONE_NAMESPACE"),
        ):
            common.obtener_namespace()

    def test_modelo_no_puede_introducir_una_cita_propia(self) -> None:
        """La salida del modelo no puede sustituir el texto de PostgreSQL."""
        with self.assertRaises(ValueError):
            rag.Afirmacion(
                texto="Una afirmación",
                fuente_id="fuente-1",
                cita_literal="Una cita que nunca apareció",
            )

    def test_id_inventado_se_rechaza(self) -> None:
        respuesta = rag.Respuesta(
            estado="con_evidencia",
            afirmaciones=[
                {
                    "texto": "Una afirmación",
                    "fuente_id": "ajena",
                }
            ],
        )
        with self.assertRaisesRegex(ValueError, "no se recuperó"):
            rag.validar_fuentes(
                respuesta, [{"id": "propia", "texto": "La copia completa es obligatoria."}]
            )

    def test_cita_y_enlace_se_toman_de_la_fuente_elegida(self) -> None:
        """La cita conserva el original aunque la afirmación esté reformulada."""
        fuente = {
            "id": "propia",
            "texto": "La copia completa es obligatoria.",
            "titulo": "Garantía",
            "version": 1,
            "pagina": 2,
            "seccion": "REQUISITOS",
            "url": "http://localhost:8002/garantia.pdf#page=2",
        }
        respuesta = rag.Respuesta(
            estado="con_evidencia",
            afirmaciones=[{"texto": "Se exige una copia.", "fuente_id": "propia"}],
        )
        rag.validar_fuentes(respuesta, [fuente])
        texto = rag.formatear_respuesta(respuesta, [fuente])
        self.assertIn("Cita del fragmento: La copia completa es obligatoria.", texto)
        self.assertIn(fuente["url"], texto)

    def test_modelo_recibe_metadatos_y_fecha_para_elegir_version(self) -> None:
        import json

        fragmento = {"id": self.fragmentos[0]["id"], **self.fragmentos[0]["metadata"]}
        cliente = Mock()
        cliente.chat.return_value = SimpleNamespace(
            message=SimpleNamespace(content='{"estado":"sin_evidencia","afirmaciones":[]}')
        )
        with (
            patch.object(common, "crear_cliente_ollama", return_value=cliente),
            patch.dict(os.environ, {"FECHA_CONSULTA": "2026-10-28"}),
        ):
            _, traza = rag.responder("pregunta", {"fragmentos": [fragmento]})
        contenido = traza["messages"][1]["content"]
        datos = json.loads(
            contenido.removeprefix("<consulta_actual>\n").removesuffix("\n</consulta_actual>")
        )
        self.assertEqual(datos["fecha_consulta"], "2026-10-28")
        for campo in ("documento", "version", "vigente_desde", "vigente_hasta", "texto"):
            self.assertEqual(datos["fragmentos"][0][campo], fragmento[campo])

    def test_cero_resultados_no_llama_llm(self) -> None:
        with patch.object(
            common, "crear_cliente_ollama", side_effect=AssertionError("no debe llamarse")
        ):
            texto, traza = rag.responder("pregunta", {"fragmentos": []})
        self.assertEqual(traza["estado"], "sin_evidencia")
        self.assertIn("No encontré evidencia", texto)

    def test_abstencion_no_admite_afirmaciones(self) -> None:
        respuesta = rag.Respuesta(
            estado="sin_evidencia",
            afirmaciones=[{"texto": "Algo", "fuente_id": "una"}],
        )
        with self.assertRaises(ValueError):
            rag.validar_fuentes(respuesta, [])

    def test_busqueda_envia_filtros_y_namespace(self) -> None:
        host_indice_prueba = "https://indice-prueba.pinecone.io"
        fuente = self.fragmentos[0]
        servicio_simulado = Mock()
        servicio_simulado.describe_index_stats.return_value = SimpleNamespace(
            dimension=common.DIMENSION_EMBEDDINGS
        )
        servicio_simulado.query.return_value = SimpleNamespace(
            matches=[SimpleNamespace(id=fuente["id"], score=0.8, metadata=fuente["metadata"])]
        )
        with (
            patch.dict(os.environ, {"PINECONE_INDEX_HOST": host_indice_prueba}),
            patch.object(common, "comprobar_indexacion"),
            patch.object(common, "cargar_fragmentos", return_value=[fuente]) as lectura_postgres,
            patch.object(common, "conectar_indice", return_value=servicio_simulado),
            patch.object(
                common, "calcular_embeddings", return_value=[[0.0] * common.DIMENSION_EMBEDDINGS]
            ),
            patch.object(preparacion, "PdfReader", side_effect=AssertionError("No releer PDF")),
        ):
            salida = common.buscar("plazo", documento="horario-orientacion", tipo="politica")
        lectura_postgres.assert_called_once_with([fuente["id"]])
        argumentos = servicio_simulado.query.call_args.kwargs
        self.assertEqual(argumentos["namespace"], common.obtener_namespace())
        self.assertFalse(argumentos["include_metadata"])
        self.assertEqual(
            salida["fragmentos"][0]["url"],
            common.enlace_documento(fuente["metadata"]["archivo"], fuente["metadata"]["pagina"]),
        )
        filtro = argumentos["filter"]["$and"]
        self.assertIn({"documento": {"$eq": "horario-orientacion"}}, filtro)
        self.assertEqual(len(filtro), 2)  # Solo documento y tipo; no añade sede ni vigencia.
        self.assertIn({"tipo": {"$eq": "politica"}}, filtro)
        self.assertEqual(salida["fragmentos"][0]["texto"], fuente["metadata"]["texto"])

    def test_id_vectorial_sin_documento_se_rechaza(self) -> None:
        """No genera una respuesta si Pinecone referencia un fragmento inexistente."""
        indice = Mock()
        indice.describe_index_stats.return_value = SimpleNamespace(
            dimension=common.DIMENSION_EMBEDDINGS
        )
        indice.query.return_value = SimpleNamespace(
            matches=[SimpleNamespace(id="ajeno", score=0.8)]
        )
        with (
            patch.object(common, "obtener_host_indice", return_value="https://prueba.pinecone.io"),
            patch.object(common, "comprobar_indexacion"),
            patch.object(common, "cargar_fragmentos", return_value=[]),
            patch.object(
                common, "calcular_embeddings", return_value=[[0.0] * common.DIMENSION_EMBEDDINGS]
            ),
            patch.object(common, "conectar_indice", return_value=indice),
            self.assertRaisesRegex(ValueError, "no existe en PostgreSQL"),
        ):
            common.buscar("pregunta")

    def test_embedding_gestionado_usa_pasaje_o_consulta(self) -> None:
        servicio_simulado = Mock()
        servicio_simulado.inference.embed.return_value = [
            SimpleNamespace(values=[0.0] * common.DIMENSION_EMBEDDINGS),
            SimpleNamespace(values=[0.0] * common.DIMENSION_EMBEDDINGS),
        ]
        with patch.object(common, "crear_cliente_pinecone", return_value=servicio_simulado):
            common.calcular_embeddings(["uno", "dos"], "passage")
        llamada = servicio_simulado.inference.embed.call_args.kwargs
        self.assertEqual(llamada["model"], common.MODELO_EMBEDDINGS)
        self.assertEqual(llamada["parameters"], {"input_type": "passage", "truncate": "NONE"})
        with self.assertRaisesRegex(ValueError, "passage"):
            common.calcular_embeddings(["uno"], "otro")

    def test_embedding_dimension_erronea(self) -> None:
        servicio_simulado = Mock()
        servicio_simulado.inference.embed.return_value = [SimpleNamespace(values=[0.0, 0.0, 0.0])]
        with (
            patch.object(common, "crear_cliente_pinecone", return_value=servicio_simulado),
            self.assertRaisesRegex(ValueError, "Dimensión"),
        ):
            common.calcular_embeddings(["uno"], "query")

    def test_dimension_erronea_se_rechaza(self) -> None:
        servicio_simulado = Mock()
        servicio_simulado.describe_index_stats.return_value = SimpleNamespace(dimension=123)
        with self.assertRaisesRegex(ValueError, "123"):
            common.comprobar_dimension_indice(servicio_simulado)

    def test_host_externo_se_rechaza_antes_de_enviar_clave(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "PINECONE_API_KEY": "clave-de-prueba",
                    "PINECONE_INDEX_HOST": "https://otro.ejemplo",
                },
            ),
            self.assertRaisesRegex(ValueError, "pinecone.io"),
        ):
            common.conectar_indice()


if __name__ == "__main__":
    unittest.main()
