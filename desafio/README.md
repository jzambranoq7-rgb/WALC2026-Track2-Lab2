# Desafío de integración

El laboratorio termina con un RAG de un solo turno y embeddings gestionados.
En este desafío, tu grupo añadirá dos módulos obligatorios a ese recorrido:

1. **Embeddings locales** con `embeddinggemma:300m` y pgvector en PostgreSQL.
2. **Memoria conversacional** con PostgreSQL: preferencia por usuario, hilos y mensajes.

El corpus ya está escrito en PDF. No se pide redactar documentos nuevos. Usa el
entorno Docker del laboratorio, el corpus de la Universidad del Valle Andino y un namespace
asignado al grupo. Pueden apoyarse en IA para escribir el código; el código del
laboratorio es el punto de partida.

## Punto de partida

- `conocimiento/` contiene nueve PDF y `catalogo.json`. Revisa los cortes de
  `3-preparar.py` y elige dos preguntas: una con evidencia y una sin ella.
- El índice gestionado de 1024 y el namespace del grupo ya funcionan.
- PostgreSQL estándar ya contiene `documentos` y `fragmentos`. El grupo debe
  instalar y activar pgvector; el laboratorio no lo entrega configurado.
  El módulo A añadirá una tabla de vectores relacionada con los IDs.
- `ollama` debe tener `qwen2.5:3b` y `embeddinggemma:300m`.
- Usa Git para conservar los cambios de código. No incluyas `.env` en la entrega.

Variables previstas para el módulo local:

```text
EMBED_LOCAL=embeddinggemma:300m
EMBED_LOCAL_DIM=768
```

## Módulo A — Embeddings locales

Requisitos mínimos:

1. Instala pgvector en el servicio PostgreSQL y activa la extensión en la base
   del laboratorio. Conserva los documentos existentes. Añade una tabla `embeddings_locales` con `fragmento_id` como clave primaria y
   foránea a `fragmentos(id)`, y una columna `embedding vector(768)`. La tabla de
   fragmentos y el texto documental ya existen; no los dupliques.
2. Representa los fragmentos con `embeddinggemma:300m` y guarda sus vectores en
   esa tabla. Comprueba que cada vector tenga 768 dimensiones. No sobrescribas
   los registros de Pinecone: conservan el recorrido gestionado para comparar.
3. Representa la consulta con el mismo modelo local y consulta el top-3 ordenando
   por distancia coseno (`<=>`). Haz JOIN con `fragmentos` y `documentos` para
   recuperar el texto, página, sección y enlace al PDF original.
4. Compara, para una misma pregunta, los tres fragmentos del modelo gestionado y
   los tres del modelo local. Anota qué cambia en el orden y en el texto.

La consulta y los documentos deben usar el mismo modelo local. No alcanza con
cambiar la dimensión: el vector de la consulta también cambia. Para este corpus
pequeño basta una búsqueda exacta en pgvector; un índice aproximado es opcional.

**Aceptación:** cada fragmento tiene un vector persistido; la consulta SQL devuelve
fragmentos y referencias a sus PDF; la comparación explica modelo, dimensión,
`passage`/`query` en Pinecone y distancia coseno en pgvector. Comprueba que repetir
la indexación actualice los vectores en lugar de duplicarlos.

## Módulo B — Memoria conversacional

Implementa una memoria explícita con tablas nuevas en el PostgreSQL del
laboratorio. Como mínimo:

```text
perfiles(usuario TEXT PRIMARY KEY, preferencia TEXT NOT NULL)
hilos(usuario TEXT, hilo TEXT, PRIMARY KEY (usuario, hilo))
mensajes(id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
         usuario TEXT, hilo TEXT,
         rol TEXT CHECK (rol IN ('user','assistant')),
         contenido TEXT,
         FOREIGN KEY (usuario, hilo) REFERENCES hilos(usuario, hilo))
```

Requisitos:

1. Guarda una preferencia de presentación para una persona ficticia. Solo orienta
   el formato; no concede permisos ni cambia los hechos.
2. Guarda los turnos aceptados de una conversación. Una respuesta `[RECHAZADO]`
   no se guarda.
3. Recupera como máximo los últimos cuatro mensajes del hilo y envíalos al modelo
   junto con la pregunta y los fragmentos actuales.
4. Una pregunta de seguimiento como «¿Y en qué plazo se devuelve?» debe recuperar
   usando la pregunta anterior y la actual. Imprime la consulta de recuperación
   para que se pueda revisar.
5. Abre otro hilo para la misma persona: conserva la preferencia, pero no los
   mensajes. Abre el mismo hilo después de cerrar Python: los mensajes siguen.
6. Separa dos usuarios con el mismo nombre de hilo.

**Aceptación:** una traza muestra preferencia, últimos mensajes y fragmentos; otra
prueba muestra la persistencia tras reiniciar el proceso; otra muestra que dos
usuarios no comparten mensajes. Las tablas y los argumentos `--usuario`/`--hilo` son
didácticos, no autenticación.

## Evidencias y explicación

Entrega:

- Una respuesta con evidencia, con documento, versión, página, sección y cita.
- Una pregunta sin evidencia suficiente y la salida del sistema.
- La comparación de la política v1 y v2, o de los dos modelos de embeddings.
- Dos trazas: una del módulo A y una del módulo B.
- Una explicación breve de qué comprobó el código y qué revisó una persona.

No incluyas claves, `.env` ni datos de personas reales.

## Criterio de revisión

Otro grupo debe poder reconstruir el origen de cada afirmación con documento,
versión, página y sección. Debe distinguir un error del servicio, una ausencia de
resultados y vecinos que no responden la pregunta. También debe explicar por qué
un índice de 768 no sirve para vectores de 1024 y por qué la memoria no es una
fuente de hechos. No se exige que el modelo siempre obedezca; se exige detectar y
explicar los fallos observados.

## Retos con documentación

Tres retos cierran la sesión. El primero completa el módulo A; los otros dos son
ampliaciones para quien termine antes. Cada uno parte de una fuente que se puede
leer mientras se implementa.

1. **pgvector.** Instala la extensión, guarda `vector(768)` y ordena por
   distancia coseno con `<=>`. Documentación:
   [pgvector](https://github.com/pgvector/pgvector).
2. **Contextual Retrieval.** Añade una frase de contexto del documento a cada
   fragmento antes de representarlo y compara el resultado con el corte actual.
   Documentación:
   [Anthropic, Introducing Contextual Retrieval](https://www.anthropic.com/research/contextual-retrieval).
3. **Memoria entre conversaciones.** Guarda preferencias y hechos fuera del hilo
   y recupéralos en una conversación nueva. Documentación:
   [LangChain, Memory](https://docs.langchain.com/oss/python/concepts/memory).

Se ejecutan en el entorno del laboratorio. Conserva el comando, la traza y una
conclusión breve de cada uno; el corpus no cambia.
