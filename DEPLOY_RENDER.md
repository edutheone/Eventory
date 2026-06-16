Render deployment instructions

1) Connect repository in Render dashboard
   - Create a new Web Service -> Connect GitHub repo -> select this repo
   - Ensure Root/Working Directory is empty (default root)
   - Build Command: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
   - Start Command: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`

2) Environment variables (set in Render -> Service -> Environment):
   - `DJANGO_SECRET_KEY` : a secure random value
   - `DJANGO_DEBUG` : `False`
   - `DATABASE_URL` : Postgres connection string provisioned by Render Postgres
   - `ALLOWED_HOSTS` : comma-separated domains (e.g. `example.com,api.example.com`)

3) Database
   - Create a Render Postgres managed database and copy the `DATABASE_URL` into service env.

4) Post-deploy commands (run in Render shell or via deploy hooks):
   - `python manage.py migrate`
   - `python manage.py createsuperuser` (or create via admin UI)

5) Notes
   - Ensure the repository `requirements.txt` includes `psycopg2-binary`, `dj-database-url`, `gunicorn`, and `whitenoise` (already added).
   - Locally on Linux, installing `psycopg2-binary` may require system packages (e.g. `libpq-dev`, `build-essential`).

6) Environment file (optional)
   - A sample env file has been added at `.env.sample` with placeholders:

```
DJANGO_SECRET_KEY=REPLACE_WITH_SECURE_RANDOM_KEY
DATABASE_URL=postgres://user:password@host:5432/dbname
DJANGO_DEBUG=False
ALLOWED_HOSTS=eventhub-lovat.vercel.app,example.onrender.com
CORS_ALLOW_ALL_ORIGINS=True
```

   - Generate a secure Django secret locally with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

   - Do not commit real secrets to the repo. Paste values into Render service Environment Variables or keep a local `.env` for development.
