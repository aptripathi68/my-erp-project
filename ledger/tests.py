from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
import openpyxl

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
        self.assertContains(response, "Store Creation")
        self.assertContains(response, "Item Entry In Store")
        self.assertContains(response, "Existing Store Locations")
        self.assertContains(response, "Edit")
        self.assertContains(response, "Delete")
        self.assertContains(response, "Reserved / Inactive Store Locations")
        self.assertContains(response, "Delete Status")

    def test_opening_raw_inward_posts_to_ledger(self):
        response = self.client.post(
            reverse("ledger:create_inventory_inward"),
            {
                "entry_type": "OPENING",
                "stock_for": "PROJECT",
                "object_type": "RAW",
                "group2": self.group2.id,
                "section_name": self.item.section_name,
                "grade_selector": self.grade.id,
                "item": self.item.id,
                "location": self.store.id,
                "project_reference": "PRJ-OPEN-01",
                "project_name": "Opening Capture",
                "qty": "2.000",
                "weight": "125.500",
                "qr_code": "1234567890123456",
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

    def test_every_inward_entry_requires_qr(self):
        response = self.client.post(
            reverse("ledger:create_inventory_inward"),
            {
                "entry_type": "OPENING",
                "stock_for": "PROJECT",
                "object_type": "RAW",
                "group2": self.group2.id,
                "section_name": self.item.section_name,
                "grade_selector": self.grade.id,
                "item": self.item.id,
                "location": self.store.id,
                "project_reference": "PRJ-02",
                "qty": "1.000",
                "weight": "22.000",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "QR code scanning is compulsory for every store inward entry.")

    def test_project_entry_requires_project_reference(self):
        response = self.client.post(
            reverse("ledger:create_inventory_inward"),
            {
                "entry_type": "OPENING",
                "stock_for": "PROJECT",
                "object_type": "RAW",
                "group2": self.group2.id,
                "section_name": self.item.section_name,
                "grade_selector": self.grade.id,
                "item": self.item.id,
                "location": self.store.id,
                "qty": "1.000",
                "weight": "10.000",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Project reference is required")

    def test_temporary_issue_and_return_update_bridge_status(self):
        stock_object = StockObject.objects.create(
            object_type="RAW",
            source_type="OPENING",
            item=self.item,
            qty=Decimal("1.000"),
            weight=Decimal("100.000"),
            qr_code="1234567890123456",
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
                "qr_code": "1234567890123456",
                "qty": "1.000",
                "weight": "60.000",
                "remarks": "Urgent fabrication usage",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        issue_txn = StockTxn.objects.get(txn_type="TEMP_ISSUE")
        self.assertEqual(issue_txn.bridge_status, "PENDING_ERP_INTEGRATION")

    def test_temporary_issue_requires_qr_scan(self):
        stock_object = StockObject.objects.create(
            object_type="RAW",
            source_type="OPENING",
            item=self.item,
            qty=Decimal("1.000"),
            weight=Decimal("25.000"),
            qr_code="1111222233334444",
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
            weight=Decimal("25.000"),
            to_location=self.store,
        )
        from ledger.services.stock_engine import post_stock_txn
        post_stock_txn(inward_txn.id)

        response = self.client.post(
            reverse("ledger:create_temporary_issue"),
            {
                "project_reference": "PRJ-QR-01",
                "project_name": "QR Required Project",
                "item": self.item.id,
                "source_location": self.store.id,
                "destination_location": self.fabrication.id,
                "qty": "1.000",
                "weight": "10.000",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "QR code scanning is compulsory before item exit from store.")

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

    def test_delete_location_marks_store_inactive(self):
        response = self.client.post(reverse("ledger:delete_location", args=[self.store.id]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.store.refresh_from_db()
        self.assertFalse(self.store.is_active)

    def test_admin_can_permanently_delete_inactive_unused_store(self):
        admin_user = User.objects.create_user(
            username="admin1",
            password="testpass123",
            role="Admin",
            is_staff=True,
        )
        inactive_store = StockLocation.objects.create(name="Unused Store", location_type="STORE", is_active=False)
        self.client.login(username="admin1", password="testpass123")
        response = self.client.post(reverse("ledger:permanent_delete_location", args=[inactive_store.id]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(StockLocation.objects.filter(id=inactive_store.id).exists())

    def test_reserved_store_shows_safe_to_delete_status(self):
        StockLocation.objects.create(name="Unused Store", location_type="STORE", is_active=False)
        response = self.client.get(reverse("ledger:inventory_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Safe to delete")

    def test_item_entry_form_uses_dependent_item_master_fields(self):
        response = self.client.get(reverse("ledger:create_inventory_inward"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Group-2")
        self.assertContains(response, "Section Name")
        self.assertContains(response, "Grade")
        self.assertContains(response, "Item Description")

    def test_inventory_dashboard_shows_store_item_register_section(self):
        response = self.client.get(reverse("ledger:inventory_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Store-wise Items in Store")
        self.assertContains(response, "Download Excel")

    def test_store_item_excel_export_downloads_filtered_rows(self):
        stock_object = StockObject.objects.create(
            object_type="RAW",
            source_type="OPENING",
            item=self.item,
            qty=Decimal("2.000"),
            weight=Decimal("20.000"),
            qr_code="9999888877776666",
        )
        txn = StockTxn.objects.create(
            txn_type="OPENING_RAW",
            entry_source_type="OPENING",
            created_by=self.user,
        )
        txn.lines.create(
            item=self.item,
            stock_object=stock_object,
            qty=Decimal("2.000"),
            weight=Decimal("20.000"),
            to_location=self.store,
        )
        from ledger.services.stock_engine import post_stock_txn
        post_stock_txn(txn.id)

        response = self.client.get(
            reverse("ledger:export_store_stock_excel"),
            {"store": self.store.id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        wb = openpyxl.load_workbook(BytesIO(response.content))
        ws = wb.active
        values = list(ws.iter_rows(values_only=True))
        flat = " ".join("" if value is None else str(value) for row in values for value in row)
        self.assertIn("Main Store", flat)
        self.assertIn(self.item.item_description, flat)

    def test_admin_can_transfer_reserved_store_records_to_active_store(self):
        admin_user = User.objects.create_user(
            username="admin2",
            password="testpass123",
            role="Admin",
            is_staff=True,
        )
        reserved_store = StockLocation.objects.create(name="Old Test Store", location_type="STORE", is_active=False)
        target_store = StockLocation.objects.create(name="New Main Store", location_type="STORE", is_active=True)
        txn = StockTxn.objects.create(
            txn_type="OPENING_RAW",
            entry_source_type="OPENING",
            created_by=self.user,
            posted=True,
        )
        StockLedgerEntry.objects.create(
            txn=txn,
            item=self.item,
            location=reserved_store,
            qty=Decimal("1.000"),
            weight=Decimal("10.000"),
        )
        self.client.login(username="admin2", password="testpass123")
        response = self.client.post(
            reverse("ledger:transfer_store_records", args=[reserved_store.id]),
            {"target_location": target_store.id},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(StockLedgerEntry.objects.filter(location=reserved_store).exists())
        self.assertTrue(StockLedgerEntry.objects.filter(location=target_store).exists())
