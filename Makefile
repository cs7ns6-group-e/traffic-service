.PHONY: install lint test build up down logs clean migrate ps restart

SERVICES := journey_booking conflict_detection notification road_routing traffic_authority

install:
	@for svc in $(SERVICES); do \
		echo "Installing $$svc dependencies..."; \
		pip install -r $$svc/requirements.txt -r $$svc/requirements-dev.txt; \
	done

lint:
	ruff check shared/ $(SERVICES)
	mypy shared/ --ignore-missing-imports --no-strict-optional

test:
	@for svc in $(SERVICES); do \
		echo "Testing $$svc..."; \
		cd $$svc && PYTHONPATH=../:. pytest app/tests/ --asyncio-mode=auto \
			--cov=app --cov-report=term-missing --cov-fail-under=70 -v; \
		cd ..; \
	done

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

clean:
	docker compose down -v

migrate:
	docker compose exec journey_booking alembic upgrade head

ps:
	docker compose ps

restart:
	docker compose restart $(service)
