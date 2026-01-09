from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.db.models import Sum, Avg, Count
from decimal import Decimal
import logging
from .models import InverterData, PowerGeneration

logger = logging.getLogger(__name__)

@receiver(post_save, sender=InverterData)
def update_power_generation(sender, instance, created, **kwargs):
    """
    Update PowerGeneration records when new InverterData is saved
    """
    if not created:
        return
    
    try:
        # Get the hour boundary for aggregation
        hour_start = instance.timestamp.replace(minute=0, second=0, microsecond=0)
        
        # Calculate energy for this hour based on all data points in the hour
        hour_data = InverterData.objects.filter(
            inverter=instance.inverter,
            timestamp__gte=hour_start,
            timestamp__lt=hour_start + timezone.timedelta(hours=1)
        )
        
        # Calculate aggregated values
        aggregated = hour_data.aggregate(
            total_power=Sum('power'),
            avg_power=Avg('power'),
            count=Count('id')
        )
        
        total_power = aggregated['total_power'] or 0
        avg_power = aggregated['avg_power'] or 0
        data_count = aggregated['count'] or 0
        
        # Convert power to energy (assuming data points are roughly evenly distributed)
        # Energy (kWh) = Average Power (W) * Time (h) / 1000
        energy_kwh = Decimal(str(avg_power)) * Decimal('1.0') / Decimal('1000.0')
        
        # Create or update PowerGeneration record
        power_gen, created = PowerGeneration.objects.get_or_create(
            inverter=instance.inverter,
            measurement_time=hour_start,
            defaults={
                'energy_generated': energy_kwh,
                'avg_power': Decimal(str(avg_power)),
                'data_points_count': data_count
            }
        )
        
        if not created:
            # Update existing record
            power_gen.energy_generated = energy_kwh
            power_gen.avg_power = Decimal(str(avg_power))
            power_gen.data_points_count = data_count
            power_gen.save()
            
            logger.info(f"Updated PowerGeneration: {instance.inverter.name} at {hour_start.strftime('%Y-%m-%d %H:%M')} - {energy_kwh} kWh (from {data_count} data points, avg power: {avg_power:.2f}W)")
        else:
            logger.info(f"Created PowerGeneration: {instance.inverter.name} at {hour_start.strftime('%Y-%m-%d %H:%M')} - {energy_kwh} kWh (from {data_count} data points, avg power: {avg_power:.2f}W)")
        
        # Verify the save was successful
        if power_gen.id:
            logger.info(f"VERIFIED: PowerGeneration record saved with ID={power_gen.id}, Energy={power_gen.energy_generated}")
        else:
            logger.error("ERROR: PowerGeneration record was not saved properly")
            
    except Exception as e:
        logger.error(f"ERROR in update_power_generation signal: {e}")
        logger.exception("Full traceback:")
