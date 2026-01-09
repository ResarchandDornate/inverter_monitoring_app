from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ManufacturerViewSet, InverterViewSet, ActivationViewSet,
    InverterDataViewSet, PowerGenerationViewSet,publish_view,power_generation_api,create_power_generation_data
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
]