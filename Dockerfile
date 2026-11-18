FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY src/ ./src/
COPY conocimiento/ ./conocimiento/
COPY tests/ ./tests/
CMD ["sleep", "infinity"]
