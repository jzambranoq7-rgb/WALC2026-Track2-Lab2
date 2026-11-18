# Diagnóstico

Ejecuta los comandos desde `lab-dia-2/`.

| Síntoma | Qué revisar | Acción |
| --- | --- | --- |
| PostgreSQL no responde | Servicio `postgres`, contraseña y volumen. | `docker compose ps` y `docker compose logs postgres --tail 50`. Cambiar la contraseña del .env no cambia la de un volumen ya inicializado. |
| Falta indexar | Tabla indexacion vacía para el grupo. | Ejecuta `4-indexar.py resultados/fragmentos.json` después de generar ese archivo. |
| Falta una tabla | Inicialización de PostgreSQL. | Aplica `sql/01-documentos.sql` sobre la base del laboratorio; se ejecuta automáticamente en el primer arranque del volumen. |
| Ollama no responde | Estado y logs del motor. | `docker compose ps` y `docker compose logs ollama --tail 50`. |
| El modelo local no existe | El nombre de `ollama list`. | `docker compose exec ollama ollama pull qwen2.5:3b`. |
| Falta clave | `PINECONE_API_KEY` en `.env`. | Complétala y ejecuta `docker compose up -d --force-recreate app`. No muestres la clave. Un host vacío se resuelve por `PINECONE_INDEX_NAME`. |
| `Unauthorized` o `Forbidden` | Proyecto, permisos de la clave y host del mismo índice. | El instructor revisa la cuenta. La app no imprime el cuerpo del error. |
| `NotFound` | `PINECONE_INDEX_NAME` o el host explícito. | Ejecuta `2-check_servicios.py` para crear el índice por nombre. Si usas host, debe pertenecer a un índice existente. |
| Falla la creación del índice | Permisos de creación de la clave, cuota, nube y región. | Revisa la cuenta con el instructor o usa su índice existente mediante `PINECONE_INDEX_HOST`. |
| El índice aún no está listo | Estado del índice en Pinecone. | Espera y repite `2-check_servicios.py`; la creación espera hasta 120 segundos. |
| El modelo gestionado no está disponible | Nombre `multilingual-e5-large`, proyecto y plan. | Revisa la cuenta y `EMBED_MODEL`. La app no muestra el cuerpo del error. |
| Dimensiones incompatibles | `EMBED_DIM`, modelo y configuración del índice. | Usa 1024 con `multilingual-e5-large` e índice cosine. No mezcles con el índice de 768 del desafío. |
| Texto demasiado largo | `truncate="NONE"` y el tamaño del fragmento. | El modelo rechaza entradas que superan su límite. Reduce `MAX_CARACTERES` o revisa el corte. |
| Error de red, TLS o timeout | DNS, proxy, acceso a Pinecone y estado del servicio. | Consulta los logs y vuelve a probar la verificación. El error de consulta no equivale a falta de evidencia. |
| La carga no es visible | Pinecone puede tardar en mostrar una escritura. | Espera y repite el indexador con el mismo archivo. El programa espera hasta 90 segundos. |
| Cambió el corpus | Modificaste los PDF; no se detecta automáticamente. | Genera de nuevo el JSON e indexa ese archivo. Si cambian los cortes, usa un namespace nuevo para no mezclar IDs antiguos. |
| Cambió la configuración | Prefijo, modelo, dimensión o host. | Recrea app y repite preparación e indexación. |
| Cero resultados | Filtros opcionales de documento y tipo, y namespace. | Revisa el filtro. Prueba sin `--documento` y después con `--tipo ficha`. |
| `[RECHAZADO]` | JSON o ID que produjo el modelo. | Ejecuta `7-inspeccionar.py` y compara con la fuente. Revisa la traza antes de otra consulta. |
| Usa una política caducada | Metadatos de vigencia y `fecha_consulta` en la traza. | Comprueba que se recuperó la política necesaria y revisa qué fuente eligió el modelo. Una petición histórica debe usar su fecha, no la actual. |
| Cita válida, afirmación incorrecta | La cita puede no respaldar el texto generado. | Registra el fallo al revisar la fuente. Tomar el texto original no comprueba la inferencia. |
| Un PDF no devuelve texto | Puede ser un PDF escaneado sin capa de texto. | El laboratorio no hace OCR. Comprueba con `pdftotext` o abre el PDF y selecciona texto. |
| `No module named pypdf` | Imagen construida con un lock anterior. | Reconstruye con `docker compose up -d --build` y revisa `requirements.lock.txt`. |

`docker compose config` puede mostrar las variables de entorno y sus valores.
Usa `docker compose config --quiet` si solo quieres revisar la configuración.
