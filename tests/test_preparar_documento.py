"""Comprueba la lectura de un PDF elegido y la vista previa sin persistencia."""

import importlib
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
common = importlib.import_module("1-common")
preparacion = importlib.import_module("3-preparar")


class PrepararDocumento(unittest.TestCase):
    def setUp(self) -> None:
        """Usa una ruta real del corpus, con su ficha documental."""
        carpeta = common.RAIZ_LABORATORIO / "conocimiento"
        self.ruta_pdf = carpeta / "inscripciones.pdf"
        catalogo = json.loads((carpeta / "catalogo.json").read_text())
        self.ficha = preparacion.ficha_del_documento(self.ruta_pdf, catalogo)

    def test_documento_elegido_no_mezcla_otros_archivos(self) -> None:
        """La ruta determina qué PDF se extrae, sin cargar todo el catálogo."""
        fragmentos = preparacion.preparar_documento(self.ruta_pdf, self.ficha)
        self.assertGreaterEqual(len(fragmentos), 4)
        for fragmento in fragmentos:
            self.assertEqual(fragmento["metadata"]["archivo"], self.ruta_pdf.name)

    def test_pdf_sin_encabezados_se_divide_por_pagina(self) -> None:
        """Un texto corriente no debe desaparecer por no tener títulos en mayúsculas."""
        with (
            patch.object(preparacion, "extraer_secciones", return_value=iter([])),
            patch.object(
                preparacion,
                "extraer_paginas",
                return_value=iter([(1, "un texto sin encabezados.")]),
            ),
        ):
            fragmentos = preparacion.preparar_documento(self.ruta_pdf, self.ficha)
        self.assertEqual(fragmentos[0]["metadata"]["texto"], "un texto sin encabezados.")
        self.assertEqual(fragmentos[0]["metadata"]["pagina"], 1)

    def test_pdf_nuevo_conserva_texto_sin_aplicar_heuristica_del_corpus(self) -> None:
        """Un encabezado casual no debe hacer desaparecer el texto previo."""
        ficha_nueva = {**self.ficha, "tipo": "documento"}
        texto_pagina = "Texto inicial.\nUN TITULO\nTexto final."
        with (
            patch.object(
                preparacion, "extraer_secciones", side_effect=AssertionError("No usar heurística")
            ),
            patch.object(preparacion, "extraer_paginas", return_value=iter([(1, texto_pagina)])),
        ):
            fragmentos = preparacion.preparar_documento(self.ruta_pdf, ficha_nueva)
        self.assertEqual(
            fragmentos[0]["metadata"]["texto"], "Texto inicial. UN TITULO Texto final."
        )

    def test_pdf_sin_texto_no_se_guarda_como_documento_vacio(self) -> None:
        """Los PDF escaneados requieren OCR; se comunica antes de escribir datos."""
        with (
            patch.object(preparacion, "extraer_secciones", return_value=iter([])),
            patch.object(preparacion, "extraer_paginas", return_value=iter([(1, "")])),
            self.assertRaisesRegex(ValueError, "OCR"),
        ):
            preparacion.preparar_documento(self.ruta_pdf, self.ficha)

    def test_sin_salida_imprime_json_y_no_escribe_en_postgres(self) -> None:
        """La salida estándar sirve para leer el contenido o redirigirlo."""
        with (
            patch.object(sys, "argv", ["3-preparar.py", str(self.ruta_pdf)]),
            patch.object(common, "guardar_corpus") as guardar,
            redirect_stdout(io.StringIO()) as salida,
        ):
            preparacion.main()
        guardar.assert_not_called()
        datos = json.loads(salida.getvalue())
        self.assertGreaterEqual(len(datos["fragmentos"]), 4)
        self.assertIn("nombre completo", datos["documentos"][0]["texto"])

    def test_salida_escribe_json_en_la_ruta_elegida(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as carpeta:
            ruta_salida = Path(carpeta) / "subcarpeta/fragmentos.json"
            with (
                patch.object(
                    sys, "argv", ["3-preparar.py", str(self.ruta_pdf), "--salida", str(ruta_salida)]
                ),
                redirect_stdout(io.StringIO()),
            ):
                preparacion.main()
            datos = json.loads(ruta_salida.read_text())
        self.assertGreaterEqual(len(datos["fragmentos"]), 4)

    def test_carpeta_prepara_todos_los_pdf(self) -> None:
        datos = preparacion.preparar_ruta(self.ruta_pdf.parent)
        self.assertEqual(len(datos["documentos"]), 10)
        self.assertGreaterEqual(len(datos["fragmentos"]), 20)

    def test_sin_ruta_prepara_la_carpeta_predeterminada(self) -> None:
        with (
            patch.object(sys, "argv", ["3-preparar.py"]),
            redirect_stdout(io.StringIO()) as salida,
        ):
            preparacion.main()
        datos = json.loads(salida.getvalue())
        self.assertEqual(len(datos["documentos"]), 10)

    def test_carpeta_incluye_pdf_de_subcarpetas(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as carpeta:
            raiz_prueba = Path(carpeta)
            conocimiento = raiz_prueba / "conocimiento"
            subcarpeta = conocimiento / "tema"
            subcarpeta.mkdir(parents=True)
            (conocimiento / "catalogo.json").write_text("[]")
            (subcarpeta / "documento.PDF").write_bytes(self.ruta_pdf.read_bytes())
            with patch.object(common, "RAIZ_LABORATORIO", raiz_prueba):
                datos = preparacion.preparar_ruta(conocimiento)
        self.assertEqual(len(datos["documentos"]), 1)
        self.assertEqual(datos["documentos"][0]["archivo"], "tema/documento.PDF")
        self.assertIn("nombre completo", datos["documentos"][0]["texto"])

    def test_salida_no_puede_sobrescribir_pdf(self) -> None:
        with (
            patch.object(
                sys, "argv", ["3-preparar.py", str(self.ruta_pdf), "--salida", str(self.ruta_pdf)]
            ),
            self.assertRaisesRegex(ValueError, "sobrescribir"),
        ):
            preparacion.main()


if __name__ == "__main__":
    unittest.main()
