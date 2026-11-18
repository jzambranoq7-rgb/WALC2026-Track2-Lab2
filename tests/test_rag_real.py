"""Regresión con PostgreSQL, Pinecone y Ollama reales, sin respuestas simuladas.

Requiere el corpus académico completo preparado e indexado. Se habilita con
PRUEBAS_RAG_REALES=1; consulta servicios y puede consumir inferencia de Pinecone.
"""

import importlib
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
common = importlib.import_module("1-common")
rag = importlib.import_module("6-rag")
busqueda = importlib.import_module("5-buscar")


@unittest.skipUnless(
    os.getenv("PRUEBAS_RAG_REALES") == "1", "Requiere servicios reales y corpus indexado"
)
class RagReal(unittest.TestCase):
    def test_respuestas_y_abstenciones_del_recorrido(self) -> None:
        """Comprueba datos esperados y abstención, además de la validez del JSON."""
        casos = [
            ("datos de inscripción", "¿Qué datos necesito para solicitar una inscripción?", "con_evidencia", ["matrícula", "período"]),
            ("biblioteca", "¿Cuántos libros puedo solicitar y por cuántos días?", "con_evidencia", ["3", "14"]),
            ("plazo no documentado", "¿Cuánto tarda la emisión de una constancia?", "sin_evidencia", []),
            ("horario actual", "¿Hasta qué hora atiende la mesa de orientación?", "con_evidencia", ["16:00"]),
            ("horario histórico", "¿Hasta qué hora atendía la mesa de orientación en septiembre de 2026?", "con_evidencia", ["15:00"]),
        ]
        for nombre, pregunta, estado, valores in casos:
            with self.subTest(caso=nombre):
                recuperacion = common.buscar(
                    pregunta, top_k=busqueda.TOP_K,
                    documento="horario-orientacion" if nombre == "horario histórico" else None,
                )
                texto, traza = rag.responder(pregunta, recuperacion)
                self.assertEqual(traza["estado"], estado, traza.get("motivo"))
                afirmaciones = traza.get("salida", {}).get("afirmaciones", [])
                respuesta_generada = " ".join(afirmacion["texto"] for afirmacion in afirmaciones)
                for valor in valores:
                    self.assertTrue(valor in respuesta_generada or (valor == "3" and "tres" in respuesta_generada.lower()), respuesta_generada)
                fuentes = {fragmento["id"]: fragmento for fragmento in recuperacion["fragmentos"]}
                for afirmacion in afirmaciones:
                    fuente = fuentes[afirmacion["fuente_id"]]
                    if nombre == "horario histórico":
                        self.assertEqual(fuente["documento"], "horario-orientacion")
                        self.assertEqual(fuente["version"], 1)
                    elif fuente["documento"] == "horario-orientacion":
                        self.assertEqual(fuente["version"], 2)
                    self.assertIn(fuente["texto"], texto)
                    self.assertIn(fuente["url"], texto)
