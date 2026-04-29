from rest_framework import serializers
from django.utils import timezone
from datetime import datetime
from .models import Manufacturer, Inverter, Activation, InverterData, PowerGeneration

class ManufacturerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Manufacturer
        fields = ['id', 'company_name', 'company_alias', 'company_address', 'phone', 'email', 'country', 'website', 'gst_number', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_gst_number(self, value):
        if value and len(value) != 15:
            raise serializers.ValidationError("GST number must be 15 characters long.")
        return value

class InverterSerializer(serializers.ModelSerializer):
    manufacturer = ManufacturerSerializer(read_only=True)
    manufacturer_id = serializers.PrimaryKeyRelatedField(
        queryset=Manufacturer.objects.all(), source='manufacturer', write_only=True, required=False
    )
    user = serializers.PrimaryKeyRelatedField(read_only=True, default=serializers.CurrentUserDefault())

    class Meta:
        model = Inverter
        fields = [
            'id', 'user', 'manufacturer', 'manufacturer_id', 'name', 'model', 'description', 
            'inverter_capacity', 'installation_date', 'serial_number', 'address', 'city', 
            'state', 'country', 'latitude', 'longitude', 'efficiency_factor', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def validate_serial_number(self, value):
        if Inverter.objects.filter(serial_number=value).exists():
            raise serializers.ValidationError("An inverter with this serial number already exists.")
        return value

    def validate_inverter_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Inverter capacity must be greater than 0.")
        return value

class ActivationSerializer(serializers.ModelSerializer):
    inverter = serializers.PrimaryKeyRelatedField(queryset=Inverter.objects.all())
    user = serializers.PrimaryKeyRelatedField(read_only=True, default=serializers.CurrentUserDefault())

    class Meta:
        model = Activation
        fields = ['id', 'inverter', 'user', 'activation_time', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'activation_time', 'created_at', 'updated_at']

    def validate_inverter(self, value):
        if value.user != self.context['request'].user:
            raise serializers.ValidationError("You do not have permission to access this inverter.")
        return value

class InverterDataSerializer(serializers.ModelSerializer):
    inverter = serializers.PrimaryKeyRelatedField(queryset=Inverter.objects.all())
    manufacturer = ManufacturerSerializer(read_only=True)
    manufacturer_id = serializers.PrimaryKeyRelatedField(
        queryset=Manufacturer.objects.all(), source='manufacturer', write_only=True, required=False
    )

    class Meta:
        model = InverterData
        fields = [
            'id', 'inverter', 'manufacturer', 'manufacturer_id', 'timestamp', 'voltage',
            'current', 'power', 'vpv', 'ipv', 'temperature', 'grid_connected'
        ]
        read_only_fields = ['id', 'timestamp', 'power']

    def validate(self, data):
        inverter = data.get('inverter')
        manufacturer = data.get('manufacturer')
        if inverter and manufacturer and inverter.manufacturer != manufacturer:
            raise serializers.ValidationError("Manufacturer does not match inverter's manufacturer.")
        if inverter and inverter.user != self.context['request'].user:
            raise serializers.ValidationError("You do not have permission to access this inverter.")
        return data

class PowerGenerationSerializer(serializers.ModelSerializer):
    inverter = serializers.PrimaryKeyRelatedField(queryset=Inverter.objects.all())

    class Meta:
        model = PowerGeneration
        fields = ['id', 'inverter', 'measurement_time', 'energy_generated', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_energy_generated(self, value):
        if value < 0:
            raise serializers.ValidationError("Energy generated cannot be negative.")
        return value

    def validate_inverter(self, value):
        if value.user != self.context['request'].user:
            raise serializers.ValidationError("You do not have permission to access this inverter.")
        return value