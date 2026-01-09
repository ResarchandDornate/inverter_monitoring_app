from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from .models import Inverter, InverterData, PowerGeneration, Manufacturer

# Get the custom User model
User = get_user_model()

class PowerGenerationSignalTest(TestCase):
    def setUp(self):
        # Use your custom User model
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',  # Add email if required by your custom User model
            password='testpass123'
        )
        
        self.manufacturer = Manufacturer.objects.create(
            company_name='Test Manufacturer'
        )
        
        self.inverter = Inverter.objects.create(
            user=self.user,
            manufacturer=self.manufacturer,
            name='Test Inverter',
            serial_number='TEST123',
            address='Test Address',
            city='Test City',
            state='Test State',
            country='Test Country',
            latitude=0.0,
            longitude=0.0,
            efficiency_factor=0.95
        )

    def test_power_generation_calculation(self):
        """Test that PowerGeneration records are created when InverterData is saved"""
        # Create some inverter data
        timestamp = timezone.now().replace(minute=30, second=0, microsecond=0)
        
        # Create InverterData - this should trigger the signal
        inverter_data = InverterData.objects.create(
            inverter=self.inverter,
            manufacturer=self.manufacturer,
            timestamp=timestamp,
            voltage=Decimal('240.00'),
            current=Decimal('10.00'),
            temperature=25.0,
            grid_connected=True
        )
        
        # Verify that power was calculated correctly (voltage * current)
        expected_power = Decimal('240.00') * Decimal('10.00')  # 2400W
        self.assertEqual(inverter_data.power, expected_power)
        
        # Check if PowerGeneration record was created by the signal
        hour_start = timestamp.replace(minute=0, second=0, microsecond=0)
        power_gen = PowerGeneration.objects.filter(
            inverter=self.inverter,
            measurement_time=hour_start
        ).first()
        
        # Assertions
        self.assertIsNotNone(power_gen, "PowerGeneration record should be created")
        self.assertGreater(power_gen.energy_generated, 0, "Energy generated should be greater than 0")
        
        # Calculate expected energy: Power(2400W) / 1000 * efficiency(0.95) = 2.28 kWh
        expected_energy = (expected_power / Decimal('1000')) * Decimal('0.95')
        self.assertEqual(power_gen.energy_generated, expected_energy)
        
        print(f"✓ PowerGeneration created: {power_gen.energy_generated} kWh at {hour_start}")

    def test_multiple_data_points_same_hour(self):
        """Test that multiple data points in the same hour update the PowerGeneration record"""
        base_timestamp = timezone.now().replace(minute=0, second=0, microsecond=0)
        
        # Create multiple data points in the same hour
        timestamps = [
            base_timestamp + timezone.timedelta(minutes=15),
            base_timestamp + timezone.timedelta(minutes=30),
            base_timestamp + timezone.timedelta(minutes=45),
        ]
        
        powers = []
        for i, timestamp in enumerate(timestamps):
            voltage = Decimal('240.00')
            current = Decimal(f'{10 + i}.00')  # 10A, 11A, 12A
            
            InverterData.objects.create(
                inverter=self.inverter,
                manufacturer=self.manufacturer,
                timestamp=timestamp,
                voltage=voltage,
                current=current,
                temperature=25.0,
                grid_connected=True
            )
            powers.append(voltage * current)
        
        # Check PowerGeneration record
        power_gen = PowerGeneration.objects.get(
            inverter=self.inverter,
            measurement_time=base_timestamp
        )
        
        # Calculate expected average power and energy
        avg_power = sum(powers) / len(powers)  # (2400 + 2640 + 2880) / 3 = 2640W
        expected_energy = (avg_power / Decimal('1000')) * Decimal('0.95')  # 2.508 kWh
        
        self.assertEqual(power_gen.energy_generated, expected_energy)
        print(f"✓ Average energy from multiple data points: {power_gen.energy_generated} kWh")

    def test_grid_disconnected_data_ignored(self):
        """Test that data when grid_connected=False is ignored"""
        timestamp = timezone.now().replace(minute=30, second=0, microsecond=0)
        
        # Create data with grid disconnected
        InverterData.objects.create(
            inverter=self.inverter,
            manufacturer=self.manufacturer,
            timestamp=timestamp,
            voltage=Decimal('240.00'),
            current=Decimal('10.00'),
            temperature=25.0,
            grid_connected=False  # Grid disconnected
        )
        
        # Check if PowerGeneration record exists
        hour_start = timestamp.replace(minute=0, second=0, microsecond=0)
        power_gen_count = PowerGeneration.objects.filter(
            inverter=self.inverter,
            measurement_time=hour_start
        ).count()
        
        # Should not create PowerGeneration record when grid is disconnected
        self.assertEqual(power_gen_count, 0, "No PowerGeneration should be created when grid is disconnected")
        print("✓ Grid disconnected data correctly ignored")
