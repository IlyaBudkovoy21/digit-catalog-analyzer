.PHONY: up down logs test worker-logs app-logs

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

app-logs:
	docker compose logs -f app

worker-logs:
	docker compose logs -f worker

test:
	pytest
