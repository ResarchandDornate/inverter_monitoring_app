from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from inverter.models import InverterData, PowerGeneration, Inverter
from django.db import connection

class Command(BaseCommand):
    help = 'Verify PowerGeneration data storage'

    def handle(self, *args, **options):
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM inverter_powergeneration")
            count = cursor.fetchone()[0]
            self.stdout.write(f"Direct SQL count of PowerGeneration records: {count}")
        
        # Check through Django ORM
        orm_count = PowerGeneration.objects.count()
        self.stdout.write(f"Django ORM count of PowerGeneration records: {orm_count}")
        
        # Check recent InverterData
        recent_time = timezone.now() - timedelta(hours=2)
        recent_inverter_data = InverterData.objects.filter(timestamp__gte=recent_time).count()
        self.stdout.write(f"Recent InverterData records (last 2 hours): {recent_inverter_data}")
        
        # Check for specific inverter
        try:
            inverter = Inverter.objects.get(name="ornatesolar")
            inverter_power_gen = PowerGeneration.objects.filter(inverter=inverter).count()
            self.stdout.write(f"PowerGeneration records for 'ornatesolar': {inverter_power_gen}")
            
            # Show recent records
            recent_records = PowerGeneration.objects.filter(
                inverter=inverter,
                measurement_time__gte=recent_time
            ).order_by('-measurement_time')
            
            self.stdout.write(f"Recent PowerGeneration records for 'ornatesolar':")
            for record in recent_records:
                self.stdout.write(f"  ID: {record.id}, Time: {record.measurement_time}, Energy: {record.energy_generated}")
                
        except Inverter.DoesNotExist:
            self.stdout.write("Inverter 'ornatesolar' not found")