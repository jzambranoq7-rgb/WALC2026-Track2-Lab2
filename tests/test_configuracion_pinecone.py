"""Comprueba creación y reutilización sin crear recursos en una cuenta real."""

import importlib
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
common = importlib.import_module("1-common")
verificacion = importlib.import_module("2-check_servicios")


class ConfiguracionPinecone(unittest.TestCase):
    def setUp(self) -> None:
        """Aísla la configuración y sustituye el cliente por un doble del SDK."""
        self.host_indice = "https://indice-prueba.pinecone.io"
        self.descripcion = SimpleNamespace(
            host=self.host_indice,
            dimension=common.DIMENSION_EMBEDDINGS,
            metric="cosine",
            vector_type="dense",
            status=SimpleNamespace(ready=True),
        )
        self.cliente = Mock()
        self.cliente.describe_index.return_value = self.descripcion
        self.cliente.create_index.return_value = self.descripcion
        entorno = patch.dict(os.environ, {"PINECONE_INDEX_HOST": ""})
        entorno.start()
        self.addCleanup(entorno.stop)
        cliente = patch.object(common, "crear_cliente_pinecone", return_value=self.cliente)
        cliente.start()
        self.addCleanup(cliente.stop)
        salida = redirect_stdout(io.StringIO())
        salida.__enter__()
        self.addCleanup(salida.__exit__, None, None, None)

    def test_crea_indice_ausente_y_resuelve_host(self) -> None:
        """Solicita vectores densos, dimensión correcta y espera de disponibilidad."""
        self.cliente.has_index.return_value = False
        verificacion.preparar_indice_pinecone()
        argumentos = self.cliente.create_index.call_args.kwargs
        self.assertEqual(argumentos["name"], common.NOMBRE_INDICE_PINECONE)
        self.assertEqual(argumentos["dimension"], common.DIMENSION_EMBEDDINGS)
        self.assertEqual(argumentos["metric"], "cosine")
        self.assertEqual(argumentos["vector_type"], "dense")
        self.assertEqual(argumentos["timeout"], 120)
        self.assertEqual(common.obtener_host_indice(), self.host_indice)

    def test_reutiliza_indice_existente_sin_crearlo(self) -> None:
        """Repetir la preparación no solicita otro índice."""
        self.cliente.has_index.return_value = True
        verificacion.preparar_indice_pinecone()
        self.cliente.create_index.assert_not_called()

    def test_rechaza_dimension_incompatible_sin_recrear(self) -> None:
        """Un índice existente incompatible se conserva y se informa el problema."""
        self.cliente.has_index.return_value = True
        self.descripcion.dimension = 768
        with self.assertRaisesRegex(ValueError, "dimensión"):
            verificacion.preparar_indice_pinecone()
        self.cliente.create_index.assert_not_called()

    def test_rechaza_metrica_y_tipo_incompatibles(self) -> None:
        """La coincidencia de dimensión no basta para reutilizar el índice."""
        self.cliente.has_index.return_value = True
        for metrica, tipo in [("dotproduct", "dense"), ("cosine", "sparse")]:
            with self.subTest(metrica=metrica, tipo=tipo):
                self.descripcion.metric = metrica
                self.descripcion.vector_type = tipo
                with self.assertRaisesRegex(ValueError, "cosine"):
                    verificacion.preparar_indice_pinecone()

    def test_rechaza_indice_que_aun_no_esta_listo(self) -> None:
        """Evita continuar con inferencia y carga mientras el índice no está listo."""
        self.cliente.has_index.return_value = True
        self.descripcion.status.ready = False
        with self.assertRaisesRegex(ValueError, "no está listo"):
            verificacion.preparar_indice_pinecone()

    def test_host_explicito_no_crea_ni_busca_por_nombre(self) -> None:
        """Un host del instructor tiene prioridad sobre el nombre por defecto."""
        with patch.dict(os.environ, {"PINECONE_INDEX_HOST": self.host_indice}):
            verificacion.preparar_indice_pinecone()
            self.assertEqual(common.obtener_host_indice(), self.host_indice)
        self.cliente.has_index.assert_not_called()
        self.cliente.create_index.assert_not_called()
        self.cliente.describe_index.assert_not_called()


if __name__ == "__main__":
    unittest.main()
