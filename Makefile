run:
	ENV_FILE=.env uvicorn api.main:app --reload

test:
	ENV_FILE=.env.test pytest

celery:
	ENV_FILE=.env python -m celery -A worker.app.celery_app worker -l info

docker-up:
	docker compose up --build
