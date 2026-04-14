from django.core.management.base import BaseCommand

from facilities.models import Facility


SEED_FACILITIES = [
    {"name": "Kanyama Level 1 Hospital", "district": "Lusaka", "province": "Lusaka"},
    {"name": "Chipata General Hospital", "district": "Chipata", "province": "Eastern"},
    {"name": "Arthur Davison Children's Hospital", "district": "Ndola", "province": "Copperbelt"},
    {"name": "Mongu General Hospital", "district": "Mongu", "province": "Western"},
    {"name": "Kasama General Hospital", "district": "Kasama", "province": "Northern"},
]


class Command(BaseCommand):
    help = "Seed sample facilities for local development and demos."

    def handle(self, *args, **options):
        created_count = 0
        for facility_data in SEED_FACILITIES:
            _, created = Facility.objects.get_or_create(
                name=facility_data["name"],
                defaults=facility_data,
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Seed complete. Added {created_count} facilities."))
