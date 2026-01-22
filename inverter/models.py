from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from master.models import BaseModel
from django.db.models import Sum
from datetime import datetime, timedelta
from django.db.models.functions import TruncWeek, TruncYear
from django.utils import timezone
from django.core.validators import MinValueValidator
import logging

class Manufacturer(BaseModel):
    """
    Model to store manufacturer details for inverters.
    
    Attributes:
        company_name: Official company name (unique, required)
        company_alias: Alternative name or abbreviation
        company_address: Physical address
        phone: Contact phone number
        email: Contact email address
        country: Country of origin
        gst_number: GST registration number (15 characters, unique)
        website: Company website URL
    """
    company_name = models.CharField(max_length=100, unique=True, verbose_name="Company Name")
    company_alias = models.CharField(max_length=100, blank=True, null=True, verbose_name="Company Alias")
    company_address = models.CharField(max_length=255, blank=True, null=True, verbose_name="Address")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Phone")
    email = models.EmailField(blank=True, verbose_name="Email")
    country = models.CharField(max_length=100, blank=True, null=True, verbose_name="Country")
    website = models.URLField(blank=True, null=True, verbose_name="Website")
    gst_number = models.CharField(
        max_length=15, 
        blank=True, 
        null=True, 
        unique=True,
        verbose_name="GST Number",
        help_text="15-character GST registration number"
    )

    def __str__(self):
        return self.company_name  

    class Meta:
        ordering = ['company_name']
        verbose_name = "Manufacturer"
        verbose_name_plural = "Manufacturers"


class Inverter(BaseModel):
    """
    Model to store inverter details, linked to users and manufacturers.
    
    Attributes:
        user: Owner of the inverter (can be None for system-generated inverters)
        manufacturer: Manufacturer of the inverter
        name: Human-readable name for the inverter
        model: Manufacturer model number/identifier
        description: Additional details about the inverter
        inverter_capacity: Maximum capacity in Watts (DecimalField for precision)
        installation_date: Date when inverter was installed
        serial_number: Unique serial number (required, unique)
        address: Installation address
        city: City of installation
        state: State/Province of installation
        country: Country of installation
        latitude: GPS latitude coordinate
        longitude: GPS longitude coordinate
        efficiency_factor: Efficiency factor (0.0 to 1.0, where 1.0 = 100%)
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='user_inverters',
        verbose_name="User",
        help_text="Owner of the inverter. Can be None for system-generated inverters."
    )
    manufacturer = models.ForeignKey(
        Manufacturer, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='manufacturer_inverters',
        verbose_name="Manufacturer"
    )
    name = models.CharField(
        max_length=100, 
        default='Unnamed',
        verbose_name="Name",
        help_text="Human-readable name for the inverter"
    )
    model = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Model",
        help_text="Manufacturer model number or identifier"
    )
    description = models.TextField(null=True, blank=True, verbose_name="Description")
    inverter_capacity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
        validators=[MinValueValidator(0.0)],
        verbose_name="Capacity (W)",
        help_text="Maximum capacity in Watts"
    )
    installation_date = models.DateField(null=True, blank=True, verbose_name="Installation Date")
    serial_number = models.CharField(
        max_length=50, 
        unique=True,
        blank=False,
        null=False,
        verbose_name="Serial Number",
        help_text="Unique serial number of the inverter"
    )
    address = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Address",
        help_text="Street address (optional for auto-created inverters)"
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="City",
        help_text="City name (optional for auto-created inverters)"
    )
    state = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="State/Province",
        help_text="State or province (optional for auto-created inverters)"
    )
    country = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Country",
        help_text="Country name (optional for auto-created inverters)"
    )
    latitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Latitude",
        help_text="GPS latitude coordinate (-90 to 90)"
    )
    longitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Longitude",
        help_text="GPS longitude coordinate (-180 to 180)"
    )
    efficiency_factor = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=1.0,
        validators=[MinValueValidator(0.0)],
        verbose_name="Efficiency Factor",
        help_text="Efficiency factor (0.0 to 1.0, where 1.0 = 100% efficiency)"
    )

    def get_hourly_energy(self, measurement_time):
        """Get energy generated for a specific hour.
        
        Args:
            measurement_time: Datetime for the hour to query
            
        Returns:
            Decimal: Energy generated in kWh, or 0 if no data exists
        """
        from .models import PowerGeneration  # Avoid forward reference
        try:
            return self.power_generation.get(measurement_time=measurement_time).energy_generated
        except PowerGeneration.DoesNotExist:
            return 0

    def get_weekly_energy(self, start_date):
        """Calculate total energy generated in a week starting from start_date.
        
        Args:
            start_date: Start date of the week
            
        Returns:
            Decimal: Total energy generated in kWh
        """
        end_date = start_date + timedelta(days=7)
        return self.power_generation.filter(
            measurement_time__gte=start_date,
            measurement_time__lt=end_date
        ).aggregate(total_energy=Sum('energy_generated'))['total_energy'] or 0

    def get_yearly_energy(self, year):
        """Calculate total energy generated in a specific year.
        
        Args:
            year: Year to calculate (integer)
            
        Returns:
            Decimal: Total energy generated in kWh
        """
        start_date = datetime(year, 1, 1)
        end_date = datetime(year + 1, 1, 1)
        return self.power_generation.filter(
            measurement_time__gte=start_date,
            measurement_time__lt=end_date
        ).aggregate(total_energy=Sum('energy_generated'))['total_energy'] or 0

    def get_all_weekly_totals(self):
        """Get all weekly energy totals grouped by week.
        
        Returns:
            QuerySet: Annotated queryset with week and total_energy
        """
        return self.power_generation.annotate(
            week=TruncWeek('measurement_time')
        ).values('week').annotate(
            total_energy=Sum('energy_generated')
        ).order_by('week')

    def get_all_yearly_totals(self):
        """Get all yearly energy totals grouped by year.
        
        Returns:
            QuerySet: Annotated queryset with year and total_energy
        """
        return self.power_generation.annotate(
            year=TruncYear('measurement_time')
        ).values('year').annotate(
            total_energy=Sum('energy_generated')
        ).order_by('year')

    def __str__(self):
        manufacturer_name = self.manufacturer.company_name if self.manufacturer else 'Unknown'
        location = self.city or 'Unknown Location'
        return f"{manufacturer_name} {self.name} in {location}"

    class Meta:
        ordering = ['-created_at']
        # Removed unique_together to allow multiple inverters with same name per user
        # Use serial_number for uniqueness instead
        verbose_name = "Inverter"
        verbose_name_plural = "Inverters"
        indexes = [
            models.Index(fields=['serial_number']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['manufacturer']),
        ]


class Activation(BaseModel):
    """
    Model to store activation events for inverters.
    
    Tracks when inverters are activated by users. The user field is kept
    separate from inverter.user for audit purposes, allowing tracking of
    who activated the inverter even if ownership changes.
    
    Attributes:
        inverter: Inverter that was activated
        user: User who performed the activation
        activation_time: When the activation occurred
    """
    inverter = models.ForeignKey(
        Inverter, 
        on_delete=models.CASCADE, 
        related_name='activations', 
        verbose_name="Inverter"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        verbose_name="User",
        help_text="User who activated this inverter (for audit trail)"
    )
    activation_time = models.DateTimeField(
        auto_now_add=True, 
        verbose_name="Activation Time"
    )

    def __str__(self):
        serial = self.inverter.serial_number if self.inverter else "Unknown"
        return f"Activation #{self.id} for {serial}"

    class Meta:
        ordering = ['-activation_time']
        verbose_name = "Activation"
        verbose_name_plural = "Activations"
        indexes = [
            models.Index(fields=['inverter', 'activation_time']),
            models.Index(fields=['user', 'activation_time']),
        ]

class InverterData(models.Model):
    """
    Time-series data points for inverter readings.
    
    Optimized for 15-minute interval data storage in PostgreSQL.
    Each record represents a single reading at a specific timestamp.
    
    Attributes:
        inverter: Inverter this data point belongs to
        timestamp: When this reading was taken (indexed for efficient queries)
        voltage: Voltage reading in Volts
        current: Current reading in Amperes
        power: Calculated power (voltage * current) in Watts
        temperature: Temperature reading in Celsius
        grid_connected: Whether inverter is connected to grid
    """
    inverter = models.ForeignKey(
        'Inverter', 
        on_delete=models.CASCADE, 
        related_name='data_points',
        verbose_name="Inverter",
        db_index=True
    )
    timestamp = models.DateTimeField(
        verbose_name="Timestamp",
        help_text="When this reading was taken",
        db_index=True
    )
    voltage = models.DecimalField(
        max_digits=7, 
        decimal_places=2, 
        validators=[MinValueValidator(0.0)],
        verbose_name="Voltage (V)",
        help_text="Voltage reading in Volts"
    )
    current = models.DecimalField(
        max_digits=7, 
        decimal_places=2, 
        validators=[MinValueValidator(0.0)],
        verbose_name="Current (A)",
        help_text="Current reading in Amperes"
    )
    power = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Power (W)",
        help_text="Calculated power (voltage * current) in Watts"
    )
    temperature = models.FloatField(
        verbose_name="Temperature (°C)",
        help_text="Temperature reading in Celsius"
    )
    grid_connected = models.BooleanField(
        default=False,
        verbose_name="Grid Connected",
        help_text="Whether inverter is connected to the electrical grid"
    )

    class Meta:
        unique_together = (('inverter', 'timestamp'),)
        ordering = ['-timestamp']
        verbose_name = "Inverter Data Point"
        verbose_name_plural = "Inverter Data Points"
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['inverter', 'timestamp']),
            models.Index(fields=['inverter', '-timestamp']),  # For latest queries
        ]

    def save(self, *args, **kwargs):
        """Override save to auto-calculate power."""
        # Auto-calculate power from voltage and current
        self.power = self.voltage * self.current
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.inverter.serial_number} - {self.timestamp}: {self.power}W"

logger = logging.getLogger(__name__)

class PowerGeneration(models.Model):
    """
    Aggregated power generation data by hour.
    
    Each record represents aggregated energy generation for a specific inverter 
    during a one-hour period. Optimized for PostgreSQL with proper indexing.
    
    Attributes:
        inverter: Inverter this generation data belongs to
        measurement_time: Start of the hour period (indexed for efficient queries)
        energy_generated: Total energy generated in kWh during this hour
        avg_power: Average power output in Watts during this hour
        data_points_count: Number of InverterData points used for calculation
        created_at: When this record was created
        updated_at: When this record was last updated
    """
    inverter = models.ForeignKey(
        'Inverter', 
        on_delete=models.CASCADE, 
        related_name='power_generation',
        verbose_name="Inverter",
        db_index=True
    )
    measurement_time = models.DateTimeField(
        verbose_name="Measurement Time",
        help_text="Start of the hour period for this aggregation",
        db_index=True
    )
    energy_generated = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(0.0)],
        help_text="Total energy generated in kWh during this hour",
        verbose_name="Energy Generated (kWh)"
    )
    avg_power = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.0)],
        help_text="Average power output in Watts during this hour",
        null=True,
        blank=True,
        verbose_name="Average Power (W)"
    )
    data_points_count = models.IntegerField(
        default=0,
        help_text="Number of InverterData points used for this calculation",
        verbose_name="Data Points Count"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At"
    )
    
    class Meta:
        unique_together = (('inverter', 'measurement_time'),)
        ordering = ['-measurement_time']
        verbose_name = "Power Generation"
        verbose_name_plural = "Power Generation Records"
        indexes = [
            models.Index(fields=['measurement_time']),
            models.Index(fields=['inverter', 'measurement_time']),
            models.Index(fields=['inverter', '-measurement_time']),  # For latest queries
        ]
    
    def save(self, *args, **kwargs):
        """Override save to validate energy value and log operations."""
        # Validate energy value (should never be negative)
        if self.energy_generated < 0:
            logger.warning(
                "Negative energy value detected: %s. Setting to 0.",
                self.energy_generated,
                extra={"inverter_id": self.inverter.serial_number if self.inverter else None}
            )
            self.energy_generated = 0
        
        # Auto-calculate avg_power if not provided and we have energy
        # avg_power = energy_generated (kWh) * 1000 / 1 hour = energy_generated * 1000 W
        if self.avg_power is None and self.energy_generated > 0:
            # Convert kWh to average Watts: 1 kWh = 1000 W over 1 hour
            self.avg_power = self.energy_generated * 1000
        
        logger.debug(
            "Saving PowerGeneration: %s at %s - %s kWh",
            self.inverter.name if self.inverter else "Unknown",
            self.measurement_time,
            self.energy_generated,
            extra={
                "inverter_id": self.inverter.serial_number if self.inverter else None,
                "component": "inverter.models"
            }
        )
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        inverter_name = self.inverter.name if self.inverter else "Unknown"
        return f"{inverter_name} - {self.measurement_time}: {self.energy_generated} kWh"