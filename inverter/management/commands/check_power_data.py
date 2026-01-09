from django.core.management.base import BaseCommand
from inverter.models import PowerGeneration, Inverter
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Check PowerGeneration data storage'

    def handle(self, *args, **options):
        # Get recent PowerGeneration records
        recent_records = PowerGeneration.objects.filter(
            measurement_time__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-measurement_time')[:10]
        
        self.stdout.write(f"Found {recent_records.count()} recent PowerGeneration records:")
        
        for record in recent_records:
            self.stdout.write(
                f"ID: {record.id}, "
                f"Inverter: {record.inverter.name}, "
                f"Time: {record.measurement_time}, "
                f"Energy: {record.energy_generated} kWh"
            )
        
        # Check total records
        total_records = PowerGeneration.objects.count()
        self.stdout.write(f"\nTotal PowerGeneration records: {total_records}")