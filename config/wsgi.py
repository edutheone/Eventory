"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os


from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()
app = application

# Run migrations on serverless/managed Postgres (Supabase via DATABASE_URL) with repair.
if os.environ.get('VERCEL') or os.environ.get('DATABASE_URL'):
    import logging
    _migration_logger = logging.getLogger('config.wsgi')
    try:
        from config.db_migrations import run_migrations
        result = run_migrations()
        if result.get('repairs'):
            _migration_logger.warning('Vercel migration repairs: %s', result['repairs'])
        if result.get('payment_actions'):
            _migration_logger.warning('Vercel payment schema actions: %s', result['payment_actions'])
        if not result.get('success'):
            _migration_logger.error(
                'Vercel startup migration failed: %s (payment_schema=%s)',
                result.get('error'),
                result.get('payment_schema'),
            )
    except Exception as e:
        _migration_logger.exception('Vercel startup migration failed: %s', e)


