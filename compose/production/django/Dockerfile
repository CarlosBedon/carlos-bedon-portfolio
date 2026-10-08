FROM docker.io/node:26.5-bookworm-slim AS client-builder

ARG APP_HOME=/app
WORKDIR ${APP_HOME}
COPY ./package.json ./package-lock.json ${APP_HOME}
RUN npm ci && npm cache clean --force
COPY . ${APP_HOME}
RUN npm run build \
  && test -s carlosbedon_web/static/css/project.min.css \
  && test -f carlosbedon_web/static/js/project.min.js \
  && test -s carlosbedon_web/static/js/vendors.min.js
# define an alias for the specific python version used in this file.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS python-build-stage

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0

ARG APP_HOME=/app

WORKDIR ${APP_HOME}

# Install apt packages
RUN apt-get update && apt-get install --no-install-recommends -y \
  # dependencies for building Python packages
  build-essential \
  # psycopg dependencies
  libpq-dev


# Requirements are installed here to ensure they will be cached.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev
COPY --from=client-builder ${APP_HOME} ${APP_HOME}


RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev

# Python 'run' stage
FROM python:3.14-slim-bookworm AS python-run-stage

ARG APP_HOME=/app

WORKDIR ${APP_HOME}

RUN addgroup --system django \
  && adduser --system --ingroup django --home /home/django django


# Install required system dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
  # psycopg dependencies
  libpq-dev \
  # Translations dependencies
  gettext \
  # entrypoint
  wait-for-it \
  # cleaning up unused files
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && rm -rf /var/lib/apt/lists/*


COPY --chown=django:django ./compose/production/django/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint


COPY --chown=django:django ./compose/production/django/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start
COPY --chown=django:django ./compose/production/django/celery/worker/start /start-celeryworker
RUN sed -i 's/\r$//g' /start-celeryworker
RUN chmod +x /start-celeryworker


COPY --chown=django:django ./compose/production/django/celery/beat/start /start-celerybeat
RUN sed -i 's/\r$//g' /start-celerybeat
RUN chmod +x /start-celerybeat


COPY --chown=django:django ./compose/production/django/celery/flower/start /start-flower
RUN sed -i 's/\r$//g' /start-flower
RUN chmod +x /start-flower

# Copy the application from the builder
COPY --from=python-build-stage --chown=django:django ${APP_HOME} ${APP_HOME}
# explicitly create the media folder before changing ownership below
RUN mkdir -p ${APP_HOME}/carlosbedon_web/media

# make django owner of the WORKDIR directory as well.
RUN chown django:django ${APP_HOME}

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

USER django

RUN DATABASE_URL="postgres://dummy" \
  DJANGO_SETTINGS_MODULE="config.settings.test" \
  python manage.py compilemessages

# CompressedManifestStaticFilesStorage reads staticfiles.json at runtime.
# Build it into the image so the manifest exists before Render starts the
# process. These values exist only for this layer; they are not image ENV.
RUN DATABASE_URL="postgres://dummy" \
  DJANGO_SETTINGS_MODULE="config.settings.production" \
  DJANGO_SECRET_KEY="build-time-collectstatic-not-a-runtime-secret" \
  DJANGO_ADMIN_URL="admin/" \
  AWS_ACCESS_KEY_ID="build" \
  AWS_SECRET_ACCESS_KEY="build" \
  AWS_STORAGE_BUCKET_NAME="build" \
  AWS_S3_REGION_NAME="us-east-1" \
  AWS_S3_ENDPOINT_URL="https://example.storage.supabase.co/storage/v1/s3" \
  python manage.py collectstatic --noinput

ENTRYPOINT ["/entrypoint"]
