import os
import django

# Replace 'your_project' with your actual project name
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')
django.setup()

from inverter.models import Inverter, PowerGeneration
from django.utils import timezone
from decimal import Decimal

def test_power_generation_creation():
    try:
        # Get the ornatesolar inverter
        inverter = Inverter.objects.get(name="ornatesolar")
        print(f"Found inverter: {inverter.name} (ID: {inverter.id})")
        
        # Create a test PowerGeneration record
        test_time = timezone.now().replace(minute=0, second=0, microsecond=0)
        
        power_gen = PowerGeneration.objects.create(
            inverter=inverter,
            measurement_time=test_time,
            energy_generated=Decimal('5.123')
        )
        
        print(f"Created PowerGeneration record:")
        print(f"  ID: {power_gen.id}")
        print(f"  Inverter: {power_gen.inverter.name}")
        print(f"  Time: {power_gen.measurement_time}")
        print(f"  Energy: {power_gen.energy_generated}")
        
        # Verify it was saved
        saved_record = PowerGeneration.objects.get(id=power_gen.id)
        print(f"Verified: Record exists with energy = {saved_record.energy_generated}")
        
        # Count total records
        total_count = PowerGeneration.objects.count()
        print(f"Total PowerGeneration records in database: {total_count}")
        
    except Inverter.DoesNotExist:
        print("Inverter 'ornatesolar' not found")
        # List all inverters
        print("Available inverters:")
        for inv in Inverter.objects.all():
            print(f"  - {inv.name} (ID: {inv.id})")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_power_generation_creation()