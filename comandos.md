# Comandos del laboratorio, en orden

Ejecuta todo desde la carpeta `lab-dia-2`. Si la terminal está en `dia2`, Compose responde `no configuration file provided: not found` porque ahí no está `docker-compose.yml`.

```bash
cd lab-dia-2
```

El indicador de la terminal debe mostrar `lab-dia-2`.

Los PDF originales se ven en http://localhost:8002. Ese visor no es el objetivo del taller: sirve para abrir la página que cita cada respuesta.

## 0. Crear el archivo `.env` y elegir la contraseña

PostgreSQL todavía no existe. En este paso no entras a la base ni te pide una contraseña: escribes la que tú eliges en un archivo, y Docker la aplica cuando crea el servicio por primera vez.

```bash
cp .env.example .env
```

Eso copia la plantilla. Abre `.env` con un editor. Hay que completar dos líneas vacías antes de arrancar cualquier contenedor.

### Contraseña de PostgreSQL

Busca esta línea:

```text
POSTGRES_PASSWORD=
```

Escribe detrás del `=` una contraseña inventada para este laboratorio, sin espacios y sin comillas. Por ejemplo, si eliges `lab2`:

```text
POSTGRES_PASSWORD=lab2
```

Guarda el archivo. Esa cadena es la contraseña. No hay otra que te entreguen.

El usuario y el nombre de la base no se eligen. `docker-compose.yml` ya los fija:

- usuario: `walc`
- base de datos: `walc`
- contraseña: el valor de `POSTGRES_PASSWORD` en `.env`

No crees el usuario a mano y no ejecutes `CREATE DATABASE`. Al arrancar el contenedor por primera vez, PostgreSQL lee esa variable, crea el usuario `walc`, crea la base `walc` y le asigna la contraseña que escribiste.

Si dejas la línea vacía, `docker compose up` se detiene y avisa que falta `POSTGRES_PASSWORD`. Si más adelante cambias la contraseña en `.env`, el contenedor ya creado sigue usando la primera: la contraseña queda grabada en el volumen la primera vez que el servicio arranca.

### Clave de Pinecone

En el mismo archivo, busca:

```text
PINECONE_API_KEY=
```

Entra en https://app.pinecone.io, abre el proyecto de práctica, crea una API key y pega el valor completo detrás del `=`, también sin comillas. Déjala en el equipo. No la pegues en el chat ni la subas a git. `.env` ya está en `.gitignore`.

`PINECONE_NAMESPACE=grupo-01` puede quedarse así si trabajas solo. Si varias personas comparten el mismo índice, cada una usa un namespace distinto, en minúsculas y sin espacios.

## 1. Levantar Ollama y PostgreSQL

Este comando solo funciona después del paso 0. Compose lee `POSTGRES_PASSWORD` desde `.env` y se la pasa al contenedor.

```bash
docker compose up -d --pull never --no-build ollama postgres
```

Crea la red y arranca los dos contenedores con las imágenes que ya están en el equipo. `--pull never` impide descargarlas de internet. Ollama queda en la red interna de Compose. PostgreSQL guarda textos, metadatos y procedencia, con el usuario `walc`, la base `walc` y la contraseña del `.env`.

Para comprobar que esa contraseña quedó aplicada, entra a la base desde el contenedor. Dentro del contenedor no te la vuelve a preguntar:

```bash
docker compose exec postgres psql -U walc -d walc -c "SELECT current_user, current_database();"
```

La consola debe mostrar:

```text
 current_user | current_database
--------------+------------------
 walc         | walc
```

`current_user` es el usuario y `current_database` es la base. Si aparece esa fila, la contraseña del paso 0 sirvió para crear el servicio.

```bash
docker compose exec ollama ollama list
```

Lista los modelos dentro del contenedor. Debe aparecer `qwen2.5:3b`, de unos 1.9 GB. Ese modelo redacta las respuestas. No calcula los embeddings.

## 2. Construir y arrancar la app

La imagen `app` no venía descargada. Hay que construirla una vez.

```bash
docker compose build app
```

Construye la imagen Python del laboratorio e instala las librerías de `requirements.lock.txt` (`ollama`, `pinecone`, `pypdf`, `psycopg` y `pydantic`).

```bash
docker compose up -d --pull never --no-build app
```

Arranca el contenedor que ejecuta los scripts y publica los PDF en http://localhost:8002.

```bash
docker compose ps
```

Muestra el estado. `ollama` y `postgres` deben estar `healthy`. `app` debe publicar `127.0.0.1:8002->8000/tcp`.

## 3. Comprobar los tres servicios

```bash
docker compose exec app python src/2-check_servicios.py
```

Hace cuatro comprobaciones:

1. Ollama tiene `qwen2.5:3b` y responde una frase corta.
2. PostgreSQL acepta la conexión.
3. Pinecone reutiliza el índice `walc-lab-dia-2` si ya existe, o lo crea si falta.
4. El embedding de prueba con `multilingual-e5-large` tiene 1024 dimensiones, igual que el índice.

En consola aparecen el modelo, una respuesta local, `PostgreSQL responde.`, el host del índice y `Dimensiones del índice: 1024`. La frase generada puede variar.

## 4. Preparar los PDF

```bash
docker compose exec app python src/3-preparar.py conocimiento/ficha-portatil-nova-14.pdf
```

Lee un solo PDF y escribe el JSON en la consola. Extrae el texto por página, lo corta en fragmentos de hasta 800 caracteres y asigna a cada uno un id, la página, la sección y la versión. Para la ficha del Nova 14 son 1 documento y 7 fragmentos. Este comando no guarda nada en las bases.

```bash
docker compose exec app python src/3-preparar.py conocimiento --salida resultados/fragmentos.json
```

Hace lo mismo con todos los PDF de `conocimiento/` y guarda el resultado. La consola muestra:

```text
Preparación guardada en resultados/fragmentos.json
Documentos: 9
Fragmentos: 65
```

Preparar no calcula embeddings ni escribe en PostgreSQL o Pinecone.

## 5. Ver un embedding e indexar

```bash
docker compose exec app python src/4-indexar.py resultados/fragmentos.json --fragmento ficha-portatil-nova-14-v1-seccion2-parte1 --solo-ver --salida resultados/registros-pinecone.json
```

Pide a Pinecone el vector de un solo fragmento, el de especificaciones del Nova 14, y lo guarda en un archivo. `--solo-ver` termina antes de escribir en las bases. La consola indica el modelo `multilingual-e5-large` y `Dimensiones por vector: 1024`.

```bash
docker compose exec app python src/4-indexar.py resultados/fragmentos.json --salida resultados/registros-pinecone.json
```

Indexa los 65 fragmentos:

1. Calcula un vector de 1024 números por fragmento.
2. Guarda el texto completo y los cortes en PostgreSQL.
3. Envía los vectores a Pinecone, en el namespace `grupo-01`.
4. Espera a que esos ids sean visibles.

La consola confirma la carga, `Registros visibles por ID: 65` y `Documentos y fragmentos guardados en PostgreSQL: 9 65`. Repetir el comando actualiza los mismos ids; no duplica el corpus.

## 6. Revisar el texto en PostgreSQL

`-U walc` es el usuario y `-d walc` es la base creados en el paso 0. La contraseña no se escribe aquí: el comando entra desde dentro del contenedor.

```bash
docker compose exec -T postgres psql -U walc -d walc -c "SELECT f.id, f.pagina, f.seccion FROM fragmentos AS f JOIN documentos AS d USING (documento, version) WHERE d.documento = 'ficha-portatil-nova-14' AND d.version = 1 ORDER BY f.id;"
```

Une `fragmentos` y `documentos` por id de documento y versión. Muestra las 7 partes de la ficha del Nova 14, con su página y su sección. Pinecone solo guarda el vector y el id; el texto que se cita sale de esta base.

```bash
docker compose exec -T postgres psql -U walc -d walc -c "SELECT namespace, modelo, dimension FROM indexacion;"
```

Muestra que el namespace `grupo-01` quedó registrado con `multilingual-e5-large` y dimensión 1024.

## 7. Buscar fragmentos

Estas consultas recuperan evidencia y todavía no llaman al modelo generativo. Cada una sustituye `resultados/busqueda.json`.

```bash
docker compose exec app python src/5-buscar.py
```

Usa la pregunta por defecto: el plazo para devolver un portátil comprado en octubre. Sin filtro, los primeros resultados son la FAQ y la política versión 2, ambas con 30 días. Cada línea trae similitud, versión, página, sección, texto y el enlace al PDF.

```bash
docker compose exec app python src/5-buscar.py "¿Qué plazo hay para devolver un portátil comprado en octubre?" --documento garantia-devoluciones
```

Limita la búsqueda al documento de garantía. Aparecen la versión 2 (30 días) y la versión 1 (15 días). El filtro se imprime como `documento = garantia-devoluciones`.

```bash
docker compose exec app python src/5-buscar.py "¿Cuánta RAM tiene el portátil Nova 14?" --tipo ficha
```

Limita la búsqueda a fichas técnicas. Los dos primeros fragmentos son la descripción y las especificaciones del Nova 14: 16 GB de RAM y 512 GB de almacenamiento.

## 8. Responder con citas

Cada comando recupera fragmentos, pide una respuesta en JSON a Ollama y sustituye `resultados/ultima-respuesta.json`. Python comprueba que el id citado esté entre los fragmentos recuperados y copia la cita desde PostgreSQL.

```bash
docker compose exec app python src/6-rag.py "¿Cuántos días tengo para devolver un producto?"
```

Responde que hay 30 días naturales y cita las preguntas frecuentes, versión 1, página 2. El enlace abre http://localhost:8002/preguntas-frecuentes.pdf#page=2.

```bash
docker compose exec app python src/6-rag.py "¿Cuánta RAM y qué almacenamiento tiene el portátil Nova 14?" --documento ficha-portatil-nova-14
```

Responde con dos afirmaciones, 16 GB de RAM y 512 GB de almacenamiento, citando las especificaciones de la ficha, página 1.

```bash
docker compose exec app python src/6-rag.py "¿Cuál es el brillo del monitor Nova 27?" --documento ficha-monitor-nova-27
```

La ficha habla de panel, resolución y frecuencia, y no indica el brillo. La consola dice que los fragmentos no aportan evidencia suficiente.

```bash
docker compose exec app python src/6-rag.py "¿Qué plazo de devolución tenía la política de septiembre de 2026?"
```

El top 3 trae la vigencia de septiembre, pero no el fragmento que dice «15 días». El modelo se abstiene.

```bash
docker compose exec app python src/6-rag.py "¿Qué plazo hay para devolver un portátil comprado en octubre?"
```

El modelo afirma 30 días, pero escribe mal el id de la fuente (`secton` en lugar de `seccion`). El programa imprime `[RECHAZADO]` y termina con código 2. El rechazo es el resultado previsto cuando la cita no pertenece a los fragmentos recuperados.

## 9. Inspeccionar la última traza

```bash
docker compose exec app python src/7-inspeccionar.py
```

Lee `resultados/ultima-respuesta.json` y lo muestra sin volver a llamar al modelo. Imprime el estado, el namespace, el filtro, los enlaces a los PDF, los mensajes enviados y la salida del modelo.

Muestra la última ejecución de `6-rag.py`. Ahora mismo esa última ejecución es el rechazo de la pregunta de octubre. Para inspeccionar otra respuesta, vuelve a lanzar el `6-rag.py` correspondiente y, enseguida, este comando.

## 10. Apagar los contenedores

```bash
docker compose down
```

Elimina los contenedores y conserva los volúmenes: los modelos de Ollama y los textos de PostgreSQL siguen guardados. Los PDF permanecen en `conocimiento/` y la última traza en `resultados/`. El índice de Pinecone permanece en la cuenta. Para volver a trabajar, repite los comandos de los pasos 1 y 2.
