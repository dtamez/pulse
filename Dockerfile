FROM python:3.13-slim
RUN apt-get update && apt-get install -y libpq-dev 

WORKDIR /app 

RUN pip install uv

COPY pyproject.toml ./ 
COPY uv.lock ./

RUN uv pip install --system . 

COPY . . 

ENV PYTHONPATH=/app 

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
