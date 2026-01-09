from django.apps import AppConfig
import logging
import threading
import time

logger = logging.getLogger(__name__)

class InverterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inverter'
    
    def ready(self):
        """
        This method is called when Django starts up.
        We use it to initialize the MQTT client.
        """
        import inverter.signals
        # Only start MQTT in the main process (not in reloader process)
        import os
        if os.environ.get('RUN_MAIN') != 'true':
            return
            
        # Start MQTT client in a separate thread to avoid blocking Django startup
        mqtt_thread = threading.Thread(target=self.start_mqtt_with_retry, daemon=True)
        mqtt_thread.start()
        logger.info("MQTT initialization thread started")
    
    def start_mqtt_with_retry(self):
        """
        Start MQTT client with retry logic
        """
        max_retries = 5
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                # Wait a bit for Django to fully initialize
                time.sleep(2)
                
                # Import and start MQTT client
                from . import mqtt_client
                
                # Check if MQTT client is already running
                if mqtt_client.mqtt_client and mqtt_client.mqtt_client.is_connected():
                    logger.info("MQTT client is already connected")
                    return
                
                # Start the MQTT client
                client = mqtt_client.start_mqtt_client()
                
                if client:
                    logger.info("SUCCESS: MQTT client started successfully")
                    return
                else:
                    raise Exception("Failed to create MQTT client")
                    
            except Exception as e:
                logger.error(f"ERROR: Attempt {attempt + 1}/{max_retries} - Failed to start MQTT client: {e}")
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error("ERROR: All MQTT connection attempts failed. MQTT functionality will not be available.")
                    logger.error("Please check:")
                    logger.error("1. MQTT broker (Mosquitto) is running")
                    logger.error("2. MQTT broker is accessible on the configured host/port")
                    logger.error("3. Network connectivity")
                    
    def mqtt_health_check(self):
        """
        Check if MQTT client is healthy and reconnect if needed
        """
        try:
            from . import mqtt_client
            
            if not mqtt_client.mqtt_client or not mqtt_client.mqtt_client.is_connected():
                logger.warning("MQTT client is not connected. Attempting to reconnect...")
                mqtt_client.start_mqtt_client()
                
        except Exception as e:
            logger.error(f"MQTT health check failed: {e}")



