# Offline verification image: docker build -t audit-env . && docker run --network none audit-env
FROM python:3.11.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app
# test-only dependency, pinned; the environment core is stdlib-only
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .
RUN useradd --create-home auditor && chown -R auditor /app
USER auditor

CMD ["python", "scripts/verify_all.py"]
