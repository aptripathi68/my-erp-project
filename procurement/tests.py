from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ledger.models import StockLedgerEntry, StockLocation, StockObject, StockTxn
from masters.models import Grade, Group2, Item
from procurement.models import BOMComponent, BOMHeader, BOMMark, FabricationJob
from procurement.services.planning import bom_material_evaluation, generate_int_erc_jobs


User = get_user_model()


class PlanningMaterialEvaluationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="planner",
            password="testpass123",
            role="Planning",
            is_staff=True,
        )
        self.client.login(username="planner", password="testpass123")
        self.group2 = Group2.objects.create(code="RM", name="Raw Material")
        self.grade = Grade.objects.create(group2=self.group2, code="IS2062", name="E250A")
        self.item = Item.objects.create(
            group2=self.group2,
            grade=self.grade,
            item_description="PL10 IS:2062, E250A",
            section_name="PL10",
            unit_weight=Decimal("10.000"),
        )
        self.bom = BOMHeader.objects.create(
            bom_name="WO-001",
            project_name="Planning Test",
            uploaded_by=self.user,
        )
        self.mark = BOMMark.objects.create(
            bom=self.bom,
            sheet_name="Sheet1",
            erc_mark="A1",
            erc_quantity=Decimal("2.000"),
            drawing_no="D-001",
        )
        BOMComponent.objects.create(
            bom_mark=self.mark,
            part_mark="P1",
            section_name="PL10",
            grade_name="IS:2062, E250A",
            part_quantity_per_assy=Decimal("1.000"),
            engg_weight_kg=Decimal("25.000"),
            item=self.item,
            item_description_raw="PL10",
            excel_row=2,
        )

    def test_generate_int_erc_jobs_is_idempotent(self):
        result = generate_int_erc_jobs(self.bom)
        self.assertEqual(result["created_jobs"], 2)
        self.assertEqual(FabricationJob.objects.filter(bom_mark=self.mark).count(), 2)

        result = generate_int_erc_jobs(self.bom)
        self.assertEqual(result["created_jobs"], 0)
        self.assertEqual(FabricationJob.objects.filter(bom_mark=self.mark).count(), 2)

    def test_material_evaluation_reports_shortage_and_coverage(self):
        store = StockLocation.objects.create(name="Main Store", location_type="STORE")
        stock_object = StockObject.objects.create(
            object_type="RAW",
            source_type="OPENING",
            item=self.item,
            qty=Decimal("2.000"),
            weight=Decimal("40.000"),
            qr_code="12345678901",
        )
        txn = StockTxn.objects.create(txn_type="OPENING_RAW", entry_source_type="OPENING", posted=True)
        StockLedgerEntry.objects.create(
            txn=txn,
            item=self.item,
            location=store,
            stock_object=stock_object,
            qty=Decimal("2.000"),
            weight=Decimal("40.000"),
        )

        evaluation = bom_material_evaluation(self.bom)
        self.assertEqual(evaluation["total_items"], 1)
        self.assertEqual(evaluation["shortage_items"], 1)
        self.assertEqual(evaluation["rows"][0]["required_weight"], Decimal("50.000"))
        self.assertEqual(evaluation["rows"][0]["shortage_weight"], Decimal("10.000"))

    def test_planning_dashboard_loads(self):
        response = self.client.get(reverse("procurement:planning_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Planning &amp; Material Evaluation")
        self.assertContains(response, "WO-001")
