from django.core.management.base import BaseCommand
from inverter.mqtt_client import start_mqtt_client, stop_mqtt_client
import signal
import time
import sys


class Command(BaseCommand):
    help = 'Start MQTT client for inverter data ingestion'

    def handle(self, *args, **options):
        self.running = True  # ✅ instance-level flag

        self.stdout.write(self.style.SUCCESS('Starting MQTT client worker...'))

        client = start_mqtt_client()
        if not client:
            self.stderr.write(self.style.ERROR('❌ Failed to start MQTT client'))
            sys.exit(1)

        self.stdout.write(self.style.SUCCESS('✅ MQTT client started successfully'))

        def shutdown(signum, frame):
            self.stdout.write(self.style.WARNING('Stopping MQTT client...'))
            self.running = False
            stop_mqtt_client()
            self.stdout.write(self.style.SUCCESS('MQTT client stopped'))
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

        # Keep process alive
        while self.running:
            time.sleep(1)
