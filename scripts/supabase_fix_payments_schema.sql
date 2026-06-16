-- EventHub: fix stuck payments migrations on Supabase / Postgres
-- Run in Supabase SQL Editor when /api/events/run-migrations/ reports:
--   error: column "legacy_event_id" of relation "payments_payment" already exists
--   payment_schema.ready: false
--
-- Safe to re-run: uses IF EXISTS / IF NOT EXISTS guards.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1) Inspect current state (optional — results appear in the query output tab)
-- ---------------------------------------------------------------------------
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'payments_payment'
ORDER BY ordinal_position;

SELECT app, name, applied
FROM django_migrations
WHERE app = 'payments'
ORDER BY applied;

-- ---------------------------------------------------------------------------
-- 2) Unblock payments.0002 — legacy_event_id exists but migration not recorded
-- ---------------------------------------------------------------------------

-- If BOTH integer event_id and legacy_event_id exist, keep legacy and drop integer.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'payments_payment' AND column_name = 'legacy_event_id'
  ) AND EXISTS (
    SELECT 1 FROM information_schema.columns c
    WHERE c.table_schema = 'public' AND c.table_name = 'payments_payment' AND c.column_name = 'event_id'
  ) AND NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'public'
      AND kcu.table_name = 'payments_payment'
      AND kcu.column_name = 'event_id'
  ) THEN
    UPDATE payments_payment
    SET legacy_event_id = event_id
    WHERE legacy_event_id IS NULL AND event_id IS NOT NULL;

    ALTER TABLE payments_payment DROP COLUMN event_id;
  END IF;
END $$;

-- Add FK event_id if missing (post-rename state).
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'payments_payment' AND column_name = 'legacy_event_id'
  ) AND NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'public'
      AND kcu.table_name = 'payments_payment'
      AND kcu.column_name = 'event_id'
  ) THEN
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'payments_payment' AND column_name = 'event_id'
    ) THEN
      ALTER TABLE payments_payment
        ADD COLUMN event_id bigint NULL
        REFERENCES events_event(id) DEFERRABLE INITIALLY DEFERRED;
    END IF;

    UPDATE payments_payment pp
    SET event_id = pp.legacy_event_id
    WHERE pp.event_id IS NULL
      AND pp.legacy_event_id IS NOT NULL
      AND EXISTS (SELECT 1 FROM events_event e WHERE e.id = pp.legacy_event_id);

    CREATE INDEX IF NOT EXISTS payments_pa_status_7ad4af_idx ON payments_payment (status);
  END IF;
END $$;

-- Apply payments.0003 — remove legacy_event_id once FK is in place.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'payments_payment' AND column_name = 'legacy_event_id'
  ) AND EXISTS (
    SELECT 1
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'public'
      AND kcu.table_name = 'payments_payment'
      AND kcu.column_name = 'event_id'
  ) THEN
    ALTER TABLE payments_payment DROP COLUMN legacy_event_id;
  END IF;
END $$;

-- Record payments.0002 and .0003 if not already present.
INSERT INTO django_migrations (app, name, applied)
SELECT 'payments', '0002_remove_payment_event_id_payment_event_and_more', NOW()
WHERE NOT EXISTS (
  SELECT 1 FROM django_migrations
  WHERE app = 'payments' AND name = '0002_remove_payment_event_id_payment_event_and_more'
);

INSERT INTO django_migrations (app, name, applied)
SELECT 'payments', '0003_remove_payment_legacy_event_id', NOW()
WHERE NOT EXISTS (
  SELECT 1 FROM django_migrations
  WHERE app = 'payments' AND name = '0003_remove_payment_legacy_event_id'
);

-- ---------------------------------------------------------------------------
-- 3) Create checkout tables from payments.0004 (if missing)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS payments_paymentorder (
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
);

CREATE INDEX IF NOT EXISTS payments_pa_status_8a1f2c_idx ON payments_paymentorder (status);
CREATE INDEX IF NOT EXISTS payments_pa_attende_3b4c5d_idx ON payments_paymentorder (attendee_id, status);
CREATE INDEX IF NOT EXISTS payments_pa_organiz_6e7f8a_idx ON payments_paymentorder (organizer_id, status);

CREATE TABLE IF NOT EXISTS payments_organizernotification (
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
);

CREATE INDEX IF NOT EXISTS payments_or_organiz_9a0b1c_idx
  ON payments_organizernotification (organizer_id, is_read);

CREATE TABLE IF NOT EXISTS payments_attendeenotification (
    id bigserial PRIMARY KEY,
    title varchar(200) NOT NULL,
    message text NOT NULL,
    notification_type varchar(20) NOT NULL DEFAULT 'info',
    is_read boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    attendee_id bigint NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
    payment_order_id bigint NULL REFERENCES payments_paymentorder(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS payments_at_attende_2d3e4f_idx
  ON payments_attendeenotification (attendee_id, is_read);

INSERT INTO django_migrations (app, name, applied)
SELECT 'payments', '0004_paymentorder_organizernotification_attendeentification', NOW()
WHERE NOT EXISTS (
  SELECT 1 FROM django_migrations
  WHERE app = 'payments' AND name = '0004_paymentorder_organizernotification_attendeentification'
);

COMMIT;

-- ---------------------------------------------------------------------------
-- 4) Verify
-- ---------------------------------------------------------------------------
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'payments_paymentorder',
    'payments_organizernotification',
    'payments_attendeenotification'
  )
ORDER BY table_name;

SELECT app, name, applied
FROM django_migrations
WHERE app = 'payments'
ORDER BY applied;
