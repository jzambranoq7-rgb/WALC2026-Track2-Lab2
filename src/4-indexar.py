"""Lee fragmentos JSON, muestra sus embeddings y los guarda en Pinecone.

La inferencia y la carga son dos llamadas distintas, visibles en un mismo script.
PostgreSQL conserva el texto; Pinecone recibe IDs, vectores y metadatos de filtro.
"""

import argparse
import json
import time
from importlib import import_module
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

common = import_module("1-common")


class FichaDocumento(BaseModel):
    """Metadatos que identifican el documento original y su vigencia."""

    model_config = ConfigDict(extra="forbid")
    documento: str = Field(min_length=1)
    version: int = Field(ge=1, strict=True)
    archivo: str = Field(min_length=1)
    titulo: str = Field(min_length=1)
    tipo: str = Field(min_length=1)
    sede: str = Field(min_length=1)
    vigente_desde: str
    vigente_hasta: str


class DocumentoPreparado(FichaDocumento):
    """Texto completo extraído, necesario aunque se elija un solo fragmento."""

    texto: str = Field(min_length=1)


class MetadatosFragmento(FichaDocumento):
    """Texto de un corte y ubicación desde la que se podrá abrir el PDF."""

    pagina: int = Field(ge=1, strict=True)
    seccion: str = Field(min_length=1)
    parte: int = Field(ge=1, strict=True)
    texto: str = Field(min_length=1)


class FragmentoPreparado(BaseModel):
    """Un ID estable asociado con el texto que se convertirá en un vector."""

    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    metadata: MetadatosFragmento


class ArchivoPreparacion(BaseModel):
    """Contrato JSON entre 3-preparar.py y este indexador."""

    model_config = ConfigDict(extra="forbid")
    documentos: list[DocumentoPreparado] = Field(min_length=1)
    fragmentos: list[FragmentoPreparado] = Field(min_length=1)


def leer_preparacion(ruta: Path) -> dict[str, Any]:
    """Comprueba estructura, IDs y procedencia antes de llamar a servicios."""
    preparacion = ArchivoPreparacion.model_validate(common.leer_json(ruta))
    documentos_por_clave = {}
    for documento in preparacion.documentos:
        clave_documento = (documento.documento, documento.version)
        if clave_documento in documentos_por_clave:
            raise ValueError("Hay documentos y versiones repetidos en el archivo.")
        documentos_por_clave[clave_documento] = documento

    identificadores = set()
    for fragmento in preparacion.fragmentos:
        if fragmento.id in identificadores:
            raise ValueError(f"ID de fragmento repetido: {fragmento.id}")
        identificadores.add(fragmento.id)
        metadatos = fragmento.metadata
        documento = documentos_por_clave.get((metadatos.documento, metadatos.version))
        if documento is None:
            raise ValueError(f"Falta el documento original del fragmento {fragmento.id}.")
        # Los campos compartidos deben apuntar al mismo original, no a otro PDF.
        for campo in FichaDocumento.model_fields:
            if getattr(documento, campo) != getattr(metadatos, campo):
                raise ValueError(f"El metadato {campo} no coincide en {fragmento.id}.")
    return preparacion.model_dump()


def construir_registros(
    fragmentos: list[dict[str, Any]], vectores: list[list[float]]
) -> list[dict[str, Any]]:
    """Empareja cada texto con su vector para construir el payload de upsert."""
    if len(fragmentos) != len(vectores):
        raise ValueError("Debe haber exactamente un vector por fragmento.")
    registros = []
    for fragmento, vector in zip(fragmentos, vectores):
        metadatos = fragmento["metadata"]
        registros.append(
            {
                "id": fragmento["id"],
                "values": vector,
                # El texto, la página y la referencia al PDF se guardan en PostgreSQL.
                "metadata": {
                    "documento": metadatos["documento"],
                    "version": metadatos["version"],
                    "tipo": metadatos["tipo"],
                    "sede": metadatos["sede"],
                },
            }
        )
    return registros


def esperar_registros_visibles(
    indice: Any,
    identificadores: list[str],
    namespace: str,
    segundos: float = 90,
) -> None:
    """Espera hasta recuperar los IDs enviados; upsert tiene consistencia eventual.

    Consultar por ID no demuestra la relevancia de una búsqueda posterior.
    """
    instante_limite = time.monotonic() + segundos
    identificadores_esperados = set(identificadores)
    while time.monotonic() < instante_limite:
        respuesta = indice.fetch(ids=identificadores, namespace=namespace)
        if set(respuesta.vectors) == identificadores_esperados:
            return
        time.sleep(2)
    raise ValueError("La carga aún no es visible. Espera y repite 4-indexar.py con el archivo.")


def main() -> None:
    """Calcula, muestra y carga; --solo-ver permite observar antes de persistir."""
    parser = argparse.ArgumentParser(
        description="Calcula embeddings e indexa un archivo de fragmentos."
    )
    parser.add_argument("archivo", type=Path, help="JSON generado por 3-preparar.py.")
    parser.add_argument(
        "--fragmento", action="append", help="ID que se quiere indexar. Se puede repetir."
    )
    parser.add_argument(
        "--salida", type=Path, help="Guarda el payload con los vectores en este JSON."
    )
    parser.add_argument(
        "--solo-ver", action="store_true", help="Calcula y muestra, sin escribir en las bases."
    )
    argumentos = parser.parse_args()
    if (
        argumentos.salida is not None
        and argumentos.salida.resolve() == argumentos.archivo.resolve()
    ):
        raise ValueError("La salida de vectores debe ser distinta del archivo de fragmentos.")

    # 1. Leer los fragmentos del archivo, sin volver a extraer los PDF.
    preparacion = leer_preparacion(argumentos.archivo)
    fragmentos = preparacion["fragmentos"]
    if argumentos.fragmento:
        fragmentos_elegidos = []
        for fragmento in fragmentos:
            if fragmento["id"] in argumentos.fragmento:
                fragmentos_elegidos.append(fragmento)
        identificadores_elegidos = {fragmento["id"] for fragmento in fragmentos_elegidos}
        if set(argumentos.fragmento) != identificadores_elegidos:
            raise ValueError("Algún ID solicitado no existe en el archivo de fragmentos.")
        fragmentos = fragmentos_elegidos

    # 2. Primera llamada: Pinecone Inference convierte cada texto en un embedding.
    textos = []
    for fragmento in fragmentos:
        textos.append(fragmento["metadata"]["texto"])
    vectores = common.calcular_embeddings(textos, "passage")

    # 3. Ver el objeto exacto que se enviará: namespace, IDs, valores y metadatos.
    registros = construir_registros(fragmentos, vectores)
    namespace = common.obtener_namespace()
    peticion_carga = {"namespace": namespace, "vectors": registros}
    if argumentos.salida is None:
        print(json.dumps(peticion_carga, ensure_ascii=False, indent=2), flush=True)
    else:
        common.guardar_json(argumentos.salida, peticion_carga)
        print(f"Payload de Pinecone guardado en {argumentos.salida}", flush=True)
    print("Modelo de embeddings:", common.MODELO_EMBEDDINGS)
    print("Dimensiones por vector:", common.DIMENSION_EMBEDDINGS)
    if argumentos.solo_ver:
        print("Vista previa: se calculó la inferencia; no se escribió en PostgreSQL ni Pinecone.")
        return

    # 4. Conservar los originales completos y los fragmentos elegidos en PostgreSQL.
    indice = common.conectar_indice()
    common.comprobar_dimension_indice(indice)
    documentos = []
    claves_documentos = set()
    for fragmento in fragmentos:
        metadatos = fragmento["metadata"]
        claves_documentos.add((metadatos["documento"], metadatos["version"]))
    for documento in preparacion["documentos"]:
        if (documento["documento"], documento["version"]) in claves_documentos:
            documentos.append(documento)
    common.guardar_corpus(documentos, fragmentos)

    # 5. Segunda llamada: guardar los vectores que acabamos de mostrar.
    indice.upsert(**peticion_carga)
    identificadores = []
    for registro in registros:
        identificadores.append(registro["id"])
    esperar_registros_visibles(indice, identificadores, namespace)
    common.registrar_indexacion(namespace, common.obtener_host_indice())
    print("Carga confirmada en Pinecone. Namespace:", namespace)
    print("Registros visibles por ID:", len(registros))
    print("Documentos y fragmentos guardados en PostgreSQL:", len(documentos), len(fragmentos))
    print("Los IDs enviados se actualizan; los demás registros se conservan.")


if __name__ == "__main__":
    common.ejecutar(main)
