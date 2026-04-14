# Health Facility Feedback System

A Django application for collecting anonymous health facility feedback through QR-code-driven forms and reviewing submissions through a secure staff dashboard.

## Features

- Anonymous public feedback form with optional demographic fields
- Facility management with auto-generated QR codes
- Secure staff dashboard for analytics and submission review
- Filterable exports to CSV and Excel
- Basic IP rate limiting for spam protection
- PostgreSQL-ready configuration for local and production deployments

## Project Structure

```text
backend/
  config/
  dashboard/
  facilities/
  feedback/
  static/
  templates/
```

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a PostgreSQL database named `health_feedback`.
4. Copy `.env.example` values into your environment.
5. Run migrations:

```bash
python manage.py migrate
```

6. Seed facilities:

```bash
python manage.py seed_facilities
```

7. Create an admin user:

```bash
python manage.py createsuperuser
```

8. Start the development server:

```bash
python manage.py runserver
```

## Key URLs

- Public feedback form: `/feedback/`
- Example QR target: `/feedback/?facility_id=1`
- Staff dashboard: `/dashboard/`
- Django admin: `/admin/`

## Production Notes

- Set `DJANGO_DEBUG=False`
- Use a strong `DJANGO_SECRET_KEY`
- Set `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`
- Enable `DJANGO_SECURE_SSL_REDIRECT=True` behind HTTPS
- Run `python manage.py collectstatic`
