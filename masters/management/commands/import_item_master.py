from django.core.management.base import BaseCommand
from masters.utils.excel_import import import_item_master_xlsx


class Command(BaseCommand):
    help = "Import item_master.xlsx into Group2, Grade, Item tables"

    def add_arguments(self, parser):
        parser.add_argument("path", type=str, help="Path to xlsx file inside the container")
        parser.add_argument("--batch", type=str, default="initial_load", help="Batch id tag")

    def handle(self, *args, **options):
        result = import_item_master_xlsx(options["path"], batch_id=options["batch"])
        self.stdout.write(self.style.SUCCESS(f"Import complete: {result}"))