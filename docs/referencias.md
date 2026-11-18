# Referencias técnicas

Documentación de los componentes utilizados en el laboratorio.

- [Ollama, salidas estructuradas](https://docs.ollama.com/capabilities/structured-outputs).
  Esquema JSON y validación de la salida del modelo generativo.
- [Ollama, EmbeddingGemma](https://ollama.com/library/embeddinggemma).
  Modelo local del desafío, no del recorrido principal.
- [Pinecone, Python SDK](https://docs.pinecone.io/reference/sdks/python/overview).
  Correspondencia entre SDK y API. El material fija la interfaz del SDK 10.2.0.
- [Pinecone, inferencia de embeddings](https://docs.pinecone.io/guides/inference/understanding-inference).
  Modelos gestionados, `input_type` y cálculo de vectores sin ejecutar el modelo
  en el equipo.
- [Pinecone, modelo multilingual-e5-large](https://docs.pinecone.io/models/multilingual-e5-large).
  Dimensiones, límite de entrada y parámetros admitidos.
- [Pinecone, creación de índices](https://docs.pinecone.io/guides/index-data/create-an-index).
  Índices para vectores calculados externamente y dimensiones compatibles.
- [Pinecone, carga de registros](https://docs.pinecone.io/guides/index-data/upsert-data).
  Upsert por ID y namespaces.
- [Pinecone, búsqueda semántica](https://docs.pinecone.io/guides/search/semantic-search).
  Consulta por vector y recuperación de metadatos.
- [Pinecone, filtros](https://docs.pinecone.io/guides/search/filter-by-metadata).
  Restricciones por documento, versión, tipo y sede.
- [Pinecone, pruebas y mock](https://docs.pinecone.io/guides/operations/local-development).
  Límites del mock y fin de vida de Pinecone Local.
- [pypdf, extracción de texto](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).
  Lectura de páginas y texto de PDF.
- [PostgreSQL, consultas y JOIN](https://www.postgresql.org/docs/16/tutorial-join.html).
  Relación entre documentos y fragmentos mediante SQL.
- [Psycopg, uso básico](https://www.psycopg.org/psycopg3/docs/basic/usage.html).
  Conexiones, transacciones y parámetros SQL del cliente Python.
- [pgvector](https://github.com/pgvector/pgvector).
  Extensión y operador de distancia coseno para el desafío de vectores locales.
- [Anthropic, Introducing Contextual Retrieval](https://www.anthropic.com/research/contextual-retrieval).
  Contexto del documento añadido a cada fragmento antes de representarlo.
- [LangChain, Memory](https://docs.langchain.com/oss/python/concepts/memory).
  Memoria de corto plazo dentro del hilo y de largo plazo entre conversaciones.

La cobertura sigue la documentación general del track y el guion activo de teoría
del día 2 del repositorio. El formato de ejecución sigue el laboratorio del día 1.
La Universidad del Valle Andino y sus documentos son ficticios.
