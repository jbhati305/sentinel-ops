.PHONY: up down backend test clean

up:
	docker compose up --build

down:
	docker compose down

backend:
	python3 -m uvicorn backend.app.main:create_app --factory --reload --host 0.0.0.0 --port 8000

test:
	python3 -m pytest backend/tests -q

clean:
	rm -f sentinel_ops.sqlite3 sentinel_ops.sqlite3-shm sentinel_ops.sqlite3-wal
