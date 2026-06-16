"""
Database migration helpers for Supabase/Postgres deployments.

Repairs known inconsistent migration history (e.g. events.0005 applied before
events.0004) so `migrate` can complete and auth tables stay in sync.
"""

from __future__ import annotations

import io
import logging
from typing import Any

from django.core.management import call_command
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone

logger = logging.getLogger(__name__)

# events.0005 was deployed to production before 0004 existed, leaving a gap.
EVENTS_REPAIR_FAKES = (
    ('events', '0004_eventimage', '0005_alter_event_banner_image_alter_eventimage_image'),
)

AUTH_COLUMN_HOTFIXES = (
    # (column_name, postgres_ddl)
    ('avatar', "ALTER TABLE accounts_user ADD COLUMN IF NOT EXISTS avatar varchar(100)"),
    (
        'avatar_url',
        "ALTER TABLE accounts_user ADD COLUMN IF NOT EXISTS avatar_url varchar(500) "
        "NOT NULL DEFAULT ''",
    ),
)

MPESA_COLUMN_HOTFIXES = (
    ('mpesa_display_name', "ALTER TABLE accounts_user ADD COLUMN IF NOT EXISTS mpesa_display_name varchar(150) NOT NULL DEFAULT ''"),
    ('mpesa_paybill', "ALTER TABLE accounts_user ADD COLUMN IF NOT EXISTS mpesa_paybill varchar(20) NOT NULL DEFAULT ''"),
    ('mpesa_till', "ALTER TABLE accounts_user ADD COLUMN IF NOT EXISTS mpesa_till varchar(20) NOT NULL DEFAULT ''"),
    ('mpesa_pochi', "ALTER TABLE accounts_user ADD COLUMN IF NOT EXISTS mpesa_pochi varchar(20) NOT NULL DEFAULT ''"),
    ('mpesa_send_money', "ALTER TABLE accounts_user ADD COLUMN IF NOT EXISTS mpesa_send_money varchar(20) NOT NULL DEFAULT ''"),
)

PAYMENT_REQUIRED_TABLES = (
    'payments_paymentorder',
    'payments_organizernotification',
    'payments_attendeenotification',
)

CORE_REQUIRED_TABLES = (
    'bookings_ticket',
    'reviews_eventreview',
    'accounts_adminnotificationstate',
    'events_event',
)

PAYMENTS_0002 = '0002_remove_payment_event_id_payment_event_and_more'
PAYMENTS_0003 = '0003_remove_payment_legacy_event_id'
PAYMENTS_0004 = '0004_paymentorder_organizernotification_attendeentification'
PAYMENTS_0005 = '0005_paymentorder_screenshot_verified'
PAYMENTS_0006 = '0006_paymentorder_screenshot_data'
PAYMENTS_0008 = '0008_paymentorder_stk_fields'

PAYMENT_ORDER_STK_COLUMN_HOTFIXES = (
    ('payment_rail', "ALTER TABLE payments_paymentorder ADD COLUMN IF NOT EXISTS payment_rail varchar(20) NOT NULL DEFAULT 'manual'"),
    ('checkout_request_id', 'ALTER TABLE payments_paymentorder ADD COLUMN IF NOT EXISTS checkout_request_id varchar(100) NULL'),
    ('merchant_request_id', "ALTER TABLE payments_paymentorder ADD COLUMN IF NOT EXISTS merchant_request_id varchar(100) NOT NULL DEFAULT ''"),
    ('mpesa_receipt', "ALTER TABLE payments_paymentorder ADD COLUMN IF NOT EXISTS mpesa_receipt varchar(50) NOT NULL DEFAULT ''"),
    ('payer_phone', "ALTER TABLE payments_paymentorder ADD COLUMN IF NOT EXISTS payer_phone varchar(15) NOT NULL DEFAULT ''"),
    ('stk_status', "ALTER TABLE payments_paymentorder ADD COLUMN IF NOT EXISTS stk_status varchar(20) NOT NULL DEFAULT ''"),
)


def _applied_migrations(app_label: str) -> set[str]:
    return set(
        MigrationRecorder.Migration.objects.filter(app=app_label).values_list('name', flat=True)
    )


def _record_migration(app_label: str, name: str) -> bool:
    """Insert a migration row directly (bypasses Django's dependency validator)."""
    recorder = MigrationRecorder(connection)
    if recorder.migration_qs.filter(app=app_label, name=name).exists():
        return False
    recorder.migration_qs.create(app=app_label, name=name, applied=timezone.now())
    return True


def _table_columns(table_name: str) -> set[str]:
    with connection.cursor() as cursor:
        if connection.vendor == 'postgresql':
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = %s",
                [table_name],
            )
            return {row[0] for row in cursor.fetchall()}
        if connection.vendor == 'sqlite':
            cursor.execute(f'PRAGMA table_info({table_name})')
            return {row[1] for row in cursor.fetchall()}
    return set()


def _column_has_fk(table_name: str, column_name: str) -> bool:
    if connection.vendor != 'postgresql':
        return False
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public'
                  AND kcu.table_name = %s
                  AND kcu.column_name = %s
            )
            """,
            [table_name, column_name],
        )
        return bool(cursor.fetchone()[0])


def _table_exists(table_name: str) -> bool:
    with connection.cursor() as cursor:
        if connection.vendor == 'postgresql':
            cursor.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = %s)",
                [table_name],
            )
            return bool(cursor.fetchone()[0])
        if connection.vendor == 'sqlite':
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=%s",
                [table_name],
            )
            return cursor.fetchone() is not None
    return False


def repair_migration_history() -> list[str]:
    """Record missing dependency migrations when a later one is already applied."""
    repairs: list[str] = []
    for app_label, missing_name, later_name in EVENTS_REPAIR_FAKES:
        applied = _applied_migrations(app_label)
        if later_name in applied and missing_name not in applied:
            if _record_migration(app_label, missing_name):
                repairs.append(f'recorded {app_label}.{missing_name}')
            else:
                repairs.append(f'skipped {app_label}.{missing_name} (already present)')

    accounts_applied = _applied_migrations('accounts')
    if (
        _table_exists('accounts_apikey')
        and '0006_apikey_teammember_user_accounts_us_role_1fa9a5_idx_and_more' not in accounts_applied
    ):
        if _record_migration('accounts', '0006_apikey_teammember_user_accounts_us_role_1fa9a5_idx_and_more'):
            repairs.append('recorded accounts.0006 (apikey table already existed)')

    user_columns = set(_auth_schema_status().get('user_columns') or [])
    if {'avatar', 'avatar_url'}.issubset(user_columns):
        if '0008_user_avatar_user_avatar_url' not in accounts_applied:
            if _record_migration('accounts', '0008_user_avatar_user_avatar_url'):
                repairs.append('recorded accounts.0008 (avatar columns already existed)')

    mpesa_columns = {'mpesa_display_name', 'mpesa_paybill', 'mpesa_till', 'mpesa_pochi', 'mpesa_send_money'}
    if mpesa_columns.issubset(user_columns):
        if '0009_user_mpesa_fields' not in accounts_applied:
            if _record_migration('accounts', '0009_user_mpesa_fields'):
                repairs.append('recorded accounts.0009 (mpesa columns already existed)')

    payments_applied = _applied_migrations('payments')
    if _table_exists('payments_paymentorder') and PAYMENTS_0004 not in payments_applied:
        if _record_migration('payments', PAYMENTS_0004):
            repairs.append('recorded payments.0004 (payment tables already existed)')

    payment_order_columns = _table_columns('payments_paymentorder') if _table_exists('payments_paymentorder') else set()
    if 'screenshot_verified' in payment_order_columns and PAYMENTS_0005 not in payments_applied:
        if _record_migration('payments', PAYMENTS_0005):
            repairs.append('recorded payments.0005 (screenshot_verified column already existed)')
    if 'screenshot_data' in payment_order_columns and PAYMENTS_0006 not in payments_applied:
        if _record_migration('payments', PAYMENTS_0006):
            repairs.append('recorded payments.0006 (screenshot_data column already existed)')

    repairs.extend(repair_payments_schema())

    return repairs


def repair_payments_schema() -> list[str]:
    """
    Fix payments_payment when production is stuck on payments.0002.

    Common failure: legacy_event_id already exists (partial 0002) while Django
    history still only has 0001_initial, so migrate cannot reach 0004.
    """
    if connection.vendor != 'postgresql' or not _table_exists('payments_payment'):
        return []

    actions: list[str] = []
    applied = _applied_migrations('payments')

    def record(name: str) -> None:
        if name not in applied and _record_migration('payments', name):
            actions.append(f'recorded payments.{name}')
            applied.add(name)

    cols = _table_columns('payments_payment')
    has_legacy = 'legacy_event_id' in cols
    has_event_id = 'event_id' in cols
    event_id_is_fk = has_event_id and _column_has_fk('payments_payment', 'event_id')

    # Both integer event_id and legacy_event_id — consolidate before 0002 can run.
    if has_legacy and has_event_id and not event_id_is_fk:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE payments_payment
                SET legacy_event_id = event_id
                WHERE legacy_event_id IS NULL AND event_id IS NOT NULL
                """
            )
            cursor.execute('ALTER TABLE payments_payment DROP COLUMN event_id')
        actions.append('removed duplicate integer payments_payment.event_id')
        cols = _table_columns('payments_payment')
        has_event_id = 'event_id' in cols
        event_id_is_fk = has_event_id and _column_has_fk('payments_payment', 'event_id')

    # 0002 rename done (legacy exists) but FK column / index missing.
    if 'legacy_event_id' in cols and not event_id_is_fk:
        with connection.cursor() as cursor:
            if 'event_id' not in cols:
                cursor.execute(
                    """
                    ALTER TABLE payments_payment
                    ADD COLUMN event_id bigint NULL
                    REFERENCES events_event(id) DEFERRABLE INITIALLY DEFERRED
                    """
                )
                actions.append('added payments_payment.event_id FK')
            cursor.execute(
                """
                UPDATE payments_payment pp
                SET event_id = pp.legacy_event_id
                WHERE pp.event_id IS NULL
                  AND pp.legacy_event_id IS NOT NULL
                  AND EXISTS (
                      SELECT 1 FROM events_event e WHERE e.id = pp.legacy_event_id
                  )
                """
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS payments_pa_status_7ad4af_idx ON payments_payment (status)'
            )
            actions.append('backfilled payments_payment.event_id from legacy_event_id')
        record(PAYMENTS_0002)
        cols = _table_columns('payments_payment')
        has_legacy = 'legacy_event_id' in cols
        event_id_is_fk = 'event_id' in cols and _column_has_fk('payments_payment', 'event_id')

    # 0002 complete — drop legacy column (0003).
    if 'legacy_event_id' in cols and event_id_is_fk:
        with connection.cursor() as cursor:
            cursor.execute('ALTER TABLE payments_payment DROP COLUMN legacy_event_id')
        actions.append('dropped payments_payment.legacy_event_id')
        record(PAYMENTS_0002)
        record(PAYMENTS_0003)
        cols = _table_columns('payments_payment')
        has_legacy = False

    # Already at post-0003 schema but history not recorded.
    if not has_legacy and event_id_is_fk:
        record(PAYMENTS_0002)
        record(PAYMENTS_0003)

    return actions


def apply_payment_order_tables_hotfix() -> list[str]:
    """Create checkout tables when payments.0004 cannot be applied via migrate."""
    if connection.vendor != 'postgresql':
        return []
    if _payment_schema_status().get('ready'):
        return []

    applied: list[str] = []
    with connection.cursor() as cursor:
        if not _table_exists('payments_paymentorder'):
            cursor.execute(
                """
                CREATE TABLE payments_paymentorder (
                    id bigserial PRIMARY KEY,
                    ticket_type varchar(20) NOT NULL,
                    quantity integer NOT NULL CHECK (quantity >= 0),
                    unit_price numeric(10, 2) NOT NULL,
                    total_amount numeric(10, 2) NOT NULL,
                    status varchar(20) NOT NULL,
                    screenshot varchar(100) NULL,
                    submitted_mpesa_name varchar(150) NOT NULL DEFAULT '',
                    ocr_raw_text text NOT NULL DEFAULT '',
                    verification_message text NOT NULL DEFAULT '',
                    created_at timestamptz NOT NULL DEFAULT NOW(),
                    updated_at timestamptz NOT NULL DEFAULT NOW(),
                    attendee_id bigint NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
                    event_id bigint NOT NULL REFERENCES events_event(id) ON DELETE CASCADE,
                    organizer_id bigint NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
                    ticket_id bigint NULL REFERENCES bookings_ticket(id) ON DELETE SET NULL
                )
                """
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS payments_pa_status_8a1f2c_idx ON payments_paymentorder (status)'
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS payments_pa_attende_3b4c5d_idx '
                'ON payments_paymentorder (attendee_id, status)'
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS payments_pa_organiz_6e7f8a_idx '
                'ON payments_paymentorder (organizer_id, status)'
            )
            applied.append('created payments_paymentorder')

        if not _table_exists('payments_organizernotification'):
            cursor.execute(
                """
                CREATE TABLE payments_organizernotification (
                    id bigserial PRIMARY KEY,
                    title varchar(200) NOT NULL,
                    message text NOT NULL,
                    notification_type varchar(20) NOT NULL DEFAULT 'info',
                    is_read boolean NOT NULL DEFAULT false,
                    requires_action boolean NOT NULL DEFAULT false,
                    action_type varchar(50) NOT NULL DEFAULT '',
                    created_at timestamptz NOT NULL DEFAULT NOW(),
                    organizer_id bigint NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
                    payment_order_id bigint NULL REFERENCES payments_paymentorder(id) ON DELETE CASCADE
                )
                """
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS payments_or_organiz_9a0b1c_idx '
                'ON payments_organizernotification (organizer_id, is_read)'
            )
            applied.append('created payments_organizernotification')

        if not _table_exists('payments_attendeenotification'):
            cursor.execute(
                """
                CREATE TABLE payments_attendeenotification (
                    id bigserial PRIMARY KEY,
                    title varchar(200) NOT NULL,
                    message text NOT NULL,
                    notification_type varchar(20) NOT NULL DEFAULT 'info',
                    is_read boolean NOT NULL DEFAULT false,
                    created_at timestamptz NOT NULL DEFAULT NOW(),
                    attendee_id bigint NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
                    payment_order_id bigint NULL REFERENCES payments_paymentorder(id) ON DELETE CASCADE
                )
                """
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS payments_at_attende_2d3e4f_idx '
                'ON payments_attendeenotification (attendee_id, is_read)'
            )
            applied.append('created payments_attendeenotification')

    if _payment_schema_status().get('ready'):
        payment_cols = _table_columns('payments_paymentorder')
        if 'screenshot_verified' not in payment_cols:
            with connection.cursor() as cursor:
                cursor.execute(
                    'ALTER TABLE payments_paymentorder '
                    'ADD COLUMN IF NOT EXISTS screenshot_verified boolean NULL'
                )
            applied.append('added payments_paymentorder.screenshot_verified')
            payment_cols = _table_columns('payments_paymentorder')
        if PAYMENTS_0004 not in _applied_migrations('payments'):
            if _record_migration('payments', PAYMENTS_0004):
                applied.append(f'recorded payments.{PAYMENTS_0004}')
        if PAYMENTS_0005 not in _applied_migrations('payments'):
            if _record_migration('payments', PAYMENTS_0005):
                applied.append(f'recorded payments.{PAYMENTS_0005}')
        if 'screenshot_data' not in payment_cols:
            with connection.cursor() as cursor:
                cursor.execute(
                    'ALTER TABLE payments_paymentorder '
                    'ADD COLUMN IF NOT EXISTS screenshot_data text NOT NULL DEFAULT \'\''
                )
            applied.append('added payments_paymentorder.screenshot_data')
        if PAYMENTS_0006 not in _applied_migrations('payments'):
            if _record_migration('payments', PAYMENTS_0006):
                applied.append(f'recorded payments.{PAYMENTS_0006}')
        payment_cols = _table_columns('payments_paymentorder')
        for column_name, ddl in PAYMENT_ORDER_STK_COLUMN_HOTFIXES:
            if column_name not in payment_cols:
                with connection.cursor() as cursor:
                    cursor.execute(ddl)
                applied.append(f'added payments_paymentorder.{column_name}')
                payment_cols = _table_columns('payments_paymentorder')
        if PAYMENTS_0008 not in _applied_migrations('payments'):
            if _record_migration('payments', PAYMENTS_0008):
                applied.append(f'recorded payments.{PAYMENTS_0008}')

    return applied


def apply_auth_column_hotfixes() -> list[str]:
    """Add auth-critical columns when migration history is still out of sync."""
    if connection.vendor != 'postgresql':
        return []

    applied: list[str] = []
    existing = set(_auth_schema_status().get('user_columns') or [])
    try:
        with connection.cursor() as cursor:
            for column_name, ddl in AUTH_COLUMN_HOTFIXES:
                if column_name not in existing:
                    cursor.execute(ddl)
                    applied.append(f'added accounts_user.{column_name}')
    except Exception:
        logger.exception('Auth column hotfix failed')
        raise
    return applied


def apply_mpesa_column_hotfixes() -> list[str]:
    """Add M-Pesa organizer settings columns when migration history is out of sync."""
    if connection.vendor != 'postgresql':
        return []

    applied: list[str] = []
    existing = set(_auth_schema_status().get('user_columns') or [])
    try:
        with connection.cursor() as cursor:
            for column_name, ddl in MPESA_COLUMN_HOTFIXES:
                if column_name not in existing:
                    cursor.execute(ddl)
                    applied.append(f'added accounts_user.{column_name}')
    except Exception:
        logger.exception('M-Pesa column hotfix failed')
        raise
    return applied


def _core_schema_status() -> dict[str, Any]:
    status: dict[str, Any] = {
        'tables': {},
        'ready': False,
        'error': None,
    }
    try:
        for table_name in CORE_REQUIRED_TABLES:
            status['tables'][table_name] = _table_exists(table_name)
        status['ready'] = all(status['tables'].values())
    except Exception as exc:
        status['error'] = str(exc)
    return status


def _schema_ready() -> bool:
    return (
        bool(_auth_schema_status().get('ready'))
        and bool(_payment_schema_status().get('ready'))
        and bool(_core_schema_status().get('ready'))
    )


def _payment_schema_status() -> dict[str, Any]:
    status: dict[str, Any] = {
        'tables': {},
        'payments_payment_columns': [],
        'ready': False,
        'error': None,
    }
    try:
        for table_name in PAYMENT_REQUIRED_TABLES:
            status['tables'][table_name] = _table_exists(table_name)
        if _table_exists('payments_payment'):
            status['payments_payment_columns'] = sorted(_table_columns('payments_payment'))
        status['ready'] = all(status['tables'].values())
    except Exception as exc:
        status['error'] = str(exc)
    return status


def ensure_payment_schema() -> list[str]:
    """Run payments/accounts migrations and hotfixes until checkout tables exist."""
    actions: list[str] = []
    if _payment_schema_status().get('ready'):
        return actions

    actions.extend(repair_payments_schema())

    out = io.StringIO()
    err = io.StringIO()
    try:
        call_command('migrate', 'payments', interactive=False, stdout=out, stderr=err)
        actions.append('migrate payments')
    except Exception as exc:
        logger.warning('payments migrate failed after schema repair: %s', exc)
        actions.append(f'payments migrate failed: {exc}')

    if not _payment_schema_status().get('ready'):
        hotfix_actions = apply_payment_order_tables_hotfix()
        actions.extend(hotfix_actions)

    return actions


def run_migrations() -> dict[str, Any]:
    """Repair history, run migrate, hotfix auth columns, and return a structured result."""
    out = io.StringIO()
    err = io.StringIO()
    repairs: list[str] = []
    hotfixes: list[str] = []
    success = False
    error_msg = None

    payment_actions: list[str] = []
    payment_repairs: list[str] = []
    try:
        payment_repairs = repair_payments_schema()
        repairs = repair_migration_history()
        call_command('migrate', interactive=False, stdout=out, stderr=err)
        hotfixes = apply_auth_column_hotfixes()
        hotfixes.extend(apply_mpesa_column_hotfixes())
        payment_actions = ensure_payment_schema()
        success = _schema_ready()
        if not success:
            error_msg = 'Schema incomplete after migrate'
    except Exception as exc:
        error_msg = str(exc)
        payment_repairs.extend(repair_payments_schema())
        # Recover from partially-applied migrations (e.g. avatar column added via hotfix).
        extra_repairs = repair_migration_history()
        repairs.extend(extra_repairs)
        try:
            call_command('migrate', interactive=False, stdout=out, stderr=err)
            hotfixes = apply_auth_column_hotfixes()
            hotfixes.extend(apply_mpesa_column_hotfixes())
            payment_actions = ensure_payment_schema()
            success = _schema_ready()
            error_msg = None if success else 'Schema incomplete after migrate retry'
        except Exception as retry_exc:
            error_msg = str(retry_exc)
            try:
                hotfixes = apply_auth_column_hotfixes()
                hotfixes.extend(apply_mpesa_column_hotfixes())
                payment_actions = ensure_payment_schema()
                success = _schema_ready()
                if success:
                    error_msg = None
            except Exception as hotfix_exc:
                logger.exception('Schema hotfix after migrate failure also failed')
                error_msg = str(hotfix_exc)

    repairs = payment_repairs + repairs

    output = out.getvalue()
    if err.getvalue():
        output = (output + '\n' + err.getvalue()).strip()

    accounts_migrations = sorted(_applied_migrations('accounts'))
    payments_migrations = sorted(_applied_migrations('payments'))
    auth_tables = _auth_schema_status()
    payment_tables = _payment_schema_status()
    core_tables = _core_schema_status()

    return {
        'success': success,
        'repairs': repairs,
        'hotfixes': hotfixes,
        'payment_actions': payment_actions,
        'output': output,
        'error': error_msg,
        'accounts_migrations': accounts_migrations,
        'payments_migrations': payments_migrations,
        'auth_schema': auth_tables,
        'payment_schema': payment_tables,
        'core_schema': core_tables,
    }


def _auth_schema_status() -> dict[str, Any]:
    """Report whether auth-critical tables/columns exist."""
    status: dict[str, Any] = {
        'accounts_user_exists': False,
        'accounts_apitoken_exists': False,
        'user_columns': [],
        'ready': False,
        'error': None,
    }
    try:
        with connection.cursor() as cursor:
            if connection.vendor == 'postgresql':
                cursor.execute(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'accounts_user')"
                )
                status['accounts_user_exists'] = bool(cursor.fetchone()[0])

                cursor.execute(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'accounts_apitoken')"
                )
                status['accounts_apitoken_exists'] = bool(cursor.fetchone()[0])

                if status['accounts_user_exists']:
                    cursor.execute(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = 'accounts_user' "
                        "ORDER BY ordinal_position"
                    )
                    status['user_columns'] = [row[0] for row in cursor.fetchall()]
            elif connection.vendor == 'sqlite':
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='accounts_user'"
                )
                status['accounts_user_exists'] = cursor.fetchone() is not None
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='accounts_apitoken'"
                )
                status['accounts_apitoken_exists'] = cursor.fetchone() is not None
                if status['accounts_user_exists']:
                    cursor.execute('PRAGMA table_info(accounts_user)')
                    status['user_columns'] = [row[1] for row in cursor.fetchall()]

        required_user_columns = {'email', 'role', 'google_id', 'avatar_url'}
        status['ready'] = (
            status['accounts_user_exists']
            and status['accounts_apitoken_exists']
            and required_user_columns.issubset(set(status['user_columns']))
        )
    except Exception as exc:
        status['error'] = str(exc)
    return status
