"""Verifica Ollama, prepara el índice de Pinecone y comprueba la inferencia."""

import argparse
import os
from importlib import import_module

common = import_module("1-common")


def preparar_indice_pinecone() -> None:
    """Crea el índice si falta o reutiliza uno compatible, sin borrar datos.

    Con PINECONE_INDEX_HOST se usa directamente el índice del instructor.
    Sin host, se busca por PINECONE_INDEX_NAME y, si no existe, se crea un
    índice serverless denso en la nube y región configuradas. El SDK espera
    hasta 120 segundos a que el índice creado esté listo.
    """
    from pinecone import ServerlessSpec

    if os.getenv("PINECONE_INDEX_HOST", "").strip():
        # El host explícito tiene prioridad. Su dimensión se comprueba en main.
        print("Se usará el índice existente indicado por PINECONE_INDEX_HOST.")
        return

    cliente_pinecone = common.crear_cliente_pinecone()
    nombre_indice = common.NOMBRE_INDICE_PINECONE
    if cliente_pinecone.has_index(nombre_indice):
        descripcion = cliente_pinecone.describe_index(name=nombre_indice)
        print("Índice existente:", nombre_indice)
    else:
        nube = os.getenv("PINECONE_CLOUD", "aws")
        region = os.getenv("PINECONE_REGION", "us-east-1")
        print("Creando índice:", nombre_indice, "en", nube, region)
        descripcion = cliente_pinecone.create_index(
            name=nombre_indice,
            dimension=common.DIMENSION_EMBEDDINGS,
            metric="cosine",
            vector_type="dense",
            spec=ServerlessSpec(cloud=nube, region=region),
            timeout=120,
        )

    # Un nombre coincidente no basta: el índice debe aceptar nuestros vectores.
    if descripcion.dimension != common.DIMENSION_EMBEDDINGS:
        raise ValueError("El índice tiene otra dimensión. Elige otro PINECONE_INDEX_NAME.")
    if descripcion.metric != "cosine" or descripcion.vector_type != "dense":
        raise ValueError("El índice debe ser vectorial denso y usar métrica cosine.")
    if not descripcion.status.ready:
        raise ValueError("El índice aún no está listo. Espera y repite 2-check_servicios.py.")
    print("Host resuelto automáticamente:", common.obtener_host_indice())


def main() -> None:
    """Prueba generación local, prepara el índice y verifica embeddings gestionados.

    --solo-ollama permite comprobar la parte local mientras se prepara Pinecone.
    No certifica que la indexación ni la búsqueda gestionadas estén disponibles.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--solo-ollama", action="store_true")
    argumentos = parser.parse_args()

    cliente_ollama = common.crear_cliente_ollama()
    modelos_descargados = []
    for modelo in cliente_ollama.list().models:
        modelos_descargados.append(modelo.model)
    print("Modelos descargados:", modelos_descargados)
    respuesta = cliente_ollama.chat(
        model=common.MODELO_GENERATIVO,
        messages=[{"role": "user", "content": "Responde hola laboratorio día 2"}],
        options={"temperature": 0, "num_predict": 40},
    )
    print("Respuesta local:", respuesta.message.content)

    if argumentos.solo_ollama:
        print("Pinecone no se verificó. Completa la cuenta antes de indexar.")
        return

    # PostgreSQL almacena documentos; este recorrido no necesita extensiones.
    with common.conectar_postgres() as conexion:
        conexion.execute("SELECT 1").fetchone()
    print("PostgreSQL responde.")

    preparar_indice_pinecone()

    # La inferencia y el índice son operaciones distintas: se comprueban ambas.
    vector_prueba = common.calcular_embeddings(["prueba de conexión"], "query")[0]
    print("Embedding gestionado:", common.MODELO_EMBEDDINGS, "dimensiones:", len(vector_prueba))
    indice = common.conectar_indice()
    estadisticas = common.comprobar_dimension_indice(indice)
    print("Pinecone responde. Dimensiones del índice:", estadisticas.dimension)


if __name__ == "__main__":
    common.ejecutar(main)
