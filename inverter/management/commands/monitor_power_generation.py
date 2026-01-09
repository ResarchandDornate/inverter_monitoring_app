from django.core.management.base import BaseCommand
from inverter.models import PowerGeneration, InverterData
from django.utils import timezone
from datetime import timedelta
import time

class Command(BaseCommand):
    help = 'Monitor PowerGeneration data in real-time'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Check interval in seconds (default: 30)'
        )

    def handle(self, *args, **options):
        interval = options['interval']
        self.stdout.write(f"Monitoring PowerGeneration data every {interval} seconds...")
        
        last_count = PowerGeneration.objects.count()
        
        while True:
            try:
                current_count = PowerGeneration.objects.count()
                
                if current_count > last_count:
                    new_records = current_count - last_count
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[{timezone.now()}] New PowerGeneration records: {new_records} "
                            f"(Total: {current_count})"
                        )
                    )
                    
                    # Show latest record
                    latest = PowerGeneration.objects.latest('measurement_time')
                    self.stdout.write(
                        f"Latest: {latest.inverter.name} - {latest.measurement_time} - {latest.energy_generated} kWh"
                    )
                    
                    last_count = current_count
                
                time.sleep(interval)
                
            except KeyboardInterrupt:
                self.stdout.write("\nMonitoring stopped.")
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error: {e}"))
                time.sleep(interval)