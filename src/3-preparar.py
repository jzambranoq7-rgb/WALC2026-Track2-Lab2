"""Extrae texto de los PDF y lo divide en fragmentos con procedencia.

Un PDF guarda páginas y posiciones, no encabezados semánticos. Este corpus usa
encabezados en mayúsculas para que el extractor pueda reconstruirlos. Es una
heurística del material: en otro PDF habría que revisar fuentes, tamaños o usar
un extractor con información de diseño.
"""

import argparse
import json
import re
from collections.abc import Iterator
from importlib import import_module
from pathlib import Path
from typing import Any
from urllib.parse import quote

from pypdf import PdfReader

# import_module permite cargar el archivo numerado, cuyo nombre contiene un guion.
common = import_module("1-common")
MAX_CARACTERES = 800  # Unidad explícita. No mide tokens.
PATRON_PIE_PAGINA = re.compile(
    r"^Universidad del Valle Andino · Material ficticio$|^\d+$"
)
PATRON_ENCABEZADO = re.compile(r"^¿?[A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ0-9 ·,./()%-]{3,85}\??$")


def dividir_texto(texto: str, limite: int = MAX_CARACTERES) -> list[str]:
    """Corta un texto por espacios, sin superar el límite de caracteres.

    Si no hay un espacio en la segunda mitad del tramo, corta en el límite.
    Así también puede dividir una palabra muy larga. No añade solapamiento.
    """
    if limite < 50:
        raise ValueError("El tamaño mínimo es 50 caracteres.")
    texto_pendiente = texto.strip()
    partes = []
    while len(texto_pendiente) > limite:
        posicion_corte = texto_pendiente.rfind(" ", 0, limite + 1)
        if posicion_corte < limite // 2:
            posicion_corte = limite
        partes.append(texto_pendiente[:posicion_corte].strip())
        texto_pendiente = texto_pendiente[posicion_corte:].strip()
    if texto_pendiente:
        partes.append(texto_pendiente)
    return partes


def normalizar_espacios(linea: str) -> str:
    """Sustituye espacios repetidos por uno y elimina los de los extremos."""
    return re.sub(r"\s+", " ", linea).strip()


def es_encabezado(linea: str) -> bool:
    """Reconoce los encabezados de sección de este corpus.

    Excluye identificadores como ABC-14: también están en mayúsculas, pero no son
    encabezados. Un PDF real exigiría revisar la fuente o el tamaño de letra.
    """
    if not PATRON_ENCABEZADO.fullmatch(linea):
        return False
    if re.fullmatch(r"[A-Z0-9]+(?:-[A-Z0-9]+)+", linea):
        return False
    cantidad_letras = 0
    for caracter in linea:
        if caracter.isalpha():
            cantidad_letras += 1
    return cantidad_letras >= 4


def extraer_paginas(ruta: Path) -> Iterator[tuple[int, str]]:
    """Entrega número y texto por página; usa texto vacío si no puede extraerlo.

    No realiza OCR. La numeración empieza en 1 para localizar el origen en el PDF.
    """
    lector = PdfReader(str(ruta))
    for numero_pagina, pagina in enumerate(lector.pages, start=1):
        texto_extraido = pagina.extract_text() or ""
        yield numero_pagina, texto_extraido


def extraer_secciones(ruta: Path) -> Iterator[dict[str, Any]]:
    """Agrupa el texto entre encabezados y descarta los pies repetidos.

    Si una sección continúa en otra página, conserva la página donde empezó.
    El texto anterior al primer encabezado no se incluye en las secciones.
    """
    titulo_seccion = None
    pagina_inicio = None
    lineas_seccion = []
    for numero_pagina, texto_pagina in extraer_paginas(ruta):
        for linea_original in texto_pagina.splitlines():
            linea = normalizar_espacios(linea_original)
            if not linea or PATRON_PIE_PAGINA.fullmatch(linea):
                continue
            if es_encabezado(linea):
                # Un nuevo encabezado cierra la sección anterior, si tenía texto.
                if titulo_seccion and lineas_seccion:
                    yield {
                        "seccion": titulo_seccion,
                        "pagina": pagina_inicio,
                        "texto": " ".join(lineas_seccion),
                    }
                titulo_seccion = linea
                pagina_inicio = numero_pagina
                lineas_seccion = []
            elif titulo_seccion:
                lineas_seccion.append(linea)

    # La última sección no tiene otro encabezado que provoque su entrega.
    if titulo_seccion and lineas_seccion:
        yield {
            "seccion": titulo_seccion,
            "pagina": pagina_inicio,
            "texto": " ".join(lineas_seccion),
        }


def preparar_documento(ruta_pdf: Path, ficha_documento: dict[str, Any]) -> list[dict[str, Any]]:
    """Extrae y divide un PDF concreto, sin guardarlo ni llamar a un modelo.

    Para los PDF del corpus conserva sus secciones. En un PDF nuevo, o si no
    reconoce encabezados, usa cada página como bloque. No realiza OCR sobre documentos escaneados.
    """
    if ruta_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"{ruta_pdf.name} no es un PDF.")
    if not ruta_pdf.is_file():
        raise FileNotFoundError(f"No existe el PDF: {ruta_pdf}")

    bloques = []
    if ficha_documento["tipo"] != "documento":
        # La heurística de encabezados solo se usa en el corpus conocido.
        bloques = list(extraer_secciones(ruta_pdf))
    if not bloques:
        for numero_pagina, texto in extraer_paginas(ruta_pdf):
            if texto.strip():
                bloques.append(
                    {
                        "seccion": f"Página {numero_pagina}",
                        "pagina": numero_pagina,
                        "texto": normalizar_espacios(texto),
                    }
                )
    if not bloques:
        raise ValueError("El PDF no contiene texto extraíble. Puede necesitar OCR.")

    fragmentos = []
    # Codificar el nombre permite IDs ASCII aunque el archivo tenga tildes.
    identificador_documento = quote(ficha_documento["documento"], safe="")
    for numero_seccion, bloque in enumerate(bloques, start=1):
        partes = dividir_texto(bloque["texto"])
        for numero_parte, texto_parte in enumerate(partes, start=1):
            metadatos = {
                **ficha_documento,
                "pagina": bloque["pagina"],
                "seccion": bloque["seccion"],
                "parte": numero_parte,
                "texto": texto_parte,
            }
            identificador = (
                f"{identificador_documento}-v{ficha_documento['version']}-"
                f"seccion{numero_seccion}-parte{numero_parte}"
            )
            fragmentos.append({"id": identificador, "metadata": metadatos})
    return fragmentos


def preparar_fragmentos() -> list[dict[str, Any]]:
    """Prepara todos los PDF del catálogo usando la misma función de un documento."""
    carpeta_conocimiento = common.RAIZ_LABORATORIO / "conocimiento"
    catalogo = json.loads((carpeta_conocimiento / "catalogo.json").read_text(encoding="utf-8"))
    fragmentos = []
    for ficha_documento in catalogo:
        ruta_pdf = carpeta_conocimiento / ficha_documento["archivo"]
        fragmentos.extend(preparar_documento(ruta_pdf, ficha_documento))
    return fragmentos


def ficha_del_documento(ruta_pdf: Path, catalogo: list[dict[str, Any]]) -> dict[str, Any]:
    """Reutiliza la ficha del catálogo o crea metadatos sencillos para un PDF nuevo.

    Coloca el archivo en conocimiento/ para que el enlace permita abrir el original.
    Los metadatos iniciales del documento nuevo se pueden editar aquí en clase.
    """
    carpeta_conocimiento = common.RAIZ_LABORATORIO / "conocimiento"
    try:
        ruta_relativa = ruta_pdf.relative_to(carpeta_conocimiento)
    except ValueError:
        raise ValueError("Copia el PDF dentro de conocimiento/ y pasa esa ruta.") from None
    for ficha in catalogo:
        if ficha["archivo"] == ruta_relativa.as_posix():
            return ficha
    return {
        "archivo": ruta_relativa.as_posix(),
        "documento": ruta_relativa.with_suffix("").as_posix(),
        "titulo": ruta_pdf.stem,
        "version": 1,
        "tipo": "documento",
        "sede": "norte",
        "vigente_desde": "sin fecha indicada",
        "vigente_hasta": "sin fecha indicada",
    }


def preparar_ruta(ruta_entrada: Path) -> dict[str, Any]:
    """Prepara un PDF o todos los PDF de una carpeta, incluidas sus subcarpetas.

    Devuelve datos; no abre PostgreSQL ni llama a Pinecone. El texto completo
    acompaña a los fragmentos para conservar el documento aunque se indexe uno.
    """
    ruta_entrada = ruta_entrada.resolve()
    if ruta_entrada.is_file():
        rutas_pdf = [ruta_entrada]
    elif ruta_entrada.is_dir():
        rutas_pdf = []
        for ruta in sorted(ruta_entrada.rglob("*")):
            if ruta.is_file() and ruta.suffix.lower() == ".pdf":
                rutas_pdf.append(ruta)
    else:
        raise ValueError(f"No existe la ruta: {ruta_entrada}")
    if not rutas_pdf:
        raise ValueError("La carpeta no contiene archivos PDF.")

    ruta_catalogo = common.RAIZ_LABORATORIO / "conocimiento" / "catalogo.json"
    catalogo = json.loads(ruta_catalogo.read_text(encoding="utf-8"))
    documentos = []
    fragmentos = []
    for ruta_pdf in rutas_pdf:
        ficha_documento = ficha_del_documento(ruta_pdf, catalogo)
        fragmentos_documento = preparar_documento(ruta_pdf, ficha_documento)
        textos_documento = []
        for fragmento in fragmentos_documento:
            textos_documento.append(fragmento["metadata"]["texto"])
        documentos.append({**ficha_documento, "texto": "\n\n".join(textos_documento)})
        fragmentos.extend(fragmentos_documento)
    return {"documentos": documentos, "fragmentos": fragmentos}


def main() -> None:
    """Imprime la preparación JSON o la guarda en la ruta elegida con --salida."""
    parser = argparse.ArgumentParser(description="Extrae y fragmenta un PDF o una carpeta.")
    parser.add_argument(
        "ruta",
        type=Path,
        nargs="?",
        default=common.RAIZ_LABORATORIO / "conocimiento",
        help="PDF o carpeta. Sin ruta, prepara todos los PDF de conocimiento/.",
    )
    parser.add_argument(
        "--salida", type=Path, help="Archivo JSON. Sin esta opción, imprime el JSON."
    )
    argumentos = parser.parse_args()
    if argumentos.salida is not None:
        ruta_salida = argumentos.salida.resolve()
        ruta_catalogo = common.RAIZ_LABORATORIO / "conocimiento/catalogo.json"
        if ruta_salida == ruta_catalogo or ruta_salida.suffix.lower() == ".pdf":
            raise ValueError("La salida JSON no debe sobrescribir un PDF ni el catálogo.")
    preparacion = preparar_ruta(argumentos.ruta)
    if argumentos.salida is None:
        print(json.dumps(preparacion, ensure_ascii=False, indent=2))
    else:
        common.guardar_json(argumentos.salida, preparacion)
        print(f"Preparación guardada en {argumentos.salida}")
        print("Documentos:", len(preparacion["documentos"]))
        print("Fragmentos:", len(preparacion["fragmentos"]))


if __name__ == "__main__":
    common.ejecutar(main)
