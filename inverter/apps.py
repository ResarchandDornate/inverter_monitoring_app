from django.apps import AppConfig

class InverterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inverter'

    def ready(self):
        # Only connect Django signals here
        import inverter.signals