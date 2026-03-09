run:
	ENV_FILE=.env uvicorn api.main:app --reload

test:
	ENV_FILE=.env.test pytest

celery:
	ENV_FILE=.env python -m celery -A worker.app.celery_app worker -l info

docker-up:
	docker compose up --build

load-events:
	PYTHONPATH=. python scripts/load_events.py --api-key pulse_1a31b0c50a6f237f73159c653716fbdb --requests 10000 --concurrency 100
