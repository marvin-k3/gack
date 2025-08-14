# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libgl1 libsm6 libxext6 && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY dist/*.whl /tmp/
RUN uv pip install --system --no-cache /tmp/*.whl && rm /tmp/*.whl

CMD ["python", "-m", "gack"]
