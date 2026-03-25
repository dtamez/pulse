# Pulse

Pulse is a locally deployable Python application built around a FastAPI API service, a Celery worker, Redis, and two Postgres shards. The Docker Compose setup runs:

- `api` via Uvicorn
- `worker` via Celery
- `redis`
- `postgres_shard0`
- `postgres_shard1`

That layout is defined in the current `docker-compose.yml`. The API and worker both build from the same Docker image and differ only by startup command. Postgres shard 0 listens on host port `5432`, shard 1 on `5433`, and Redis on `6379`.

## Project layout

This README assumes the repo contains:

- a `Dockerfile`
- `docker-compose.yml`
- `.env.docker`
- `.env.kubernetes`
- Kubernetes manifests under `k8s/`

It also assumes the Kubernetes setup now uses:

- service names like `pulse-postgres-shard0`, `pulse-postgres-shard1`, and `pulse-redis`
- local Postgres storage via `emptyDir` for local development
- separate migrate and bootstrap jobs that are run after the databases are up

## Prerequisites

### For Docker
- Docker Engine
- Docker Compose plugin

### For Kubernetes
- Docker
- `kubectl`
- `kind`

## Running with Docker

### 1. Verify local environment file
Make sure `.env.docker` exists and contains the Docker-specific values for:
- Postgres credentials
- Redis settings
- any application secrets
- Docker hostnames expected by the app

### 2. Start the stack
```bash
docker compose up --build
```

### 3. Run in detached mode
```bash
docker compose up --build -d
```

### 4. Check containers
```bash
docker compose ps
```

### 5. View logs
```bash
docker compose logs -f
```

To follow a single service:
```bash
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f postgres_shard0
docker compose logs -f postgres_shard1
docker compose logs -f redis
```

### 6. Access the API
The API is published on port `8000`:
```text
http://localhost:8000
```

If Swagger is enabled:
```text
http://localhost:8000/docs
```

### 7. Stop the stack
```bash
docker compose down
```

To also remove volumes:
```bash
docker compose down -v
```

## Running with Kubernetes (local kind cluster)

This section is for the local Kubernetes version of the project.

### 1. Verify Kubernetes environment file
Make sure `.env.kubernetes` exists and uses Kubernetes service names, not Docker Compose names.

For example, use:
```env
POSTGRES_SHARD0_HOST=pulse-postgres-shard0
POSTGRES_SHARD1_HOST=pulse-postgres-shard1
REDIS_HOST=pulse-redis
```

### 2. Create a kind cluster
```bash
kind create cluster --name pulse
```

Verify:
```bash
kubectl get nodes
kubectl get pods -n kube-system
```

You should see CoreDNS running before deploying the app.

### 3. Build the application image
From the repo root:
```bash
docker build -t pulse-app:latest .
```

### 4. Load the image into kind
```bash
kind load docker-image pulse-app:latest --name pulse
```

### 5. Create the namespace
```bash
kubectl apply -f k8s/namespace.yaml
```

### 6. Create the Kubernetes secret from `.env.kubernetes`
```bash
kubectl delete secret pulse-secrets -n pulse --ignore-not-found

kubectl create secret generic pulse-secrets \
  --namespace pulse \
  --from-env-file=.env.kubernetes
```

### 7. Apply the manifests
Apply the core services first:
```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/redis-service.yaml
kubectl apply -f k8s/postgres-shard0-deployment.yaml
kubectl apply -f k8s/postgres-shard0-service.yaml
kubectl apply -f k8s/postgres-shard1-deployment.yaml
kubectl apply -f k8s/postgres-shard1-service.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/api-service.yaml
kubectl apply -f k8s/worker-deployment.yaml
```

### 8. Wait for the main services
```bash
kubectl get pods -n pulse -w
```

Wait until these are running:
- `pulse-api`
- `pulse-worker`
- `pulse-redis`
- `pulse-postgres-shard0`
- `pulse-postgres-shard1`

### 9. Create the application databases if needed
For the local `emptyDir` Postgres setup, the `pulse` database may need to be created before migrations run.

Create it on both shards:
```bash
kubectl exec -it deployment/pulse-postgres-shard0 -n pulse -- psql -U postgres -c "CREATE DATABASE pulse;"
kubectl exec -it deployment/pulse-postgres-shard1 -n pulse -- psql -U postgres -c "CREATE DATABASE pulse;"
```

If `POSTGRES_DB=pulse` is already handled by your manifests and first-time init path, this step may not be necessary.

### 10. Run migrations
```bash
kubectl delete job pulse-migrate -n pulse --ignore-not-found
kubectl apply -f k8s/migrate-job.yaml
kubectl logs job/pulse-migrate -n pulse -f
```

### 11. Run bootstrap
```bash
kubectl delete job pulse-bootstrap -n pulse --ignore-not-found
kubectl apply -f k8s/bootstrap-job.yaml
kubectl logs job/pulse-bootstrap -n pulse -f
```

### 12. Access the API
Port-forward the service:
```bash
kubectl port-forward svc/pulse-api 8000:8000 -n pulse
```

Then open:
```text
http://localhost:8000
```

If Swagger is enabled:
```text
http://localhost:8000/docs
```

### 13. Inspect Kubernetes resources
```bash
kubectl get all -n pulse
kubectl get svc -n pulse
kubectl get endpoints -n pulse
kubectl logs deployment/pulse-api -n pulse
kubectl logs deployment/pulse-worker -n pulse
```

## Teardown

### Docker
```bash
docker compose down
```

### Kubernetes
Delete app resources:
```bash
kubectl delete namespace pulse
```

Delete the local kind cluster:
```bash
kind delete cluster --name pulse
```

## Troubleshooting

### Docker
- If the API or worker cannot connect to Postgres, verify `.env.docker`
- If a port is already in use, stop the conflicting service or adjust ports
- Use `docker compose logs -f` to inspect failures

### Kubernetes
- If service names do not resolve, verify CoreDNS is running:
```bash
kubectl get pods -n kube-system
```
- If migrations fail with host resolution errors, verify `.env.kubernetes` uses Kubernetes service names
- If Postgres comes up but migrations fail with `database "pulse" does not exist`, create the database on both shards before running the migration job
- If the bootstrap job fails, inspect the job command and logs:
```bash
kubectl logs job/pulse-bootstrap -n pulse
```

## Notes

- Docker Compose and Kubernetes use different service names. Keep `.env.docker` and `.env.kubernetes` separate.
- For local Kubernetes development, `emptyDir` is acceptable for Postgres, but it is ephemeral.
- Because Postgres data is ephemeral in the local Kubernetes setup, restarting the Postgres deployments may require recreating the `pulse` database and rerunning migrate/bootstrap.
