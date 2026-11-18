# Laboratorio día 2 — RAG con documentos propios

En este laboratorio construirás un asistente que responde preguntas sobre los
documentos de una universidad ficticia y cita la página de cada afirmación.
Seguirás el recorrido RAG desde los PDF hasta la respuesta: prepararás fragmentos,
calcularás embeddings gestionados y buscarás evidencia. La memoria conversacional
y los embeddings locales se trabajan en el desafío.

Continúa el día 1 con Python, Ollama, scripts numerados y
`docker compose exec app python ...`.

El caso es la **Universidad del Valle Andino**, del asistente académico de los
días 1 y 3. El corpus contiene diez PDF ficticios: cuatro sobre inscripciones y
atención reutilizan el contenido del día 3; los demás tratan horarios, biblioteca,
tutorías, constancias y acceso. El horario de orientación cambia entre septiembre
y octubre. El plazo de emisión de una constancia no está documentado: sirve para
practicar una abstención.

## Qué necesitas preparar antes del laboratorio

- Docker con Compose. No necesitas instalar Python, Ollama ni paquetes en el equipo.
- Internet para las imágenes, el modelo generativo y Pinecone. CPU suficiente para
  un modelo de 3B. Reserva unos 8 GB de RAM libres como referencia y espacio para
  las imágenes. La duración depende del equipo y la conexión. GPU opcional.
- Cuenta y proyecto de práctica de Pinecone y una clave con permiso para crear
  índices. El script `2-check_servicios.py` prepara un **índice vectorial denso de 1024 dimensiones y
  métrica cosine**, para vectores externos, si no existe. También puedes usar
  el host de un índice compartido preparado por el instructor, con un prefijo
  distinto por grupo. Consulta [la preparación del instructor](docs/instructor.md).

El laboratorio **no descarga un modelo de embeddings**. Pinecone Inference calcula
los vectores con `multilingual-e5-large`. El texto de los documentos y las consultas
se envía a Pinecone por HTTPS; no se calcula localmente. La inferencia tiene costo
por tokens según el plan de la cuenta. `2-check_servicios.py` crea el índice si falta; ningún programa elimina índices.

PostgreSQL estándar guarda documentos y fragmentos. En el desafío, cada grupo
debe instalar y activar pgvector para guardar embeddings locales de 768 dimensiones
con `embeddinggemma:300m`. Esa configuración forma parte del trabajo del grupo.

## Recorrido del laboratorio

| Bloque | Resultado observable |
| --- | --- |
| Entorno y servicios | Ollama responde, el embedding gestionado y el índice de 1024 coinciden. |
| Preparación documental | Documento y fragmentos visibles en consola y guardados en JSON. |
| Embeddings e indexación | Vectores inspeccionados, textos en PostgreSQL e IDs visibles en Pinecone. |
| Búsqueda y filtros | Fragmentos, vigencia y procedencia revisados. |
| RAG y citas | Respuesta con página, cita y abstención. |
| Diagnóstico y cierre | Traza revisada y recursos explicados. |

Prepara las imágenes, el modelo y el índice antes del laboratorio. Las descargas
iniciales pueden requerir una sesión de preparación adicional.

## Archivos Python en orden

| Archivo | Qué hace |
| --- | --- |
| `src/1-common.py` | Configuración, clientes, embeddings gestionados y recuperación compartida. Se lee. |
| `src/2-check_servicios.py` | Verifica generación local, crea o reutiliza el índice y comprueba embeddings. |
| `src/3-preparar.py` | Lee un PDF o carpeta y muestra o guarda un JSON con documentos y fragmentos. |
| `src/4-indexar.py` | Lee el JSON, calcula y muestra embeddings, guarda textos en PostgreSQL y vectores en Pinecone. |
| `src/5-buscar.py` | Busca IDs en Pinecone, lee texto de PostgreSQL y muestra el enlace al PDF. |
| `src/6-rag.py` | Recupera y genera JSON con afirmaciones y citas. |
| `src/7-inspeccionar.py` | Muestra la petición y salida guardadas, sin llamar al modelo. |

Los archivos comparten código mediante `import_module("1-common")`, como en el día 1.
No hay scripts de memoria ni de chat en el recorrido principal.

Para leer el código en clase, empieza por `main()` y sigue las funciones que llama.
Cada función documenta su propósito y sus límites. Las anotaciones como
`pregunta: str` y `-> list[str]` indican el tipo de entrada y de salida; no validan los datos
por sí solas. `Any` se reserva para contenido JSON de estructura variable y objetos
del SDK. Las funciones `extraer_paginas` y `extraer_secciones` usan `yield` para
entregar un resultado por vez. Los nombres describen la operación, por ejemplo
`preparar_fragmentos`, `calcular_embeddings` y `validar_fuentes`.

## Paso 0 — Desempaquetar y configurar

El paquete `lab-dia-2-paquete.tar` reúne el laboratorio, las imágenes y los dos
modelos para Linux x86-64 (amd64). Necesitas Docker con Compose, espacio libre
para extraer el TAR y cargar las imágenes y modelos, y conexión a Pinecone.
En otros equipos y arquitecturas debe probarse la compatibilidad.

En una terminal Bash, desde la carpeta que contiene el TAR:

```bash
tar -xf lab-dia-2-paquete.tar
docker load -i imagenes-dia-2.tar.gz
cd lab-dia-2
```

`tar -xf` extrae el contenido; `docker load -i` carga las imágenes en Docker;
`cd` entra en la carpeta del laboratorio. El archivo `docker-compose.override.yml`
del paquete selecciona esas imágenes locales automáticamente. Si usas el material
sin el paquete, sigue la alternativa de descarga del paso 1.

### Crear la cuenta y obtener la clave de Pinecone

1. Abre [la consola de Pinecone](https://app.pinecone.io/). Regístrate y completa
   el acceso; si ya tienes cuenta, inicia sesión.
2. Selecciona el proyecto de práctica indicado por el instructor o crea uno si
   tu cuenta lo permite. Revisa las condiciones y límites del plan antes de usarlo.
3. En el proyecto, entra en **API keys**, pulsa **+ API key**, asigna un nombre,
   selecciona los permisos necesarios para el laboratorio y pulsa **Create key**.
   Si se usará un índice compartido, sigue los permisos y el host que indique el
   instructor. En algunos planes la consola solo ofrece el permiso **All**.
4. Copia la clave y guárdala de forma segura antes de cerrar el diálogo: Pinecone
   no vuelve a mostrar su valor completo. Si ya cerraste el diálogo sin copiarla,
   crea otra clave. [Pasos oficiales de Pinecone](https://docs.pinecone.io/admin/projects/manage-api-keys).

### Guardar la configuración local

Copia la configuración solo si aún no existe `.env`; si ya existe, consérvalo:


```bash
cp .env.example .env
```

Abre `.env` en tu editor. Pega la clave en la línea `PINECONE_API_KEY=`, guarda
el archivo, elige `POSTGRES_PASSWORD`
para la base local y completa el prefijo asignado a tu
grupo en `PINECONE_NAMESPACE`. `PINECONE_INDEX_NAME=walc-lab-dia-2` identifica el
índice que se creará o reutilizará. Para uno nuevo, los valores iniciales son
`PINECONE_CLOUD=aws` y `PINECONE_REGION=us-east-1`.

Si ya usaste el corpus anterior, asigna un **namespace nuevo** en `PINECONE_NAMESPACE`
y prepara e indexa el corpus completo. La indexación no elimina los vectores
antiguos; reutilizar el namespace mezclaría documentos de ambos casos. Los textos
antiguos pueden seguir en PostgreSQL, pero no se recuperan desde el namespace nuevo.

Deja `PINECONE_INDEX_HOST` vacío para usar el nombre: cada script resuelve el host
automáticamente, sin editar `.env` después ni recrear el contenedor. Si el instructor
te entrega un host de un índice existente, puedes indicarlo como alternativa:
empieza por `https://` y termina en `.pinecone.io`, sin rutas. Ese host tiene
prioridad y el script no crea otro índice.

Mantén `MODEL=qwen2.5:3b`, `EMBED_MODEL=multilingual-e5-large` y `EMBED_DIM=1024`.
La clave permanece en tu archivo local. No pegues `.env` en chats ni lo añadas al ZIP.

## Paso 1 — Servicios y modelo

Con el paquete extraído, inicia únicamente Ollama y comprueba el ID de su
contenedor antes de copiar los modelos:

```bash
docker compose up -d --no-build --pull never ollama
docker compose ps -q ollama
```

`up -d` inicia en segundo plano; `--no-build` evita construir imágenes;
`--pull never` impide descargarlas y `ollama` es el nombre del servicio.
`ps -q ollama` muestra solo el ID del contenedor del servicio en el proyecto
Compose actual. Si no muestra nada, comprueba `docker compose ps`, la carpeta
y el proyecto; no continúes con la copia hasta ver el ID.

En un volumen nuevo del día 2, restaura los modelos y verifica la lista:

```bash
docker cp - "$(docker compose ps -q ollama):/root/.ollama/" < ../modelos-dia-2.tar
docker compose exec ollama ollama list
docker compose up -d --no-build --pull never
docker compose ps
```

`$(...)` sustituye el comando por el ID obtenido; `<` envía el TAR a `docker cp`;
`-` indica entrada estándar y la ruta final es el directorio dentro del
contenedor. Deben aparecer `qwen2.5:3b` y `embeddinggemma:300m` (desafío).
Si el volumen ya contiene modelos, revisa su contenido antes de copiar: se pueden
sobrescribir archivos. `up` sin un servicio inicia los tres.

**Alternativa sin paquete:** prepara `.env` y ejecuta `docker compose up -d --build`,
seguido de `docker compose exec ollama ollama pull qwen2.5:3b`. Para el desafío,
descarga también `embeddinggemma:300m`. Esta ruta requiere descargas.

Comprueba los servicios `app`, `ollama` y `postgres`. Ollama y PostgreSQL deben
estar `healthy`. PostgreSQL solo se expone dentro de la red de Compose. Este proyecto
no publica el puerto 11434 en el equipo, de modo que puede coexistir con el día 1.
`app` usa `http://ollama:11434` dentro de la red de Compose. Pinecone es un servicio
externo por HTTPS. El nombre de proyecto y los volúmenes son independientes del día 1.
`app` sirve los PDF originales en http://localhost:8002; los scripts siguen
utilizando `docker compose exec app python ...`.

```bash
docker compose exec app python src/2-check_servicios.py
```

Este script crea el índice por nombre si falta y espera hasta 120 segundos a que
esté listo. Si ya existe, comprueba que sea denso, de 1024 dimensiones y métrica
cosine; no lo borra ni lo recrea. Si indicaste un host, usa ese índice existente y
comprueba su dimensión. Repetir el comando reutiliza el índice.

Debes ver el modelo local, una respuesta, un vector gestionado de 1024 números y
la confirmación de dimensión del índice. El texto generado puede variar. Si todavía
preparas Pinecone, puedes verificar solo Ollama con `--solo-ollama`. Esa opción no
verifica la inferencia ni la búsqueda gestionada.

## Paso 2 — Preparar un PDF o una carpeta

Sin `--salida`, el preparador imprime JSON en consola. Puedes ver el texto del
documento y cada fragmento con su ID, página, sección y metadatos:

```bash
docker compose exec app python src/3-preparar.py conocimiento/inscripciones.pdf
```

Para guardar ese mismo resultado, indica la ruta del archivo:

```bash
docker compose exec app python src/3-preparar.py conocimiento/inscripciones.pdf --salida resultados/fragmentos.json
```

También puedes pasar una carpeta: se preparan todos sus PDF, incluidas las
subcarpetas. Sin ruta se usa `conocimiento/`. Prepara el corpus completo para
las preguntas de inscripción y servicios académicos del resto del laboratorio:

```bash
docker compose exec app python src/3-preparar.py conocimiento --salida resultados/fragmentos.json
```

El JSON contiene `documentos`, con el texto completo extraído, y `fragmentos`,
con el texto y la procedencia de cada corte. **Preparar no calcula embeddings ni
escribe en PostgreSQL o Pinecone.** Sin `--salida`, también puedes redirigir la
salida estándar a un archivo del equipo anfitrión; usa `docker compose exec -T`
para evitar los caracteres de una terminal interactiva.

Para un PDF propio, cópialo a `conocimiento/` y pasa su ruta. El programa reutiliza
los metadatos de `catalogo.json` para los PDF conocidos. Para uno nuevo asigna
nombre del archivo, versión 1 y tipo `documento`; puedes ver y editar esos datos
en el JSON antes de indexar. Las rutas de Docker se refieren a `/app`: `resultados/`
está montada y permite guardar archivos visibles también desde tu equipo.

`pypdf` extrae texto, sin OCR. El corpus conocido usa encabezados en mayúsculas
para agrupar secciones. Los PDF nuevos se dividen por página para no perder texto
por una heurística de encabezados. Cada parte tiene como máximo 800 **caracteres**;
no son tokens. El corte puede separar una condición de su explicación. Aquí no
se usa solapamiento. Revisa los fragmentos antes de continuar.

Práctica opcional: cambia `MAX_CARACTERES` a 160, vuelve a preparar y observa los
cortes en consola. Restablece 800 y genera de nuevo `resultados/fragmentos.json`.

## Paso 3 — Ver los embeddings e indexar el archivo

El indexador recibe el JSON del paso anterior. En un mismo script se ven las dos
llamadas: `inference.embed` calcula los embeddings; `upsert` los guarda en Pinecone.
No vuelve a extraer los PDF ni lee los fragmentos de PostgreSQL para calcularlos.

Empieza por un solo fragmento. La opción `--solo-ver` **sí llama a la inferencia
gestionada**, pero no guarda nada en las bases. Sin `--salida` muestra todos los
valores del vector y los metadatos en consola:

```bash
docker compose exec app python src/4-indexar.py resultados/fragmentos.json --fragmento inscripciones-v1-seccion1-parte1 --solo-ver
```

Para guardar ese objeto en un archivo en vez de imprimir los números, añade
`--salida`. Este archivo permite inspeccionar el payload exacto de `upsert`:

```bash
docker compose exec app python src/4-indexar.py resultados/fragmentos.json --fragmento inscripciones-v1-seccion1-parte1 --solo-ver --salida resultados/registros-pinecone.json
```

El objeto contiene `namespace` y `vectors`. Cada registro tiene `id`, `values`
—los 1024 números del embedding— y `metadata` —documento, versión, tipo y sede—.
Los valores no se redondean ni se sustituyen por puntos suspensivos. El texto y la
ubicación del original se guardarán en PostgreSQL, no en los metadatos de Pinecone.

Para indexar, ejecuta el mismo script sin `--solo-ver`. Calcula los embeddings,
muestra o guarda el payload **antes de enviarlo**, guarda los textos en PostgreSQL,
ejecuta `upsert` y confirma que los IDs sean visibles. Sin `--fragmento`, procesa
todos los fragmentos del archivo:

```bash
docker compose exec app python src/4-indexar.py resultados/fragmentos.json --salida resultados/registros-pinecone.json
```

`--salida` solo cambia dónde ves el payload; no evita la carga. `--solo-ver` es la
opción que evita escribir en las bases. Cada ejecución vuelve a calcular los
embeddings. El archivo de vectores sirve para inspeccionar lo enviado; la entrada
del indexador sigue siendo el archivo de documentos y fragmentos.

Puedes usar `--fragmento ID` para cargar uno, o repetir la opción para varios.
Se actualizan los IDs enviados y se conservan los demás registros. **No hay borrado
automático de fragmentos antiguos.** Si cambias el tamaño de corte, practica en
un namespace nuevo y vuelve a cargar el corpus completo. El namespace es exactamente
`PINECONE_NAMESPACE`; no se calculan huellas.

Después de la carga, PostgreSQL contiene el texto completo en `documentos` y los
cortes indexados en `fragmentos`. Puedes comprobar la relación y abrir el PDF original:

```bash
docker compose exec postgres psql -U walc -d walc
```

```sql
SELECT f.id, d.archivo, f.pagina, f.seccion, f.texto
FROM fragmentos AS f
JOIN documentos AS d USING (documento, version)
WHERE d.documento = 'inscripciones' AND d.version = 1;
```

El esquema está en `sql/01-documentos.sql`. La tabla `indexacion` registra modelo,
dimensión e índice tras confirmar la carga. Si la carga falla, no queda marcada
como lista. Modificar un PDF o preparar otro JSON no cambia lo que ya está indexado:
debes ejecutar explícitamente el indexador con el archivo elegido.

## Paso 4 — Buscar antes de generar

```bash
docker compose exec app python src/5-buscar.py
docker compose exec app python src/5-buscar.py "¿Qué datos necesito para solicitar una inscripción?" --documento inscripciones
docker compose exec app python src/5-buscar.py "¿Cuántos libros puedo solicitar en préstamo?" --tipo procedimiento
```

La pregunta puede escribirse sin filtros. La búsqueda conserva las distintas
versiones: el modelo recibe documento, versión y fechas junto al texto recuperado.
El prompt le indica usar la última versión vigente, salvo que el usuario pida
otra fecha o versión. El cliente no necesita conocer números internos de versión.

`FECHA_CONSULTA=2026-10-28` fija la fecha del caso para repetirlo en clase.
El modelo la recibe como referencia: el horario de septiembre termina a las 15:00;
el vigente desde octubre termina a las 16:00. Compara la pregunta actual con la histórica, filtrando esta última para inspeccionar
las dos versiones del horario:

```bash
docker compose exec app python src/6-rag.py "¿Hasta qué hora atiende la mesa de orientación?"
docker compose exec app python src/6-rag.py "¿Hasta qué hora atendía la mesa de orientación en septiembre de 2026?" --documento horario-orientacion
```

`--documento` y `--tipo` son filtros opcionales de inspección para la práctica.
No hay un argumento `--version`. La búsqueda no descarta versiones por fecha:
el modelo elige con los metadatos del contexto. Esto es RAG de dos pasos, sin
tool calling. `sede` se conserva como metadato, sin restringir automáticamente
la búsqueda a una sede.

El modelo solo puede elegir entre los fragmentos recuperados. Si falta la versión
necesaria, debe abstenerse. Revisa la traza: el prompt no garantiza por sí solo
que siempre seleccione bien la vigencia.

Pinecone devuelve IDs y similitudes. Con esos IDs, una consulta SQL hace JOIN entre
`fragmentos` y `documentos` para obtener el texto y su procedencia. Cada resultado
muestra similitud, página, sección, texto, identificador y un enlace al PDF original,
por ejemplo `http://localhost:8002/orientacion-v2.pdf#page=1`. El visor del
navegador suele abrir la página indicada; si no, puedes ir a la página mostrada. La
puntuación no es una probabilidad de verdad ni un umbral universal de suficiencia.

Práctica manual: cambia **solo** `TOP_K = 3` a `TOP_K = 1` en `src/5-buscar.py`.
Repite una pregunta compuesta como «¿Qué datos necesito para solicitar una inscripción y
cómo consulto su estado?». Compara qué información quedó fuera. Restablece 3.

## Paso 5 — Responder con citas revisables

```bash
docker compose exec app python src/6-rag.py "¿Qué datos necesito para solicitar una inscripción?"
docker compose exec app python src/6-rag.py "¿Cuántos libros puedo solicitar y por cuántos días?" --documento biblioteca
docker compose exec app python src/6-rag.py "¿Cuánto tarda la emisión de una constancia?" --documento constancias
```

En la primera respuesta, revisa cada afirmación contra la página del PDF. La
segunda debe citar el documento de biblioteca. La tercera encuentra información
sobre constancias, pero no un plazo de emisión: el
comportamiento esperado es abstenerse. Si el modelo inventa un dato, registra el
fallo aunque el JSON sea válido. Si no se recuperan fragmentos, el programa se
abstiene sin llamar al LLM.

Pydantic comprueba el JSON. El código comprueba que la fuente elegida fue
recuperada. El modelo redacta la afirmación y devuelve su ID; Python añade como
cita el texto del fragmento original de PostgreSQL, junto con su enlace al PDF. Si falla, muestra `[RECHAZADO]` y devuelve
código de salida 2. Es un resultado para diagnosticar, no para ocultar con reintentos
hasta que parezca funcionar. Un modelo pequeño puede fallar en estos contratos.

**Una cita literal válida no demuestra que la afirmación se deduzca de ella.**
La revisión humana completa esa comprobación. Las instrucciones del prompt tampoco
garantizan protección frente a contenido malicioso. No se configuran herramientas
ni acciones externas ejecutables por el modelo en este laboratorio.

```bash
docker compose exec app python src/7-inspeccionar.py
```

Muestra los mensajes reales enviados al modelo y la salida. La evidencia documental
viaja como datos del mensaje `user`, con instrucciones separadas en `system`.
`resultados/ultima-respuesta.json` se reemplaza en cada pregunta y permite revisar
la ejecución actual.

### Más preguntas para explorar el corpus

Ejecuta las consultas con `src/6-rag.py` y compara cada afirmación con su PDF.
Los resultados dependen de los fragmentos recuperados y del modelo; no se trata de
respuestas garantizadas.

1. ¿Qué datos necesito para solicitar una inscripción?
2. ¿Puedo consultar el estado con mi matrícula en vez del número de seguimiento?
3. ¿Qué ocurre si envío dos veces la misma solicitud?
4. ¿Una solicitud recibida confirma mi cupo?
5. ¿Qué hago si pierdo el número de seguimiento?
6. ¿Qué hago si no recibo respuesta al registrar una solicitud?
7. ¿Cuántos libros puedo solicitar y por cuántos días?
8. ¿Cuándo puedo renovar un préstamo de biblioteca?
9. ¿Qué información debo proporcionar para pedir una tutoría?
10. ¿A qué dirección escribo si no puedo acceder a la plataforma?
11. ¿Cuánto tarda la emisión de una constancia? (El plazo no está documentado.)
12. ¿Hasta qué hora atendía orientación en septiembre de 2026? (Inspecciona
    `--documento horario-orientacion` para comparar las versiones.)

## Paso 6 — Cierre y entrega del grupo

Revisa un ejemplo con evidencia, uno sin evidencia y la selección actual e histórica
de la política a partir de sus metadatos.
Anota qué verificaste leyendo el PDF y qué comprobó automáticamente el código.

```bash
docker compose down
```

Los contenedores se eliminan. `ollama_data` conserva los modelos y `postgres_data`
conserva documentos, fragmentos y estado de indexación. `resultados/` conserva la
última traza. Los PDF permanecen en `conocimiento/`. El índice externo de
Pinecone permanece en la cuenta, independiente de Docker. No uses `down -v` si
quieres conservar los modelos y la base documental.

El laboratorio no guarda memoria conversacional. Esa pieza, junto con los
embeddings locales, se implementa en el desafío.

## Material complementario

- [Diapositivas PowerPoint](../slides/lab-dia-2.pptx) · [PDF](../slides/lab-dia-2.pdf)
- [Mapa de conceptos y límites](docs/mapa-conceptos.md)
- [Diagnóstico](docs/diagnostico.md)
- [Preparación y guía del instructor](docs/instructor.md)
- [Desafío de integración](desafio/README.md)
- [Documentación técnica oficial](docs/referencias.md)

## Comprobaciones del material

```bash
docker compose exec app python -m unittest discover -s tests -v
```

Las pruebas aisladas comprueban extracción de PDF, cortes, procedencia, filtros,
namespace fijo, creación o reutilización del índice y rechazo de citas inválidas
con dobles de los servicios. Las pruebas SQL de `tests/test_postgres.py` se habilitan
con `PRUEBAS_POSTGRES=1` y `PGDATABASE=walc_pruebas`, exclusivamente en una base
separada donde se haya aplicado `sql/01-documentos.sql`. Comprueban persistencia,
JOIN por ID, invalidación al preparar y rollback ante errores. No sustituyen
la prueba de conexión ni una consulta real a Pinecone.

## Comprobación del recorrido

Las pruebas aisladas se ejecutan con:

```bash
docker compose exec app python -m unittest discover -s tests -v
```

La regresión real requiere el catálogo completo preparado e indexado. Consulta
PostgreSQL, Pinecone y Ollama y consume inferencia gestionada:

```bash
docker compose exec -e PRUEBAS_RAG_REALES=1 app python -m unittest discover -s tests -p test_rag_real.py -v
```

Comprueba datos de inscripción, préstamo de biblioteca, plazo no documentado y
horarios actual e histórico. Además revisa las fuentes y los enlaces. Usa
`MODEL=qwen2.5:3b`: usa este modelo para el recorrido; las respuestas deben comprobarse al ejecutarlo. Pasar estos casos no garantiza cualquier respuesta futura.
