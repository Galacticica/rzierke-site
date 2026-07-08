FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
     && apt-get install -y --no-install-recommends \
         curl ca-certificates gnupg build-essential libpq-dev git cron \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json* ./

RUN npm ci --unsafe-perm

# Install Python deps from the lockfile so the image can never drift from
# pyproject.toml. --no-dev keeps test tooling (pytest, playwright) out of
# the production image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"

COPY . .

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
# Strip CR so the entrypoint survives a Windows (CRLF) checkout.
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

RUN npm run build 

ENV DJANGO_SETTINGS_MODULE=conf.settings

RUN python manage.py collectstatic --noinput

EXPOSE 8000 5173

CMD ["/usr/local/bin/docker-entrypoint.sh"]
