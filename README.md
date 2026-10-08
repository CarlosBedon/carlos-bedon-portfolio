# Dashboard - Cookiecutter Django Cloud Ready

Django template ready to deploy on Render with Supabase Postgres and Storage. It is based on Cookiecutter Django: base / local / production settings, Bootstrap 5 with Sass and Gulp, WhiteNoise, pytest, and uv.

The Python package lives in the `dashboard` folder, the same name shown in the interface.

---

## What was set up

1. **Portfolio app**: `PortfolioHomeView` serves `portfolio/home.html` at `/portfolio/`. The route is in `config/urls.py`, right after the users route.
2. **External Postgres**: In production, `DATABASE_URL` wins over `POSTGRES_*`. Supabase is reached through the IPv4 session pooler (`aws-0-<region>.pooler.supabase.com`, port `5432`, user `postgres.<project-ref>`, `sslmode=require`). The direct host `db.<project-ref>.supabase.co` is IPv6-only, and Render cannot reach it. If the password contains `$`, write it as `%24` inside `DATABASE_URL`. `POSTGRES_WAIT=false` skips the wait for Docker Postgres.
3. **Static files in the image**: The production Dockerfile runs `collectstatic` while building the image, with dummy values that are not stored in the image. WhiteNoise needs `staticfiles.json` before Gunicorn starts. CSS comes from `npm run build` (`project.min.css`).
4. **Migrations on boot**: `compose/production/django/start` runs `migrate`, then `collectstatic` again, then Gunicorn on `0.0.0.0:${PORT:-5000}`.
5. **Secrets stay out of the repository**: `.env.example` has placeholders only. `.env`, `.env.production`, and `.envs/*` are in `.gitignore`. `.dockerignore` keeps `.env` and `.env.*` out of the image build.
6. **Pre-commit**: When the local container starts, `compose/local/django/start` installs the hooks. The set covers file cleanup, `detect-private-key`, `pyupgrade`, `django-upgrade`, `isort`, `black`, `flake8`, and `djLint`. The GitHub Action `.github/workflows/pre-commit.yml` runs `pre-commit run --all-files`.
7. **Supabase Storage**: `django-storages` and `boto3` are production dependencies in `pyproject.toml`. The image installs them with `uv sync --locked --no-dev`. The five `AWS_*` variables default to empty, so the app starts without them and keeps media on local disk. When all five are set, uploads use `S3Boto3Storage` and `AWS_S3_ENDPOINT_URL`. Addressing is path and the signature is `s3v4`. CSS and JS stay on WhiteNoise.
8. **Template branding**: The navbar, the title, and the greeting say **Dashboard** and **Welcome**, in English.

---

## Production variables

Copy the keys into the Render dashboard. Do not commit real values.

```env
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=change-me
DJANGO_ADMIN_URL=admin/
DJANGO_ALLOWED_HOSTS=.example.com,.onrender.com
DJANGO_CSRF_TRUSTED_ORIGINS=[https://example.com](https://example.com),https://*.onrender.com

DATABASE_URL=postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?sslmode=require
POSTGRES_HOST=aws-0-REGION.pooler.supabase.com
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=postgres.PROJECT_REF
POSTGRES_PASSWORD=change-me
POSTGRES_SSLMODE=require
POSTGRES_WAIT=false

AWS_ACCESS_KEY_ID=change-me
AWS_SECRET_ACCESS_KEY=change-me
AWS_STORAGE_BUCKET_NAME=media
AWS_S3_REGION_NAME=us-east-1
AWS_S3_ENDPOINT_URL=https://PROJECT_REF.storage.supabase.co/storage/v1/s3
```
