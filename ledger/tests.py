from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from masters.models import Grade, Group2, Item

from .models import StockLedgerEntry, StockLocation, StockObject, StockTxn


User = get_user_model()


class InventoryManagementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="store1",
            password="testpass123",
            role="Store",
            is_staff=True,
        )
        self.client.login(username="store1", password="testpass123")

        self.group2 = Group2.objects.create(code="RM", name="Raw Material")
        self.grade = Grade.objects.create(group2=self.group2, code="IS:2062", name="E250BR")
        self.item = Item.objects.create(
            group2=self.group2,
            grade=self.grade,
            item_description="ISMC75 IS:2062, E250BR",
            section_name="ISMC75",
            unit_weight=Decimal("7.140"),
        )
        self.store = StockLocation.objects.create(name="Main Store", location_type="STORE")
        self.fabrication = StockLocation.objects.create(name="Fab Yard", location_type="FABRICATION")

    def test_inventory_dashboard_loads(self):
        response = self.client.get(reverse("ledger:inventory_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inventory Management")

    def test_opening_raw_inward_posts_to_ledger(self):
        response = self.client.post(
            reverse("ledger:create_inventory_inward"),
            {
                "entry_type": "OPENING",
                "object_type": "RAW",
                "item": self.item.id,
                "location": self.store.id,
                "qty": "2.000",
                "weight": "125.500",
                "reference_no": "OPEN-001",
                "remarks": "Initial raw material capture",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        txn = StockTxn.objects.get(txn_type="OPENING_RAW")
        self.assertTrue(txn.posted)
        ledger_row = StockLedgerEntry.objects.get(txn=txn)
        self.assertEqual(ledger_row.location, self.store)
        self.assertEqual(ledger_row.weight, Decimal("125.500"))

    def test_offcut_inward_requires_qr(self):
        response = self.client.post(
            reverse("ledger:create_inventory_inward"),
            {
                "entry_type": "OPENING",
                "object_type": "OFFCUT",
                "item": self.item.id,
                "location": self.store.id,
                "qty": "1.000",
                "weight": "22.000",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "QR code is compulsory for off-cuts.")

    def test_temporary_issue_and_return_update_bridge_status(self):
        stock_object = StockObject.objects.create(
            object_type="RAW",
            source_type="OPENING",
            item=self.item,
            qty=Decimal("1.000"),
            weight=Decimal("100.000"),
        )
        inward_txn = StockTxn.objects.create(
            txn_type="OPENING_RAW",
            entry_source_type="OPENING",
            created_by=self.user,
        )
        inward_txn.lines.create(
            item=self.item,
            stock_object=stock_object,
            qty=Decimal("1.000"),
            weight=Decimal("100.000"),
            to_location=self.store,
        )
        from ledger.services.stock_engine import post_stock_txn
        post_stock_txn(inward_txn.id)

        response = self.client.post(
            reverse("ledger:create_temporary_issue"),
            {
                "project_reference": "PRJ-01",
                "project_name": "Bridge Project",
                "item": self.item.id,
                "source_location": self.store.id,
                "destination_location": self.fabrication.id,
                "qty": "1.000",
                "weight": "60.000",
                "remarks": "Urgent fabrication usage",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        issue_txn = StockTxn.objects.get(txn_type="TEMP_ISSUE")
        self.assertEqual(issue_txn.bridge_status, "PENDING_ERP_INTEGRATION")

        response = self.client.post(
            reverse("ledger:create_temporary_return"),
            {
                "issue_txn": issue_txn.id,
                "return_type": "RAW",
                "destination_location": self.store.id,
                "qty": "1.000",
                "weight": "60.000",
                "remarks": "Unused stock returned",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        issue_txn.refresh_from_db()
        self.assertEqual(issue_txn.bridge_status, "RETURNED")
