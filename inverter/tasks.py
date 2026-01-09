from celery import shared_task
from .mqtt_client import generate_demo_data
import logging

logger = logging.getLogger(__name__)

@shared_task
def generate_random_inverter_data():
    """Task to generate random inverter data for testing"""
    logger.info("Starting task to generate random inverter data")
    generate_demo_data()
    logger.info("Completed task to generate random inverter data")
