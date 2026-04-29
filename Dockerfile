FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        meson \
        ninja-build \
        libpq-dev \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libcairo2-dev \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        libjpeg-dev \
        zlib1g-dev \
        shared-mime-info \
        netcat-openbsd \
        gettext \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

COPY Pipfile Pipfile.lock* ./
RUN pip install --upgrade pip pipenv \
 && pipenv install --system --skip-lock

COPY . /src/
RUN chmod +x /src/entrypoint.sh

EXPOSE 8000

# Invoke via `sh` so the volume mount overriding the +x bit on macOS/Windows hosts
# does not break startup.
ENTRYPOINT ["sh", "/src/entrypoint.sh"]
