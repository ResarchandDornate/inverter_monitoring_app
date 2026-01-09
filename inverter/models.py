from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from master.models import BaseModel
from django.db.models import Sum
from datetime import datetime, timedelta
from django.db.models.functions import TruncWeek, TruncYear
from django.utils import timezone
from django.core.validators import MinValueValidator
from timescale.db.models.fields import TimescaleDateTimeField
from timescale.db.models.managers import TimescaleManager
import logging

class Manufacturer(BaseModel):
    """
    Model to store manufacturer details for inverters.
    """
    company_name = models.CharField(max_length=100, unique=True,verbose_name="Company Name")
    company_alias = models.CharField(max_length=100, blank=True, null=True)
    company_address = models.CharField(max_length=255, blank=True, null=True, verbose_name="Address")
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    gst_number = models.CharField(
        max_length=15, 
        blank=True, 
        null=True, 
        unique=True ,
    )

    def __str__(self):
        return self.company_name  

    class Meta:
        ordering = ['company_name']


class Inverter(BaseModel):
    """
    Model to store inverter details, linked to users and manufacturers.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_inverters')
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.SET_NULL, null=True, blank=True, related_name='manufacturer_inverters')
    name = models.CharField(max_length=100, default='Unnamed')
    description = models.TextField(null=True, blank=True)
    inverter_capacity = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0)]
    )
    installation_date = models.DateField(null=True, blank=True)
    serial_number = models.CharField(  # Make required
        max_length=50, 
        unique=True,
        blank=False,  # Was nullable
        null=False
    )
    address= models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()
    efficiency_factor = models.FloatField(default=1.0)

    def get_hourly_energy(self, measurement_time):
        try:
            return self.power_generation.get(measurement_time=measurement_time).energy_generated
        except PowerGeneration.DoesNotExist:
            return 0

    def get_weekly_energy(self, start_date):
        end_date = start_date + timedelta(days=7)
        return self.power_generation.filter(
            measurement_time__gte=start_date,
            measurement_time__lt=end_date
        ).aggregate(total_energy=Sum('energy_generated'))['total_energy'] or 0

    def get_yearly_energy(self, year):
        start_date = datetime(year, 1, 1)
        end_date = datetime(year + 1, 1, 1)
        return self.power_generation.filter(
            measurement_time__gte=start_date,
            measurement_time__lt=end_date
        ).aggregate(total_energy=Sum('energy_generated'))['total_energy'] or 0

    def get_all_weekly_totals(self):
        return self.power_generation.annotate(week=TruncWeek('measurement_time')).values('week').annotate(total_energy=Sum('energy_generated')).order_by('week')

    def get_all_yearly_totals(self):
        return self.power_generation.annotate(year=TruncYear('measurement_time')).values('year').annotate(total_energy=Sum('energy_generated')).order_by('year')

    def __str__(self):
        return f"{self.manufacturer.company_name if self.manufacturer else 'Unknown'} {self.name} in {self.city}"

    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'name']


class Activation(BaseModel):
    """
    Model to store activation events for inverters.
    """
    inverter = models.ForeignKey(Inverter, on_delete=models.CASCADE, related_name='activations', verbose_name="Inverter")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="User")
    activation_time = models.DateTimeField(auto_now_add=True, verbose_name="Activation Time")

    def __str__(self):
        return f"Activation #{self.id} for {self.inverter.serial_number or self.inverter.id}"

    class Meta:
        ordering = ['-activation_time']
        indexes = [
            models.Index(fields=['inverter', 'activation_time']),
        ]

class InverterData(models.Model):
    inverter = models.ForeignKey('Inverter', on_delete=models.CASCADE, related_name='data_points')
    manufacturer = models.ForeignKey('Manufacturer', on_delete=models.SET_NULL, null=True, blank=True, related_name='inverter_data')
    timestamp = TimescaleDateTimeField(interval="1 day")
    voltage = models.DecimalField(max_digits=7, decimal_places=2, validators=[MinValueValidator(0.0)])
    current = models.DecimalField(max_digits=7, decimal_places=2, validators=[MinValueValidator(0.0)])
    power = models.DecimalField(max_digits=10, decimal_places=2)
    temperature = models.FloatField()
    grid_connected = models.BooleanField(default=False)

    objects = TimescaleManager()

    class Meta:
        unique_together = (('inverter', 'timestamp'),)
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['inverter', 'timestamp']),
        ]

    def save(self, *args, **kwargs):
        self.power = self.voltage * self.current
        super().save(*args, **kwargs)

logger = logging.getLogger(__name__)

class PowerGeneration(models.Model):
    inverter = models.ForeignKey('Inverter', on_delete=models.CASCADE, related_name='power_generation')
    measurement_time = TimescaleDateTimeField(interval="1 hour")  # Changed from "1 day" to "1 hour" for better granularity
    energy_generated = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(0.0)],
        help_text="Energy in kWh"
    )
    avg_power = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.0)],
        help_text="Average power in Watts",
        null=True,
        blank=True
    )
    data_points_count = models.IntegerField(
        default=0,
        help_text="Number of data points used for calculation"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = TimescaleManager()
    
    class Meta:
        unique_together = (('inverter', 'measurement_time'),)
        ordering = ['-measurement_time']
        indexes = [
            models.Index(fields=['measurement_time']),
            models.Index(fields=['inverter', 'measurement_time']),
        ]
    
    def save(self, *args, **kwargs):
        # Log before saving
        logger.info(f"Saving PowerGeneration: {self.inverter.name} at {self.measurement_time} - {self.energy_generated} kWh")
        
        # Validate energy value
        if self.energy_generated < 0:
            logger.warning(f"Negative energy value detected: {self.energy_generated}")
            self.energy_generated = 0
        
        super().save(*args, **kwargs)
        
        # Log after successful save
        logger.info(f"PowerGeneration saved successfully: ID={self.id}")
    
    def __str__(self):
        return f"{self.inverter.name} - {self.measurement_time}: {self.energy_generated} kWh"