.PHONY: up down reset seed-postgres seed-mongo seed-all logs

up:
	docker compose up -d --build
	docker compose exec backend python /app/scripts/seed_if_needed.py

down:
	docker compose down

reset:
	docker compose down -v
	docker compose up -d --build
	docker compose exec backend python /app/scripts/seed_if_needed.py

# force-reseed even if data already exists - use when you want fresh random data
seed-postgres:
	docker compose exec backend python /app/scripts/seed_postgres.py

seed-mongo:
	docker compose exec backend python /app/scripts/seed_mongo.py

seed-all: seed-postgres seed-mongo

logs:
	docker compose logs -f