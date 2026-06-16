from django.db import connection
from django.test import TestCase

from config.db_migrations import (
    PAYMENTS_0002,
    PAYMENTS_0003,
    PAYMENTS_0004,
    _applied_migrations,
    _payment_schema_status,
    apply_payment_order_tables_hotfix,
    repair_payments_schema,
)


class PaymentSchemaRepairTests(TestCase):
    def test_payment_schema_ready_after_migrate(self):
        status = _payment_schema_status()
        self.assertTrue(status['tables']['payments_paymentorder'])
        self.assertTrue(status['tables']['payments_organizernotification'])
        self.assertTrue(status['tables']['payments_attendeenotification'])
        self.assertTrue(status['ready'])

    def test_payments_migrations_recorded(self):
        applied = _applied_migrations('payments')
        self.assertIn(PAYMENTS_0002, applied)
        self.assertIn(PAYMENTS_0003, applied)
        self.assertIn(PAYMENTS_0004, applied)

    def test_repair_payments_schema_is_idempotent(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Postgres-only repair helpers')
        first = repair_payments_schema()
        second = repair_payments_schema()
        self.assertEqual(second, [])
        self.assertTrue(_payment_schema_status()['ready'])

    def test_payment_order_hotfix_is_idempotent(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Postgres-only hotfix helpers')
        self.assertEqual(apply_payment_order_tables_hotfix(), [])
        self.assertTrue(_payment_schema_status()['ready'])
