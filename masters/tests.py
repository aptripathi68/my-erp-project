from decimal import Decimal

from django.test import TestCase

from .models import Grade, Group2, Item


class ItemMasterApiTests(TestCase):
    def setUp(self):
        self.group2 = Group2.objects.create(code="RM", name="Raw Material")
        self.grade = Grade.objects.create(group2=self.group2, code="E250", name="IS:2062, E250BR")
        self.item = Item.objects.create(
            group2=self.group2,
            grade=self.grade,
            item_description="ISMC75 IS:2062, E250BR",
            section_name="ISMC75",
            unit_weight=Decimal("7.140"),
        )

    def test_sections_api_filters_by_group2(self):
        response = self.client.get(f"/api/sections/?group2={self.group2.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"id": "ISMC75", "section_name": "ISMC75"}])

    def test_sections_api_supports_partial_search(self):
        response = self.client.get(f"/api/sections/?group2={self.group2.id}&q=MC7")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"id": "ISMC75", "section_name": "ISMC75"}])

    def test_grades_api_can_filter_by_group2_and_section(self):
        response = self.client.get(f"/api/grades/?group2={self.group2.id}&section=ISMC75")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], self.grade.id)

    def test_items_api_can_filter_by_group2_section_and_grade(self):
        response = self.client.get(
            f"/api/items/?group2={self.group2.id}&section=ISMC75&grade={self.grade.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], self.item.id)
