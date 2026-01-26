from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ManufacturerViewSet,
    InverterViewSet,
    ActivationViewSet,
    InverterDataViewSet,
    PowerGenerationViewSet,
    MQTTViewSet,
    HealthViewSet,
)

router = DefaultRouter()
router.register("manufacturers", ManufacturerViewSet, basename="manufacturer")
router.register("inverters", InverterViewSet, basename="inverter")
router.register("activations", ActivationViewSet, basename="activation")
router.register("inverter-data", InverterDataViewSet, basename="inverter-data")
router.register("power-generation", PowerGenerationViewSet, basename="power-generation")
router.register("mqtt", MQTTViewSet, basename="mqtt")
router.register("health", HealthViewSet, basename="health")

urlpatterns = [
    path("", include(router.urls)),
]
