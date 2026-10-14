# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd --gid "${USER_GID}" ranger \
    && useradd \
        --uid "${USER_UID}" \
        --gid "${USER_GID}" \
        --create-home \
        --shell /bin/bash \
        ranger

WORKDIR /workspace

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install --editable ".[dev,analysis]"

COPY --chown=ranger:ranger . .

USER ranger

CMD ["./scripts/ci.sh"]