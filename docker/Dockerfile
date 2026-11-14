FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TOPORIA_WEB_HOST=0.0.0.0 \
    TOPORIA_WEB_PORT=8765 \
    TOPORIA_WEB_OPEN_BROWSER=0

WORKDIR /app
COPY . .

RUN python -m pip install --no-cache-dir ".[3d]"

EXPOSE 8765
CMD ["toporia", "web"]
