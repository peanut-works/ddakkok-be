up:
	docker compose up --build

upd:
	docker compose up -d --build

down:
	docker compose down

reset-db:
	docker compose down -v
	docker compose up -d --build

logs:
	docker compose logs -f backend

shell:
	docker compose exec backend bash

health:
	curl http://localhost:8000/api/health