# Observability

## Overview
Pulse uses Prometheus to scrape metrics from the API, Redis, Postgres shard exporters, and Celery exporter.

## Services Scraped

| Component | Job | Target | Purpose |
|---|---|---|---|
| FastAPI | pulse-api | api:8000/metrics | HTTP request counts, latency, Python/process metrics |
| Prometheus | prometheus | prometheus:9090 | Prometheus self-health |
| Redis | redis | redis-exporter:9121 | Redis memory, clients, commands/sec |
| Postgres shard 0 | postgres | postgres-exporter-shard0:9187 | DB health, connections, size, tx rate |
| Postgres shard 1 | postgres | postgres-exporter-shard1:9187 | DB health, connections, size, tx rate |
| Celery | celery-exporter | celery-exporter:9808 | task counts, queue length, runtime, worker health |

## Health Checks

```promql
up

pg_up

sum(celery_worker_up)
```



## Prometheus Queries 

### API
```promql

sum by (handler, method, status) (http_requests_total) 

sum by (handler, status) (
  rate(http_requests_total[5m])
)

sum(rate(http_requests_total{handler="/events",status="2xx"}[5m]))

sum(rate(http_requests_total{handler="/events"}[5m]))       

```

## Postgres 
```promql
pg_stat_database_numbackends{datname="pulse"} 

pg_database_size_bytes{datname="pulse"} 

rate(pg_stat_database_xact_commit{datname="pulse"}[5m])

rate(pg_stat_database_xact_rollback{datname="pulse"}[5m])

sum by (instance) (
  pg_stat_database_numbackends{datname="pulse"}
)

sum by (instance) (
  pg_database_size_bytes{datname="pulse"}
)

sum by (instance) (
  rate(pg_stat_database_xact_commit{datname="pulse"}[5m])
)
```

## Redis 
```promql
up{job="redis"}
redis_up
redis_connected_clients
redis_memory_used_bytes
rate(redis_commands_processed_total[5m]) 

```
## Celery 
```promql
sum(celery_worker_up)

sum by (name, queue_name) (
  celery_task_succeeded_total
)

sum by (name, queue_name) (
  rate(celery_task_succeeded_total[5m])
)

sum by (name, queue_name) (
  rate(celery_task_failed_total[5m])
)

celery_queue_length{queue_name="pulse"}

celery_active_worker_count{queue_name="pulse"}

histogram_quantile(
  0.95,
  sum by (le, name, queue_name) (
    rate(celery_task_runtime_bucket[5m])
  )
)

sum by (name, queue_name) (
  rate(celery_task_succeeded_total[5m])
)
```
## Dashboard Panels Planned

- API request rate by route/status
- API p95 latency
- Event ingest success/rejection rate
- Redis memory and command rate
- Postgres connections per shard
- Postgres transaction rate per shard
- Celery task throughput
- Celery queue length
- Celery p95 task runtime
- Worker online status

## Notes

- `up=1` means Prometheus can scrape the exporter.
- `pg_up=1` means the Postgres exporter can connect to Postgres.
- Celery task metrics only reflect events seen while the exporter is running.
- Query actual metric names from `/metrics`; do not assume Flower metric names.
