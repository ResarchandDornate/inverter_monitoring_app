from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActivationViewSet,
    InverterDataViewSet,
    InverterViewSet,
    ManufacturerViewSet,
    PowerGenerationViewSet,
    create_power_generation_data,
    mqtt_health,
    power_generation_api,
    publish_view,
    db_health,
)

router = DefaultRouter()
router.register(r'manufacturers', ManufacturerViewSet)
router.register(r'inverters', InverterViewSet, basename='inverter')
router.register(r'activations', ActivationViewSet, basename='activation')
router.register(r'inverter-data', InverterDataViewSet, basename='inverter-data')
router.register(r'power-generation', PowerGenerationViewSet, basename='power-generation')

urlpatterns = [
    path('', include(router.urls)),
    path('publish/', publish_view, name='publish'),
    path('api/power-generation/', power_generation_api, name='power_generation_api'),
    path('api/power-generation/create/', create_power_generation_data, name='create_power_generation'),
    path('health/mqtt/', mqtt_health, name='mqtt_health'),
    path('health/db/', db_health, name='db_health'),
]