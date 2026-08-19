FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

WORKDIR /app

COPY requirements-server.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip --index-url "${PIP_INDEX_URL}" \
    && python -m pip install --index-url "${PIP_INDEX_URL}" -r /tmp/requirements.txt

RUN groupadd --gid 10001 smartsync \
    && useradd --uid 10001 --gid smartsync --create-home smartsync

COPY --chown=smartsync:smartsync . /app
RUN mkdir -p /app/uploads \
    && chown -R smartsync:smartsync /app \
    && chmod +x /app/docker-entrypoint.sh

USER smartsync

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
