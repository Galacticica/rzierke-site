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

RUN python -m pip install --upgrade pip

COPY package.json package-lock.json* ./

RUN npm ci --unsafe-perm

RUN pip install --no-cache-dir \
    "django>=6.0.1" \
    "django-browser-reload>=1.21.0" \
    "django-filter>=25.2" \
    "django-htmx>=1.27.0" \
    "django-unfold>=0.83.1" \
    "django-vite>=3.1.0" \
    "openai>=2.24.0" \
    "psycopg[binary]>=3.3.2" \
    "python-dotenv>=1.2.1" \
    "python-pptx>=1.0.2" \
    "reportlab>=4.4.9" \
    "gunicorn>=20.1.0"

COPY . .

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

RUN npm run build 

ENV DJANGO_SETTINGS_MODULE=conf.settings

RUN python manage.py collectstatic --noinput

EXPOSE 8000 5173

CMD ["/usr/local/bin/docker-entrypoint.sh"]
