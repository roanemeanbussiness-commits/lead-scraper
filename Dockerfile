# Pinned: keep in step with the version the app is developed against.
FROM python:3.12.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY copy_agent ./copy_agent
COPY README.md .

EXPOSE 8080

CMD ["uvicorn", "copy_agent.web:app", "--host", "0.0.0.0", "--port", "8080"]
