# Relación con la teoría del día 2

| Concepto | Dónde se observa |
| --- | --- |
| Tipos de información | Documentos, consultas y fragmentos tienen estructuras separadas. |
| Base documental | `documentos` y `fragmentos` se relacionan por documento y versión en PostgreSQL. |
| Preparación documental | `3-preparar.py` recibe un PDF o una carpeta y produce JSON en consola o en un archivo. |
| Chunking | Secciones con límite explícito en caracteres, sin solapamiento. |
| Embeddings | `4-indexar.py` lee el JSON, calcula vectores de 1024 dimensiones y muestra el payload antes de subirlo. |
| Modo de entrada | Los documentos usan `passage`; la consulta usa `query`. |
| Almacenamiento vectorial | Pinecone guarda vectores, IDs y metadatos para filtrar. PostgreSQL conserva el texto. |
| Compatibilidad | Mismo modelo y dimensión al indexar y consultar. La tabla indexacion registra esa configuración. |
| Retriever | `common.buscar` busca IDs en Pinecone y hace JOIN en PostgreSQL para obtener texto y procedencia. |
| Versiones y vigencia | El modelo usa los metadatos para elegir la última versión vigente, salvo petición histórica. |
| RAG de dos pasos | La aplicación recupera antes de generar. El LLM no decide llamar una herramienta. |
| Evidencia ausente | Abstención sin LLM cuando el filtro no devuelve fragmentos. |
| Vecinos insuficientes | El documento de constancias describe la solicitud, pero no el plazo de emisión. |
| Trazabilidad | Consulta, filtros, contexto, salida y citas en la última traza. |
| Memoria conversacional | Fuera del laboratorio; se implementa en el desafío. |
| Embeddings locales | Fuera del laboratorio; se implementan en el desafío con `embeddinggemma:300m`. |

## Alcance de esta implementación

No implementa todos los componentes del catálogo teórico. No usa LangGraph,
reranking, búsqueda híbrida, OCR, RAG agéntico ni deducción automática de permisos.
El laboratorio no guarda perfiles, hilos ni mensajes: esa parte se trabaja en el
desafío. La extracción de PDF es una heurística sobre un corpus conocido; no es un
extractor universal de documentos corporativos.

Los namespaces separan las pruebas, pero no constituyen un sistema de autorización.
Se conserva la sede como metadato y se usa material ficticio. En una aplicación real, el servidor tendría
que identificar a la persona y aplicar sus permisos.

## Qué permanece y dónde

| Estado | Ubicación | Sobrevive a `docker compose down` |
| --- | --- | --- |
| Modelo generativo | Volumen `ollama_data` del proyecto | Sí, sin `-v`. |
| Documentos, fragmentos y estado de indexación | Volumen `postgres_data`, PostgreSQL | Sí, sin `-v`. |
| Preparación y payload de vectores | Archivos elegidos con `--salida`, por ejemplo en `resultados/` | Sí, si se guardan en una carpeta montada. |
| Última traza | `resultados/ultima-respuesta.json` | Sí, pero la siguiente consulta la reemplaza. |
| Vectores, IDs y filtros | Pinecone externo | Sí, independiente de Docker. |
| Variables Python | Proceso del script | No. |

## Datos que cruzan la red

El modelo generativo se ejecuta en Ollama dentro de Docker. Pinecone Inference
recibe el texto de los documentos y de la consulta para calcular los embeddings.
Pinecone recibe además vectores, IDs y metadatos de filtrado durante la carga.
Los textos y la relación con los PDF originales se leen desde PostgreSQL.
Este diseño usa embeddings gestionados y no calcula vectores en el equipo.

El texto de los documentos no es anónimo solo por ser ficticio: en una aplicación
real puede contener información sensible. Solo se incluyen datos de práctica.
