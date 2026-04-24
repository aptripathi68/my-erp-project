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
        self.assertNotContains(response, "Correct Wrong QR / Quantity / Weight")

    def test_store_item_excel_export_downloads_filtered_rows(self):
        stock_object = StockObject.objects.create(
            object_type="RAW",
            source_type="OPENING",
            item=self.item,
            qty=Decimal("2.000"),
            weight=Decimal("20.000"),
            qr_code="9999888877776666",
            rack_number="R-01",
            shelf_number="S-02",
            bin_number="B-03",
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
        self.assertIn("R-01", flat)
        self.assertIn("S-02", flat)
        self.assertIn("B-03", flat)
        self.assertIn(self.item.item_description, flat)

    def test_store_user_can_edit_stored_item_non_stock_fields(self):
        stock_object = StockObject.objects.create(
            object_type="RAW",
            source_type="OPENING",
            item=self.item,
            qty=Decimal("1.000"),
            weight=Decimal("15.000"),
            qr_code="4444333322221111",
            rack_number="OLD-RACK",
            shelf_number="OLD-SHELF",
            bin_number="OLD-BIN",
            remarks="Old remarks",
        )
        txn = StockTxn.objects.create(
            txn_type="OPENING_RAW",
            entry_source_type="OPENING",
            created_by=self.user,
            posted=True,
        )
        StockLedgerEntry.objects.create(
            txn=txn,
            item=self.item,
            location=self.store,
            stock_object=stock_object,
            qty=Decimal("1.000"),
            weight=Decimal("15.000"),
        )

        response = self.client.post(
            reverse("ledger:edit_stock_object_details", args=[stock_object.id]),
            {
                "rack_number": "NEW-RACK",
                "shelf_number": "NEW-SHELF",
                "bin_number": "NEW-BIN",
                "remarks": "Corrected position",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        stock_object.refresh_from_db()
        self.assertEqual(stock_object.rack_number, "NEW-RACK")
        self.assertEqual(stock_object.shelf_number, "NEW-SHELF")
        self.assertEqual(stock_object.bin_number, "NEW-BIN")
        self.assertEqual(stock_object.remarks, "Corrected position")

    def test_store_user_can_correct_stored_item_qr_code(self):
        stock_object = StockObject.objects.create(
            object_type="RAW",
            source_type="OPENING",
            item=self.item,
            qty=Decimal("1.000"),
            weight=Decimal("15.000"),
            qr_code="4444333322221111",
        )
        txn = StockTxn.objects.create(
            txn_type="OPENING_RAW",
            entry_source_type="OPENING",
            created_by=self.user,
            posted=True,
        )
        StockLedgerEntry.objects.create(
            txn=txn,
            item=self.item,
            location=self.store,
            stock_object=stock_object,
            qty=Decimal("1.000"),
            weight=Decimal("15.000"),
        )

        admin_user = User.objects.create_user(
            username="admin-correct-qr",
            password="testpass123",
            role="Admin",
            is_staff=True,
        )
        self.client.login(username="admin-correct-qr", password="testpass123")

        response = self.client.post(
            reverse("ledger:correct_stock_object", args=[stock_object.id]),
            {
                "corrected_qr_code": "7777888899990000",
                "corrected_qty": "1.000",
                "corrected_weight": "15.000",
                "correction_reason": "QR was wrongly scanned during inward entry.",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        stock_object.refresh_from_db()
        self.assertEqual(stock_object.qr_code, "7777888899990000")
        correction_txn = StockTxn.objects.filter(txn_type="STOCK_CORRECTION").latest("id")
        self.assertTrue(correction_txn.posted)
        self.assertEqual(StockLedgerEntry.objects.filter(txn=correction_txn).count(), 0)

    def test_store_user_can_correct_stored_item_quantity_and_weight(self):
        stock_object = StockObject.objects.create(
            object_type="RAW",
            source_type="OPENING",
            item=self.item,
            qty=Decimal("1.000"),
            weight=Decimal("15.000"),
            qr_code="1234123412341234",
        )
        txn = StockTxn.objects.create(
            txn_type="OPENING_RAW",
            entry_source_type="OPENING",
            created_by=self.user,
            posted=True,
        )
        StockLedgerEntry.objects.create(
            txn=txn,
            item=self.item,
            location=self.store,
            stock_object=stock_object,
            qty=Decimal("1.000"),
            weight=Decimal("15.000"),
        )

        admin_user = User.objects.create_user(
            username="admin-correct-weight",
            password="testpass123",
            role="Admin",
            is_staff=True,
        )
        self.client.login(username="admin-correct-weight", password="testpass123")

        response = self.client.post(
            reverse("ledger:correct_stock_object", args=[stock_object.id]),
            {
                "corrected_qr_code": "1234123412341234",
                "corrected_qty": "1.500",
                "corrected_weight": "18.000",
                "correction_reason": "Original inward quantity and weight were entered short.",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        stock_object.refresh_from_db()
        self.assertEqual(stock_object.qty, Decimal("1.500"))
        self.assertEqual(stock_object.weight, Decimal("18.000"))
        correction_txn = StockTxn.objects.filter(txn_type="STOCK_CORRECTION").latest("id")
        ledger_row = StockLedgerEntry.objects.get(txn=correction_txn)
        self.assertEqual(ledger_row.location, self.store)
        self.assertEqual(ledger_row.stock_object, stock_object)
        self.assertEqual(ledger_row.qty, Decimal("0.500"))
        self.assertEqual(ledger_row.weight, Decimal("3.000"))

    def test_store_user_cannot_access_controlled_correction_route(self):
        stock_object = StockObject.objects.create(
            object_type="RAW",
            source_type="OPENING",
            item=self.item,
            qty=Decimal("1.000"),
            weight=Decimal("5.000"),
            qr_code="2222333344445555",
        )
        txn = StockTxn.objects.create(
            txn_type="OPENING_RAW",
            entry_source_type="OPENING",
            created_by=self.user,
            posted=True,
        )
        StockLedgerEntry.objects.create(
            txn=txn,
            item=self.item,
            location=self.store,
            stock_object=stock_object,
            qty=Decimal("1.000"),
            weight=Decimal("5.000"),
        )
        response = self.client.get(reverse("ledger:correct_stock_object", args=[stock_object.id]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Only Admin or Superuser can correct stored item QR, quantity, and weight.")

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

    def test_admin_can_purge_dummy_reserved_store_data(self):
        admin_user = User.objects.create_user(
            username="admin3",
            password="testpass123",
            role="Admin",
            is_staff=True,
        )
        reserved_store = StockLocation.objects.create(name="Dummy Store", location_type="STORE", is_active=False)
        stock_object = StockObject.objects.create(
            object_type="RAW",
            source_type="OPENING",
            item=self.item,
            qty=Decimal("1.000"),
            weight=Decimal("10.000"),
            qr_code="5555666677778888",
        )
        txn = StockTxn.objects.create(
            txn_type="OPENING_RAW",
            entry_source_type="OPENING",
            created_by=self.user,
            posted=True,
        )
        line = txn.lines.create(
            item=self.item,
            stock_object=stock_object,
            qty=Decimal("1.000"),
            weight=Decimal("10.000"),
            to_location=reserved_store,
        )
        StockLedgerEntry.objects.create(
            txn=txn,
            item=self.item,
            location=reserved_store,
            stock_object=stock_object,
            qty=Decimal("1.000"),
            weight=Decimal("10.000"),
        )

        self.client.login(username="admin3", password="testpass123")
        response = self.client.post(
            reverse("ledger:purge_reserved_location_data", args=[reserved_store.id]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(StockLocation.objects.filter(id=reserved_store.id).exists())
        self.assertFalse(StockLedgerEntry.objects.filter(location_id=reserved_store.id).exists())
        self.assertFalse(StockTxn.objects.filter(id=txn.id).exists())
        self.assertFalse(StockObject.objects.filter(id=stock_object.id).exists())
