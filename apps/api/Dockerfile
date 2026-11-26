FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MUNSHI_DB=/data/munshi.db

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api ./apps/api
COPY packages ./packages
RUN mkdir -p apps/api/var /data

EXPOSE 8000
CMD ["python", "apps/api/run.py"]
