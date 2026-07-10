FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["python3", "-m", "uvicorn", "backend.app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
