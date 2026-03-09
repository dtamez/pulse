FROM python:3.13-slim
RUN apt-get update && apt-get install -y libpq-dev

WORKDIR /app 

COPY pyproject.toml ./ 
COPY uv.lock ./

RUN pip install uv
RUN uv pip install --system . 

COPY . . 

ENV PYTHONPATH=/app 

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
