from django.core.management.base import BaseCommand
from inverter.mqtt_client import start_mqtt_client, stop_mqtt_client
import signal
import sys
import threading
import time

class Command(BaseCommand):
    help = 'Start MQTT client for inverter data'

    running = True  # Class-level flag

    def add_arguments(self, parser):
        parser.add_argument(
            '--daemon',
            action='store_true',
            help='Run as daemon',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting MQTT client...'))

        # Start MQTT client
        client = start_mqtt_client()
        if not client:
            self.stdout.write(self.style.ERROR('Failed to start MQTT client.'))
            return

        self.stdout.write(self.style.SUCCESS('MQTT client started successfully'))

        # Signal handler
        def signal_handler(sig, frame):
            self.stdout.write(self.style.WARNING('Stopping MQTT client...'))
            stop_mqtt_client()
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Keep the process alive
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            signal_handler(None, None)
