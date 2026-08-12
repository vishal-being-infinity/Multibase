.PHONY: up down reset seed logs

up:
	docker compose up -d --build

down:
	docker compose down

reset:
	docker compose down -v
	docker compose up -d --build
	sleep 3
	docker compose exec backend python ../scripts/seed.py

seed:
	docker compose exec backend python /app/scripts/seed.py

logs:
	docker compose logs -f