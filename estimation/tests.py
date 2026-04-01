from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from masters.models import Grade, Group2, Item

from .models import (
    EstimateExpense,
    EstimateProject,
    EstimateProjectSupplier,
    EstimateSupplier,
)
from .services import (
    ensure_project_cost_heads,
    generate_budget_heads,
    recalculate_cost_heads,
    refresh_budget_totals,
    sync_project_supplier_rates,
)


User = get_user_model()


class EstimationFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="planner", password="test123", role="Planning")
        self.marketing_user = User.objects.create_user(username="marketing", password="test123", role="Marketing")
        self.group2 = Group2.objects.create(code="STEEL", name="Steel")
        self.grade = Grade.objects.create(group2=self.group2, code="E250", name="IS:2062, E250Br")
        self.item = Item.objects.create(
            item_master_id="ITEM-001",
            group2=self.group2,
            grade=self.grade,
            item_description="PL10MM IS:2062, E250BR",
            section_name="PL10MM",
            unit_weight=Decimal("78.50"),
        )

    def test_create_inquiry_screen_creates_project(self):
        self.client.login(username="marketing", password="test123")
        response = self.client.post(
            reverse("estimation:estimate_create"),
            {
                "client_name": "PAHARPUR",
                "project_name": "W STYLE ACC STRUCTURE AND HANDRAIL",
                "quantity_mt": "950",
                "notes": "Urgent submission",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            EstimateProject.objects.filter(
                client_name="PAHARPUR",
                project_name="W STYLE ACC STRUCTURE AND HANDRAIL",
                quantity_mt=Decimal("950"),
            ).exists()
        )

    def test_create_inquiry_without_quantity_is_allowed(self):
        self.client.login(username="marketing", password="test123")
        response = self.client.post(
            reverse("estimation:estimate_create"),
            {
                "client_name": "PAHARPUR",
                "project_name": "NO QTY HEADER",
                "quantity_mt": "",
                "notes": "Header first",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            EstimateProject.objects.filter(
                client_name="PAHARPUR",
                project_name="NO QTY HEADER",
                quantity_mt=Decimal("0"),
            ).exists()
        )

    def test_planning_cannot_create_inquiry(self):
        self.client.login(username="planner", password="test123")
        response = self.client.get(reverse("estimation:estimate_create"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Only Marketing, Management, or Admin can create a new quotation inquiry.")

    def test_project_inquiry_number_and_cost_heads_created(self):
        project = EstimateProject.objects.create(
            client_name="PAHARPUR",
            project_name="W STYLE ACC STRUCTURE AND HANDRAIL",
            quantity_mt=Decimal("284"),
            created_by=self.user,
            updated_by=self.user,
        )
        ensure_project_cost_heads(project)
        self.assertTrue(project.inquiry_no.startswith("EST/"))
        self.assertEqual(project.cost_heads.count(), 29)
        self.assertEqual(project.cost_heads.get(code="SCRAP_BURNING").percentage, Decimal("-0.03888"))
        self.assertEqual(project.cost_heads.get(code="SCRAP_BURNING").rate_per_kg, Decimal("28"))
        self.assertEqual(project.cost_heads.get(code="OFFCUT_RECOVERY").percentage, Decimal("-0.05830"))
        self.assertEqual(project.cost_heads.get(code="OFFCUT_RECOVERY").rate_per_kg, Decimal("35"))
        self.assertEqual(project.cost_heads.get(code="FABRICATION").rate_per_kg, Decimal("11"))

    def test_rate_finalization_updates_raw_material_cost(self):
        project = EstimateProject.objects.create(
            client_name="PAHARPUR",
            project_name="W STYLE ACC STRUCTURE AND HANDRAIL",
            quantity_mt=Decimal("0"),
            created_by=self.user,
            updated_by=self.user,
        )
        ensure_project_cost_heads(project)

        supplier_1 = EstimateSupplier.objects.create(name="ABC Steel")
        supplier_2 = EstimateSupplier.objects.create(name="XYZ Steel")
        EstimateProjectSupplier.objects.create(project=project, supplier=supplier_1, column_order=1)
        EstimateProjectSupplier.objects.create(project=project, supplier=supplier_2, column_order=2)

        line = project.raw_material_lines.create(item=self.item, quantity_mt=Decimal("40"), sort_order=1)
        sync_project_supplier_rates(project)
        rate_1 = line.supplier_rates.get(supplier=supplier_1)
        rate_1.rate_per_mt = Decimal("56000")
        rate_1.save()
        rate_2 = line.supplier_rates.get(supplier=supplier_2)
        rate_2.rate_per_mt = Decimal("58000")
        rate_2.save()
        line.final_rate_per_mt = Decimal("56000")
        line.save()

        recalculate_cost_heads(project)
        line.refresh_from_db()
        project.refresh_from_db()

        self.assertEqual(line.lowest_rate_per_mt, Decimal("56000"))
        self.assertEqual(line.total_amount, Decimal("2240000.00"))
        self.assertEqual(project.raw_material_cost_per_kg, Decimal("56.00"))
        self.assertEqual(project.quantity_mt, Decimal("40.00"))

    def test_budget_generation_and_expense_approval(self):
        management = User.objects.create_user(username="boss", password="test123", role="Management")
        project = EstimateProject.objects.create(
            client_name="PAHARPUR",
            project_name="Budget Test",
            quantity_mt=Decimal("100"),
            created_by=self.user,
            updated_by=self.user,
            work_order_no="WO-001",
        )
        ensure_project_cost_heads(project)
        head = project.cost_heads.get(code="FABRICATION")
        head.rate_per_kg = Decimal("11")
        head.save()
        recalculate_cost_heads(project)
        generate_budget_heads(project)

        budget = project.budget_heads.get(cost_head__code="FABRICATION")
        expense = EstimateExpense.objects.create(
            budget_head=budget,
            amount=Decimal("50000"),
            description="Vendor advance",
            created_by=self.user,
        )
        expense.status = EstimateExpense.Status.APPROVED
        expense.approved_by = management
        expense.save()
        refresh_budget_totals(project)
        budget.refresh_from_db()

        self.assertEqual(budget.budget_code, "WO-001/006")
        self.assertEqual(budget.approved_amount, Decimal("50000.00"))

    def test_raw_material_line_can_be_deleted(self):
        project = EstimateProject.objects.create(
            client_name="PAHARPUR",
            project_name="Delete Line Test",
            quantity_mt=Decimal("0"),
            created_by=self.user,
            updated_by=self.user,
        )
        ensure_project_cost_heads(project)
        line = project.raw_material_lines.create(item=self.item, quantity_mt=Decimal("10"), sort_order=1)
        recalculate_cost_heads(project)

        self.client.login(username="planner", password="test123")
        response = self.client.post(
            reverse("estimation:delete_raw_material_line", args=[project.id, line.id]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(project.raw_material_lines.filter(id=line.id).exists())

    def test_percentage_input_is_saved_as_fraction(self):
        project = EstimateProject.objects.create(
            client_name="PAHARPUR",
            project_name="Percentage Test",
            quantity_mt=Decimal("100"),
            created_by=self.user,
            updated_by=self.user,
        )
        ensure_project_cost_heads(project)
        head = project.cost_heads.get(code="FABRICATION")

        self.client.login(username="planner", password="test123")
        payload = {}
        for h in project.cost_heads.filter(line_type="ENTRY"):
            payload[f"percentage_{h.id}"] = "-3.888" if h.code == "SCRAP_BURNING" else "100.00"
            payload[f"rate_{h.id}"] = str(h.rate_per_kg)
            payload[f"remarks_{h.id}"] = h.remarks
        payload[f"rate_{head.id}"] = "11"
        response = self.client.post(
            reverse("estimation:update_cost_heads", args=[project.id]),
            payload,
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        head.refresh_from_db()
        self.assertEqual(head.percentage, Decimal("1"))
        self.assertEqual(project.cost_heads.get(code="SCRAP_BURNING").percentage, Decimal("-0.03888"))

    def test_planning_cannot_add_supplier_column(self):
        project = EstimateProject.objects.create(
            client_name="PAHARPUR",
            project_name="Supplier Permission",
            quantity_mt=Decimal("0"),
            created_by=self.user,
            updated_by=self.user,
        )
        supplier = EstimateSupplier.objects.create(name="IronMart")

        self.client.login(username="planner", password="test123")
        response = self.client.post(
            reverse("estimation:add_project_supplier", args=[project.id]),
            {"supplier_id": supplier.id},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(project.project_suppliers.filter(supplier=supplier).exists())

    def test_marketing_can_add_supplier_column(self):
        project = EstimateProject.objects.create(
            client_name="PAHARPUR",
            project_name="Supplier Permission OK",
            quantity_mt=Decimal("0"),
            created_by=self.user,
            updated_by=self.user,
        )
        supplier = EstimateSupplier.objects.create(name="IronMart")

        self.client.login(username="marketing", password="test123")
        response = self.client.post(
            reverse("estimation:add_project_supplier", args=[project.id]),
            {"supplier_id": supplier.id},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(project.project_suppliers.filter(supplier=supplier).exists())

    def test_management_can_delete_unused_quotation(self):
        management = User.objects.create_user(username="mgmtdelete", password="test123", role="Management")
        project = EstimateProject.objects.create(
            client_name="PAHARPUR",
            project_name="Delete Me",
            quantity_mt=Decimal("0"),
            created_by=self.user,
            updated_by=self.user,
        )
        self.client.login(username="mgmtdelete", password="test123")
        response = self.client.post(reverse("estimation:delete_estimate", args=[project.id]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EstimateProject.objects.filter(id=project.id).exists())

    def test_management_cannot_delete_quotation_with_budget(self):
        management = User.objects.create_user(username="mgmtkeep", password="test123", role="Management")
        project = EstimateProject.objects.create(
            client_name="PAHARPUR",
            project_name="Keep Me",
            quantity_mt=Decimal("100"),
            created_by=self.user,
            updated_by=self.user,
        )
        ensure_project_cost_heads(project)
        generate_budget_heads(project)
        self.client.login(username="mgmtkeep", password="test123")
        response = self.client.post(reverse("estimation:delete_estimate", args=[project.id]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(EstimateProject.objects.filter(id=project.id).exists())
