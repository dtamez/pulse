run:
	ENV_FILE=.env uvicorn api.main:app --reload

test:
	ENV_FILE=.env.test pytest

celery:
	ENV_FILE=.env python -m celery -A worker.app.celery_app worker -l info

docker-up:
	docker compose up --build

REQUESTS ?= 10000
CONCURRENCY ?= 100
load-events:
	PYTHONPATH=. python scripts/load_events.py --api-key pulse_1a31b0c50a6f237f73159c653716fbdb --requests $(REQUESTS) --concurrency $(CONCURRENCY)

NUM_EXPECTED ?= 500
check-summary:
	PYTHONPATH=. python scripts/check_tenant_summary.py --api-key pulse_1a31b0c50a6f237f73159c653716fbdb --tenant-id d34756c5-64d8-40cf-b2bd-5f844b53e80a --num-expected $(NUM_EXPECTED)
