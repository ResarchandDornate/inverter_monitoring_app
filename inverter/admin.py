from django.contrib import admin
from .models import Manufacturer, Inverter, InverterData, PowerGeneration, Activation

@admin.register(Inverter)
class InverterAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'manufacturer', 'serial_number', 'user', 'installation_date', 'address']
    list_filter = ['user', 'installation_date', 'manufacturer']
    search_fields = ['name', 'serial_number', 'address']

@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'country', 'email', 'phone']
    search_fields = ['company_name', 'country', 'gst_number']
    list_filter = ['country']

@admin.register(InverterData)
class InverterDataAdmin(admin.ModelAdmin):
    list_display = ['inverter', 'timestamp', 'voltage', 'current', 'power', 'temperature', 'grid_connected']
    list_filter = ['timestamp', 'grid_connected']
    search_fields = ['inverter__name']
    date_hierarchy = 'timestamp'

@admin.register(PowerGeneration)
class PowerGenerationAdmin(admin.ModelAdmin):
    list_display = ['inverter', 'measurement_time', 'energy_generated']
    list_filter = ['measurement_time']
    search_fields = ['inverter__name']
    date_hierarchy = 'measurement_time'

@admin.register(Activation)
class ActivationAdmin(admin.ModelAdmin):
    list_display = ['inverter', 'user', 'activation_time']
    list_filter = ['activation_time', 'user']
    search_fields = ['inverter__name', 'inverter__serial_number']
    date_hierarchy = 'activation_time'
