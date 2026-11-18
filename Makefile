.PHONY: up modelos modelo-local check preparar indexar buscar rag inspeccionar test sql down
up:
	docker compose up -d --build
modelos:
	docker compose exec ollama ollama pull qwen2.5:3b
modelo-local:
	docker compose exec ollama ollama pull embeddinggemma:300m
check:
	docker compose exec app python src/2-check_servicios.py
preparar:
	docker compose exec app python src/3-preparar.py conocimiento --salida resultados/fragmentos.json
indexar:
	docker compose exec app python src/4-indexar.py resultados/fragmentos.json --salida resultados/registros-pinecone.json
buscar:
	docker compose exec app python src/5-buscar.py
rag:
	docker compose exec app python src/6-rag.py
inspeccionar:
	docker compose exec app python src/7-inspeccionar.py
test:
	docker compose exec app python -m unittest discover -s tests -v
sql:
	docker compose exec postgres psql -U walc -d walc
down:
	docker compose down
