"""Comprueba el recorrido archivo → embeddings → payload → bases de datos."""

import copy
import importlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
common = importlib.import_module("1-common")
preparacion = importlib.import_module("3-preparar")
indexacion = importlib.import_module("4-indexar")


class IndexacionDesdeArchivo(unittest.TestCase):
    def setUp(self) -> None:
        """Usa un PDF real y dobles para las llamadas de inferencia y escritura."""
        self.carpeta = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.archivo = self.carpeta / "fragmentos.json"
        ruta_pdf = common.RAIZ_LABORATORIO / "conocimiento/inscripciones.pdf"
        self.preparacion = preparacion.preparar_ruta(ruta_pdf)
        common.guardar_json(self.archivo, self.preparacion)
        self.vectores = []
        for numero in range(len(self.preparacion["fragmentos"])):
            self.vectores.append([float(numero)] * common.DIMENSION_EMBEDDINGS)
        self.indice = Mock()
        self.indice.describe_index_stats.return_value = SimpleNamespace(
            dimension=common.DIMENSION_EMBEDDINGS
        )
        self.calcular = self.enterContext(
            patch.object(common, "calcular_embeddings", return_value=self.vectores)
        )
        self.conectar = self.enterContext(
            patch.object(common, "conectar_indice", return_value=self.indice)
        )
        self.guardar = self.enterContext(patch.object(common, "guardar_corpus"))
        self.registrar = self.enterContext(patch.object(common, "registrar_indexacion"))
        self.esperar = self.enterContext(patch.object(indexacion, "esperar_registros_visibles"))
        self.enterContext(patch.object(common, "obtener_namespace", return_value="grupo-prueba"))
        self.enterContext(
            patch.object(common, "obtener_host_indice", return_value="https://prueba.pinecone.io")
        )
        self.salida = self.enterContext(redirect_stdout(io.StringIO()))

    def ejecutar(self, *opciones: str) -> None:
        """Ejecuta el CLI con el archivo preparado en esta prueba."""
        with patch.object(sys, "argv", ["4-indexar.py", str(self.archivo), *opciones]):
            indexacion.main()

    def test_payload_guardado_es_exactamente_el_enviado(self) -> None:
        """Los números visibles son los que se entregan a upsert, sin recalcularlos."""
        ruta_payload = self.carpeta / "vectores.json"
        self.ejecutar("--salida", str(ruta_payload))
        payload = json.loads(ruta_payload.read_text())
        self.assertEqual(payload, self.indice.upsert.call_args.kwargs)
        self.assertEqual(payload["vectors"][0]["values"], self.vectores[0])
        self.assertNotIn("texto", payload["vectors"][0]["metadata"])
        self.indice.delete.assert_not_called()
        self.guardar.assert_called_once_with(
            self.preparacion["documentos"], self.preparacion["fragmentos"]
        )
        self.registrar.assert_called_once_with("grupo-prueba", "https://prueba.pinecone.io")

    def test_vista_previa_imprime_vectores_sin_escribir_en_bases(self) -> None:
        """La vista previa sí usa inferencia; no conecta a las bases para guardar."""
        self.ejecutar("--solo-ver")
        self.assertIn('"values": [', self.salida.getvalue())
        self.assertIn('"namespace": "grupo-prueba"', self.salida.getvalue())
        self.calcular.assert_called_once()
        self.conectar.assert_not_called()
        self.guardar.assert_not_called()
        self.registrar.assert_not_called()

    def test_indexa_un_fragmento_y_conserva_texto_completo_del_documento(self) -> None:
        """Elegir un ID reduce inferencia y carga, sin recortar el original SQL."""
        fragmento = self.preparacion["fragmentos"][1]
        self.calcular.return_value = [self.vectores[1]]
        self.ejecutar("--fragmento", fragmento["id"])
        self.calcular.assert_called_once_with([fragmento["metadata"]["texto"]], "passage")
        self.guardar.assert_called_once_with(self.preparacion["documentos"], [fragmento])
        self.assertEqual(len(self.indice.upsert.call_args.kwargs["vectors"]), 1)
        self.indice.delete.assert_not_called()

    def test_id_inexistente_se_rechaza_antes_de_pagar_inferencia(self) -> None:
        with self.assertRaisesRegex(ValueError, "no existe"):
            self.ejecutar("--fragmento", "inexistente")
        self.calcular.assert_not_called()
        self.guardar.assert_not_called()

    def test_archivo_sin_procedencia_se_rechaza_antes_de_inferencia(self) -> None:
        datos = copy.deepcopy(self.preparacion)
        datos["fragmentos"][0]["metadata"]["archivo"] = "otro.pdf"
        common.guardar_json(self.archivo, datos)
        with self.assertRaisesRegex(ValueError, "no coincide"):
            self.ejecutar()
        self.calcular.assert_not_called()

    def test_no_sobrescribe_el_archivo_de_entrada(self) -> None:
        with self.assertRaisesRegex(ValueError, "distinta"):
            self.ejecutar("--salida", str(self.archivo))
        self.calcular.assert_not_called()
        self.assertEqual(common.leer_json(self.archivo), self.preparacion)

    def test_fallo_de_carga_no_marca_el_indice_como_listo(self) -> None:
        self.indice.upsert.side_effect = RuntimeError("Carga fallida")
        with self.assertRaises(RuntimeError):
            self.ejecutar()
        self.registrar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
