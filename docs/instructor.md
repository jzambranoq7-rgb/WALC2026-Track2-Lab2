# Preparación y conducción del laboratorio

## Antes de clase

1. Distribuye `lab-dia-2-paquete.tar` (Linux amd64), prueba su instalación antes de clase y asigna un prefijo `grupo-01`, `grupo-02`, etc.
2. En un proyecto de práctica de Pinecone, ejecuta `src/2-check_servicios.py`
   con Docker Compose. Crea `PINECONE_INDEX_NAME` si falta: índice **vectorial denso**
   para vectores externos de **1024 dimensiones** y métrica cosine. Para crearlo
   usa `PINECONE_CLOUD` y `PINECONE_REGION` (aws/us-east-1 inicialmente). Si ya existe,
   comprueba su compatibilidad y lo reutiliza; los scripts resuelven su host por
   nombre. Puedes distribuir un host existente en `PINECONE_INDEX_HOST` como
   alternativa, sin dar a los alumnos permiso para crear índices. Este material
   fija el SDK Pinecone **10.2.0** y usa `pc.index(host=...)`, `upsert`, `fetch`,
   `query`, `describe_index_stats` e `inference.embed`. No requiere la interfaz de
   índices de documentos ni embeddings integrados.
3. Levanta PostgreSQL con Compose y configura `POSTGRES_PASSWORD` en el .env local.
   La imagen es PostgreSQL estándar. Comprueba que existan las tablas
   `documentos`, `fragmentos` e `indexacion`. Instalar y activar pgvector
   corresponde a los participantes durante el desafío.
4. Comprueba plan, región, límites y acceso antes de clase. La inferencia gestionada
   tiene costo por tokens. No se promete que crear o usar los índices sea gratuito.
   Evita cuentas de producción.
5. Guía el registro o inicio de sesión en Pinecone y la selección del proyecto de
   práctica. Cada alumno crea o recibe una clave autorizada, la copia antes de
   cerrar el diálogo y la guarda localmente como `PINECONE_API_KEY` en `.env`.
   Usa el nombre o el host del índice de 1024, según el acceso asignado.
6. Comprueba que el paquete haya cargado `qwen2.5:3b` y `embeddinggemma:300m`;
   ejecuta `2-check_servicios.py`. Sin paquete, descarga ambos modelos. Usa la
   misma configuración en tu demostración y en los equipos participantes.
7. Ejecuta las pruebas aisladas. Después realiza todo el recorrido con la cuenta
   de práctica y revisa manualmente las citas. Las pruebas con dobles no verifican
   conectividad, consistencia ni relevancia del servicio gestionado.

Pinecone mantiene diferentes generaciones de SDK y API. Este laboratorio fija una
versión concreta para evitar que una instalación futura cambie la interfaz. La
documentación oficial explica la correspondencia. No actualizar dependencias el
día de clase sin repetir la prueba completa.

## Puntos de control durante las dos horas

- Minuto 20. Cada grupo obtiene generación local y un embedding gestionado de 1024;
  confirma que el índice tiene la misma dimensión.
- Minuto 35. Cada grupo elige un PDF por ruta, observa los cortes en consola
  y guarda el JSON con `--salida`. Explica qué hace `pypdf` y el límite de caracteres. Luego
  puede preparar el catálogo completo antes de comparar horarios y trámites.
- Minuto 60. El indexador lee el JSON. Primero muestra el vector de un fragmento
  con `--fragmento ID --solo-ver`. Después carga el archivo completo, muestra el
  payload enviado y confirma los IDs. Registra el estado en `indexacion`.
- Minuto 80. El grupo revisa cómo el modelo usa los metadatos para elegir la política
  vigente y cómo cambia su respuesta al pedir septiembre expresamente. Usa
  `--tipo procedimiento` para inspeccionar la recuperación.
- Minuto 105. El grupo obtiene una respuesta con página y cita, y una abstención
  sobre el plazo de emisión de una constancia.
- Minuto 120. El grupo revisa la traza y explica qué comprobó el código y qué
  revisó leyendo el PDF.

## Preguntas para conducir la práctica

¿Qué dato del fragmento permite localizar su origen? ¿Por qué un vector de consulta
debe usar el mismo modelo y dimensión que el documento? ¿Qué cambia entre la
versión documental y la versión del software? ¿Por qué `input_type` distingue
`passage` de `query`? ¿Puede una cita literal correcta acompañar una conclusión
incorrecta? ¿Qué información del PDF se pierde al extraer solo texto?

## Desafío de 60 minutos

El corpus ya está escrito en PDF; no se pide redactar documentos. El grupo revisa
el catálogo y los cortes, y trabaja dos módulos obligatorios:

- Embeddings locales con `embeddinggemma:300m` y columnas `vector(768)` en PostgreSQL.
- Memoria conversacional con PostgreSQL: perfiles, hilos y mensajes.

Reparto sugerido: 10 minutos para revisar el corpus, 15 para embeddings locales,
20 para memoria, 10 para las dos trazas y 5 para explicar. Los participantes pueden
apoyarse en IA para escribir el código. El instructor comprueba PostgreSQL y el
modelo local antes de empezar. El grupo se encarga de instalar y activar pgvector.

Si el grupo termina antes, la última diapositiva propone tres retos con
documentación: pgvector, Contextual Retrieval y memoria entre conversaciones. Son
ampliaciones del desafío y no consumen el tiempo de los módulos obligatorios.

## Cierre de recursos

`docker compose down` detiene solo los servicios de este laboratorio. No elimina
Pinecone. Cuando finalice el evento, revisa los namespaces asignados a los grupos
y retira únicamente los recursos de práctica que corresponda. El material no incluye
comandos de borrado automático de la cuenta.

## Si no hay cuenta disponible

Puedes realizar el entorno, la extracción de PDF y las pruebas aisladas. La
indexación, la búsqueda y el RAG completo requieren Pinecone configurado. No
presentar dobles ni respuestas guardadas como una consulta real al servicio.

Pinecone Local llegó al fin de vida el 7 de octubre de 2026 según la documentación
oficial consultada para esta entrega. No se usa como sustituto del servicio. El
mock oficial valida peticiones, pero no almacena documentos ni reproduce búsquedas.
