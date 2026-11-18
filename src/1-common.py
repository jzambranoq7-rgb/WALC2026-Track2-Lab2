"""Configuración y operaciones compartidas por los ejercicios del día 2.

Ollama genera respuestas localmente. Pinecone Inference calcula los embeddings
con un modelo gestionado. La memoria conversacional y los embeddings locales
quedan fuera de este recorrido y se trabajan en el desafío.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import quote

if TYPE_CHECKING:
    from ollama import Client
    from pinecone import Pinecone
    from psycopg import Connection

RAIZ_LABORATORIO = Path(__file__).resolve().parents[1]
DIRECTORIO_RESULTADOS = Path(os.getenv("RESULTS_DIR", RAIZ_LABORATORIO / "resultados"))
MODELO_GENERATIVO = os.getenv("MODEL", "qwen2.5:3b")
MODELO_EMBEDDINGS = os.getenv("EMBED_MODEL", "multilingual-e5-large")
DIMENSION_EMBEDDINGS = int(os.getenv("EMBED_DIM", "1024"))
NOMBRE_INDICE_PINECONE = os.getenv("PINECONE_INDEX_NAME", "walc-lab-dia-2").strip()


def guardar_json(ruta: Path, contenido: Any) -> None:
    """Guarda datos JSON sin dejar un archivo final escrito parcialmente.

    Primero escribe un temporal en la misma carpeta y después lo renombra.
    El contenido debe poder serializarse a JSON.
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta_temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    texto_json = json.dumps(contenido, ensure_ascii=False, indent=2)
    ruta_temporal.write_text(texto_json, encoding="utf-8")
    ruta_temporal.replace(ruta)


def leer_json(ruta: Path) -> Any:
    """Lee un JSON generado por una etapa anterior del laboratorio.

    Se utiliza para inspeccionar las trazas de respuesta guardadas en resultados/.
    """
    if not ruta.exists():
        raise ValueError(f"Falta {ruta.name}. Sigue el orden del README.")
    texto_json = ruta.read_text(encoding="utf-8")
    return json.loads(texto_json)


def crear_cliente_ollama() -> Client:
    """Conecta con Ollama en la red de Compose, con 180 segundos de espera."""
    from ollama import Client

    host = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    return Client(host=host, timeout=180)


def crear_cliente_pinecone() -> Pinecone:
    """Crea el cliente; la clave solo se envía a la API de Pinecone por HTTPS."""
    from pinecone import Pinecone

    clave_api = os.getenv("PINECONE_API_KEY", "").strip()
    if not clave_api:
        raise ValueError("Configura PINECONE_API_KEY en .env y recrea app.")
    return Pinecone(api_key=clave_api)


def calcular_embeddings(
    textos: list[str],
    uso: Literal["passage", "query"],
) -> list[list[float]]:
    """Calcula un vector por texto mediante el modelo gestionado.

    ``passage`` representa documentos y ``query`` representa consultas. Un
    modelo asimétrico puede producir vectores distintos según ese uso.
    ``truncate="NONE"`` rechaza textos demasiado largos en vez de recortarlos
    en silencio. Se comprueban la cantidad y la dimensión de los vectores.
    """
    if uso not in ("passage", "query"):
        raise ValueError("uso debe ser 'passage' o 'query'.")
    if isinstance(textos, str) or not textos:
        raise ValueError("embedding espera una lista de textos no vacía.")

    cliente_pinecone = crear_cliente_pinecone()
    respuesta = cliente_pinecone.inference.embed(
        model=MODELO_EMBEDDINGS,
        inputs=textos,
        parameters={"input_type": uso, "truncate": "NONE"},
    )
    vectores = []
    for resultado in respuesta:
        vectores.append(resultado.values)

    if len(vectores) != len(textos):
        raise ValueError("Faltan vectores devueltos por la inferencia.")
    for vector in vectores:
        if len(vector) != DIMENSION_EMBEDDINGS:
            raise ValueError("Dimensión incompatible. Revisa EMBED_MODEL.")
    return vectores


def obtener_host_indice() -> str:
    """Usa el host explícito o consulta el índice por su nombre en Pinecone.

    Resolverlo por nombre evita copiar el host al .env tras crear el índice.
    El índice debe haberse preparado antes con 2-check_servicios.py.
    """
    host_indice = os.getenv("PINECONE_INDEX_HOST", "").strip().rstrip("/")
    if not host_indice:
        cliente_pinecone = crear_cliente_pinecone()
        descripcion = cliente_pinecone.describe_index(name=NOMBRE_INDICE_PINECONE)
        host_indice = descripcion.host.rstrip("/")
    if not re.fullmatch(r"https://[a-zA-Z0-9.-]+\.pinecone\.io", host_indice):
        raise ValueError("El host debe ser la URL HTTPS del índice en pinecone.io, sin rutas.")
    return host_indice


def conectar_indice() -> Any:
    """Abre el índice preparado por 2-check_servicios.py; no crea ni elimina recursos.

    Valida el host antes de enviarle la clave. El objeto devuelto es el cliente
    de datos del SDK de Pinecone, con métodos query, upsert y fetch.
    """
    host_indice = obtener_host_indice()
    cliente_pinecone = crear_cliente_pinecone()
    return cliente_pinecone.index(host=host_indice)


def comprobar_dimension_indice(indice: Any) -> Any:
    """Verifica que el índice admita los vectores y devuelve sus estadísticas."""
    estadisticas = indice.describe_index_stats()
    if estadisticas.dimension != DIMENSION_EMBEDDINGS:
        raise ValueError(
            f"Índice de {estadisticas.dimension} dimensiones y embeddings de {DIMENSION_EMBEDDINGS}."
        )
    return estadisticas


def conectar_postgres() -> Connection[dict[str, Any]]:
    """Abre PostgreSQL con las variables PG* inyectadas por Compose.

    El bloque with cierra la conexión y confirma la transacción si no hay error.
    Las filas se leen como diccionarios para acceder por nombres de columna.
    """
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(row_factory=dict_row, connect_timeout=10)


def guardar_corpus(catalogo: list[dict[str, Any]], fragmentos: list[dict[str, Any]]) -> None:
    """Guarda o actualiza los documentos recibidos dentro de una transacción.

    Se llama al indexar, después de calcular los vectores. Invalida el estado
    hasta que Pinecone confirme la carga. No elimina otros fragmentos.
    Conserva en documentos el texto limpio y en fragmentos sus cortes y páginas.
    Los PDF originales permanecen en conocimiento/.
    """
    with conectar_postgres() as conexion:
        conexion.execute("DELETE FROM indexacion")
        for documento in catalogo:
            textos_documento = []
            for fragmento in fragmentos:
                metadatos = fragmento["metadata"]
                if (
                    metadatos["documento"] == documento["documento"]
                    and metadatos["version"] == documento["version"]
                ):
                    textos_documento.append(metadatos["texto"])
            conexion.execute(
                """INSERT INTO documentos
                   (documento, version, titulo, archivo, tipo, sede,
                    vigente_desde, vigente_hasta, texto)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (documento, version) DO UPDATE
                   SET titulo = EXCLUDED.titulo, archivo = EXCLUDED.archivo,
                       tipo = EXCLUDED.tipo, sede = EXCLUDED.sede,
                       vigente_desde = EXCLUDED.vigente_desde,
                       vigente_hasta = EXCLUDED.vigente_hasta, texto = EXCLUDED.texto""",
                (
                    documento["documento"],
                    documento["version"],
                    documento["titulo"],
                    documento["archivo"],
                    documento["tipo"],
                    documento["sede"],
                    documento["vigente_desde"],
                    documento["vigente_hasta"],
                    documento.get("texto", "\n\n".join(textos_documento)),
                ),
            )
        for fragmento in fragmentos:
            metadatos = fragmento["metadata"]
            conexion.execute(
                """INSERT INTO fragmentos
                   (id, documento, version, pagina, seccion, parte, texto)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE
                   SET documento = EXCLUDED.documento, version = EXCLUDED.version,
                       pagina = EXCLUDED.pagina, seccion = EXCLUDED.seccion,
                       parte = EXCLUDED.parte, texto = EXCLUDED.texto""",
                (
                    fragmento["id"],
                    metadatos["documento"],
                    metadatos["version"],
                    metadatos["pagina"],
                    metadatos["seccion"],
                    metadatos["parte"],
                    metadatos["texto"],
                ),
            )


def cargar_fragmentos(identificadores: list[str] | None = None) -> list[dict[str, Any]]:
    """Recupera texto y procedencia mediante un JOIN de fragmentos y documentos.

    Sin IDs, lee todos los fragmentos almacenados. Con IDs, lee los resultados de
    Pinecone. Una lista vacía no lee toda la base. Los parámetros SQL van aparte
    del texto de la consulta, sin interpolarlos en el SQL.
    """
    if identificadores == []:
        return []
    consulta = """SELECT f.id, f.pagina, f.seccion, f.parte, f.texto,
                        d.documento, d.version, d.titulo, d.archivo, d.tipo,
                        d.sede, d.vigente_desde, d.vigente_hasta
                 FROM fragmentos AS f
                 JOIN documentos AS d USING (documento, version)"""
    parametros = ()
    if identificadores is not None:
        consulta += " WHERE f.id = ANY(%s)"
        parametros = (identificadores,)
    consulta += " ORDER BY f.id"
    with conectar_postgres() as conexion:
        filas = conexion.execute(consulta, parametros).fetchall()
    fragmentos = []
    for fila in filas:
        identificador = fila.pop("id")
        fragmentos.append({"id": identificador, "metadata": fila})
    return fragmentos


def obtener_namespace() -> str:
    """Lee el namespace fijo del grupo. No depende del contenido de los PDF."""
    namespace = os.getenv("PINECONE_NAMESPACE", "grupo-01")
    if not re.fullmatch(r"[a-z0-9-]{1,40}", namespace):
        raise ValueError("PINECONE_NAMESPACE debe tener 1–40 letras minúsculas, números o guiones.")
    return namespace


def registrar_indexacion(namespace: str, host: str) -> None:
    """Marca en PostgreSQL que terminó la carga del corpus para este grupo."""
    with conectar_postgres() as conexion:
        conexion.execute(
            """INSERT INTO indexacion (namespace, host, modelo, dimension)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (namespace) DO UPDATE
               SET host = EXCLUDED.host, modelo = EXCLUDED.modelo,
                   dimension = EXCLUDED.dimension""",
            (namespace, host, MODELO_EMBEDDINGS, DIMENSION_EMBEDDINGS),
        )


def comprobar_indexacion(namespace: str, host: str) -> None:
    """Exige una carga terminada y una configuración compatible con sus vectores.

    No vuelve a abrir los PDF. Si editas un PDF debes ejecutar explícitamente
    los pasos de preparación e indexación.
    """
    with conectar_postgres() as conexion:
        estado = conexion.execute(
            "SELECT host, modelo, dimension FROM indexacion WHERE namespace = %s",
            (namespace,),
        ).fetchone()
    if estado is None:
        raise ValueError(
            "Falta una carga terminada. Ejecuta 4-indexar.py con el archivo de fragmentos."
        )
    if (
        estado["host"] != host
        or estado["modelo"] != MODELO_EMBEDDINGS
        or estado["dimension"] != DIMENSION_EMBEDDINGS
    ):
        raise ValueError(
            "La configuración cambió. Indexa el archivo completo en un namespace nuevo."
        )


def enlace_documento(archivo: str, pagina: int) -> str:
    """Devuelve un enlace al PDF original servido por app en el equipo del alumno."""
    url_base = os.getenv("DOCUMENTOS_URL", "http://localhost:8002").rstrip("/")
    return f"{url_base}/{quote(archivo)}#page={pagina}"


def buscar(
    pregunta: str,
    documento: str | None = None,
    tipo: str | None = None,
    top_k: int = 3,
) -> dict[str, Any]:
    """Busca en Pinecone y recupera el texto y su procedencia desde PostgreSQL.

    Conserva las versiones recuperadas: el modelo elegirá según sus metadatos.
    Los filtros de inspección se combinan con AND. La puntuación expresa similitud,
    no la probabilidad de que el contenido permita responder correctamente.
    """
    if not 1 <= top_k <= 10:
        raise ValueError("top_k debe estar entre 1 y 10.")

    # 1. Comprobar que se ejecutó la indexación, sin reprocesar los PDF.
    namespace = obtener_namespace()
    comprobar_indexacion(namespace, obtener_host_indice())

    # 2. Aplicar solo los filtros de inspección solicitados por el usuario.
    condiciones = []
    if documento:
        condiciones.append({"documento": {"$eq": documento}})
    if tipo:
        condiciones.append({"tipo": {"$eq": tipo}})
    filtro = None
    if condiciones:
        filtro = {"$and": condiciones}

    # 3. Representar la pregunta como consulta y recuperar vecinos del índice.
    vector_consulta = calcular_embeddings([pregunta], "query")[0]
    indice = conectar_indice()
    comprobar_dimension_indice(indice)
    resultado = indice.query(
        namespace=namespace,
        vector=vector_consulta,
        top_k=top_k,
        include_metadata=False,
        filter=filtro,
    )

    # 4. Pinecone devuelve IDs y puntuaciones; el texto se lee de PostgreSQL.
    identificadores = []
    for coincidencia in resultado.matches:
        identificadores.append(coincidencia.id)
    fragmentos = cargar_fragmentos(identificadores)
    fragmentos_por_id = {}
    for fragmento in fragmentos:
        fragmentos_por_id[fragmento["id"]] = fragmento["metadata"]

    fragmentos_encontrados = []
    for coincidencia in resultado.matches:
        fuente = fragmentos_por_id.get(coincidencia.id)
        if fuente is None:
            raise ValueError(
                "Un ID de Pinecone no existe en PostgreSQL. Indexa el archivo de fragmentos correspondiente."
            )
        fragmento_encontrado = {
            "id": coincidencia.id,
            "score": coincidencia.score,
            **fuente,
            "url": enlace_documento(fuente["archivo"], fuente["pagina"]),
        }
        fragmentos_encontrados.append(fragmento_encontrado)

    return {
        "consulta": pregunta,
        "namespace": namespace,
        "filtro": filtro,
        "fragmentos": fragmentos_encontrados,
    }


def ejecutar(funcion: Callable[[], None]) -> None:
    """Ejecuta un ejercicio y presenta errores sin volcar respuestas externas.

    Una interrupción termina la sesión. Los errores previstos se muestran con
    su mensaje; los demás, solo con su tipo, para no imprimir claves ni cuerpos
    de error de los servicios. SystemExit conserva el código elegido por el RAG.
    """
    try:
        funcion()
    except (KeyboardInterrupt, EOFError):
        print("\nFin.")
    except Exception as error:  # noqa: BLE001 - No exponer cuerpos de error externos.
        if isinstance(error, (ValueError, FileNotFoundError)):
            print(f"[error] {error}", file=sys.stderr)
        else:
            print(f"[error] {type(error).__name__}. Consulta docs/diagnostico.md.", file=sys.stderr)
        sys.exit(1)
