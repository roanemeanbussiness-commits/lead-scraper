# Pinned: jstyleson (a former transitive dep) breaks on Python 3.13+; stay on 3.12.
FROM python:3.12.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lead_scraper ./lead_scraper
COPY data ./data
COPY docs ./docs
COPY README.md .

EXPOSE 8080

CMD ["uvicorn", "lead_scraper.web:app", "--host", "0.0.0.0", "--port", "8080"]

