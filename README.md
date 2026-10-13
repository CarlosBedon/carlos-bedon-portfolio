# commerce

Django project based on Cookiecutter Django: `local` / `test` / `production` settings, Bootstrap 5 with Sass and Gulp, WhiteNoise, pytest, and uv. It can run on Render with Supabase Postgres and Storage.

The Python package is `commerce`. There is no `dashboard` package. The navbar label is Dashboard. `/portfolio/` still shows the Welcome page.

There is no `config.settings.staging` module. A staging host uses `config.settings.production` with its own database, secret, hosts, and bucket.

---

## Settings

| Module                       | When it is used                                                           |
| ---------------------------- | ------------------------------------------------------------------------- |
| `config.settings.local`      | `manage.py` when `DJANGO_SETTINGS_MODULE` is unset. Docker Compose local. |
| `config.settings.test`       | `pytest` (`--ds=config.settings.test` in `pyproject.toml`).               |
| `config.settings.production` | `config/wsgi.py` by default. The production image and a Render service.   |

`config/settings/base.py` is shared. Production replaces the admin path, cache, HTTPS cookies, and media storage.

---

## Local

```bash
docker compose -f docker-compose.local.yml up django
```

Compose starts Postgres 18, Redis, and Mailpit, then Django. `compose/local/django/start` installs pre-commit hooks, runs `migrate` against the Compose Postgres, and starts `runserver_plus` on port 8000.

Those commands read `.envs/.local/.django` and `.envs/.local/.postgres`. Both paths are gitignored. `USE_DOCKER` is required by `config/settings/local.py` and has no default. Without `DATABASE_URL`, Django also requires `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD`. `POSTGRES_HOST` defaults to `postgres` and `POSTGRES_PORT` to `5432`.

---

## Tests

```bash
docker compose -f docker-compose.local.yml run --rm django pytest
```

Pytest uses `config.settings.test` and `--reuse-db`. The test settings reuse the database configuration from `base.py`, store mail in memory, and set `MEDIA_URL` to `http://media.testserver/`. The test database is created on the Compose Postgres named by `POSTGRES_*`. It is not the Render database.

---

## Production boot

`compose/production/django/Dockerfile` builds CSS and JS with `npm run build`, installs Python dependencies with `uv sync --locked --no-dev`, and runs `collectstatic` while building the image. The values used for that build step are dummies. They are not stored as image environment variables. WhiteNoise needs `staticfiles.json` before Gunicorn starts.

`compose/production/django/entrypoint` waits for `postgres:5432` only when `POSTGRES_HOST` is `postgres` and `DATABASE_URL` is empty, unless `POSTGRES_WAIT` says otherwise. `POSTGRES_WAIT=false` skips the wait. `POSTGRES_WAIT=true` always waits.

`compose/production/django/start` then runs, in order:

1. `python manage.py migrate --noinput`
2. `python manage.py collectstatic --noinput`
3. Gunicorn on `0.0.0.0:${PORT:-5000}`

`migrate` changes whichever database `DATABASE_URL` or `POSTGRES_*` points at. A staging service that is given the production URL will migrate production. Give staging its own URL.

If the database host is not `postgres`, `localhost`, or `127.0.0.1`, and `POSTGRES_SSLMODE` is empty, production settings set `sslmode=require`. Supabase on Render is reached through the IPv4 session pooler (`aws-0-<region>.pooler.supabase.com`, port `5432`, user `postgres.<project-ref>`). The direct host `db.<project-ref>.supabase.co` is IPv6-only, and Render cannot reach it. If the password contains `$`, write it as `%24` inside `DATABASE_URL`. `CONN_MAX_AGE` defaults to 60 seconds, which matches that session pooler. The transaction pooler on port `6543` is not what this project is set up for.

---

## Static files and media

`STATIC_ROOT` is `staticfiles/` (`/app/staticfiles` in the container). `STATIC_URL` is `/static/`. CSS and JS stay on WhiteNoise (`CompressedManifestStaticFilesStorage` in production).

Local Compose bind-mounts the repository over `/app`, so the `staticfiles/` tree built into an image is hidden. Tests and `runserver` then log `No directory at: /app/staticfiles/`. Django still finds CSS through the static file finders. The warning does not fail the test suite and does not describe the production image, where `collectstatic` creates that directory.

Media uses `MEDIA_URL=/media/` and `FileSystemStorage` unless all five `AWS_*` variables are set. Then production uses `S3Boto3Storage` with path addressing and signature `s3v4`. `AWS_QUERYSTRING_AUTH` is false, and `AWS_S3_CUSTOM_DOMAIN` is the public Supabase object host derived from `AWS_S3_ENDPOINT_URL` and `AWS_STORAGE_BUCKET_NAME`.

---

## Environment variables

Names and fictional values are in `.env.example`. That file is safe to commit. `.dockerignore` excludes `.env.*` from image builds. `.env`, `.env.production`, and `.envs/*` are gitignored. Do not commit real values.

Production refuses to start without `DJANGO_SECRET_KEY` and `DJANGO_ADMIN_URL`. It also needs a database: `DATABASE_URL`, or `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD`.

These have defaults, but a public host should set them:

| Variable                                | Default in production  |
| --------------------------------------- | ---------------------- |
| `DJANGO_ALLOWED_HOSTS`                  | `example.com`          |
| `DJANGO_CSRF_TRUSTED_ORIGINS`           | `https://example.com`  |
| `DJANGO_SECURE_SSL_REDIRECT`            | `true`                 |
| `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` | `true`                 |
| `DJANGO_SECURE_HSTS_PRELOAD`            | `true`                 |
| `DJANGO_SECURE_CONTENT_TYPE_NOSNIFF`    | `true`                 |
| `REDIS_URL`                             | `redis://redis:6379/0` |
| `DJANGO_EMAIL_BACKEND`                  | SMTP                   |
| `DJANGO_ACCOUNT_ALLOW_REGISTRATION`     | `true`                 |

HTTPS cookies are always marked secure in production (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`). `SECURE_PROXY_SSL_HEADER` trusts `X-Forwarded-Proto`. `SECURE_HSTS_SECONDS` is 60.

The web start script does not start Celery. Redis is used if the cache or a worker runs. Cache errors are ignored. A missing Redis host does not, by itself, stop Gunicorn.

Email defaults to SMTP. Staging should not reuse production SMTP credentials.

---

## Staging, not wired up here

Do not point a new Render service at the production Supabase database or bucket. Auto-deploy on the existing service follows `main`. A staging service should deploy another branch and get its own:

- `DJANGO_SECRET_KEY`
- `DATABASE_URL` (and matching `POSTGRES_*`)
- `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` for the staging hostname
- `POSTGRES_WAIT=false`
- its own five `AWS_*` values, or all five empty
- its own mail settings

`migrate` on boot will run against that service's database.
