"""REST API views for inverter manufacturers, devices and power data."""

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import connection
from django.db.models import Avg, Count, Max, Min, Sum
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models.functions import TruncHour
from django.db.models.functions import TruncDay
from .models import Activation, Inverter, InverterData, Manufacturer, PowerGeneration
from .serializers import (
    ActivationSerializer,
    InverterDataSerializer,
    InverterSerializer,
    ManufacturerSerializer,
    PowerGenerationSerializer,
)
from .mqtt_client import get_last_message_timestamp, mqtt_client
from django.utils.dateparse import parse_datetime

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def publish_view(request):
    try:
        data = request.data
        topic = data.get('topic')
        message = data.get('message')
        if not topic or not message:
            return Response({'status': 'error', 'message': 'Topic and message are required'}, status=status.HTTP_400_BAD_REQUEST)
        if mqtt_client:
            mqtt_client.publish(topic, message)
            return Response({'status': 'success', 'message': 'Message published'}, status=status.HTTP_200_OK)
        else:
            return Response({'status': 'error', 'message': 'MQTT client not connected'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except ValueError:
        return Response({'status': 'error', 'message': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)
    
class ManufacturerViewSet(viewsets.ModelViewSet):
    queryset = Manufacturer.objects.all()
    serializer_class = ManufacturerSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['country', 'company_name']
    search_fields = ['company_name', 'company_alias', 'gst_number']
    ordering_fields = ['company_name', 'created_at']

class InverterViewSet(viewsets.ModelViewSet):
    serializer_class = InverterSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['city', 'state', 'country', 'manufacturer']
    search_fields = ['name', 'serial_number', 'city']
    ordering_fields = ['name', 'installation_date', 'created_at']
    
    def get_queryset(self):
        return (
            Inverter.objects.select_related("manufacturer")
            .filter(user=self.request.user)
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['get'])
    def hourly_energy(self, request, pk=None):
        inverter = self.get_object()
        measurement_time = request.query_params.get('measurement_time')
        try:
            measurement_time = datetime.fromisoformat(measurement_time) if measurement_time else timezone.now()
            energy = inverter.get_hourly_energy(measurement_time)
            return Response({'energy_generated': energy}, status=status.HTTP_200_OK)
        except ValueError:
            return Response({'error': 'Invalid datetime format'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def weekly_energy(self, request, pk=None):
        inverter = self.get_object()
        start_date = request.query_params.get('start_date')
        try:
            start_date = datetime.fromisoformat(start_date) if start_date else timezone.now()
            energy = inverter.get_weekly_energy(start_date)
            return Response({'total_energy': energy}, status=status.HTTP_200_OK)
        except ValueError:
            return Response({'error': 'Invalid datetime format'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def yearly_energy(self, request, pk=None):
        inverter = self.get_object()
        year = request.query_params.get('year')
        try:
            year = int(year) if year else timezone.now().year
            energy = inverter.get_yearly_energy(year)
            return Response({'total_energy': energy}, status=status.HTTP_200_OK)
        except ValueError:
            return Response({'error': 'Invalid year format'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def all_weekly_totals(self, request, pk=None):
        inverter = self.get_object()
        weekly_totals = inverter.get_all_weekly_totals()
        return Response(list(weekly_totals), status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def all_yearly_totals(self, request, pk=None):
        inverter = self.get_object()
        yearly_totals = inverter.get_all_yearly_totals()
        return Response(list(yearly_totals), status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def monthly_energy(self, request, pk=None):
        """
        Get total energy generated in a specific month.
        Query params:
        - year (int)
        - month (int, 1-12)
        """
        inverter = self.get_object()
        year = request.query_params.get("year")
        month = request.query_params.get("month")

        if not year or not month:
            return Response(
                {"error": "year and month query parameters are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            year = int(year)
            month = int(month)

            if month < 1 or month > 12:
                raise ValueError("Invalid month")

            start_date = datetime(year, month, 1)

            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)

            total_energy = inverter.power_generation.filter(
                measurement_time__gte=start_date,
                measurement_time__lt=end_date
            ).aggregate(
                total=Sum("energy_generated")
            )["total"] or 0

            return Response(
                {
                    "year": year,
                    "month": month,
                    "total_energy": float(total_energy),
                },
                status=status.HTTP_200_OK
            )

        except ValueError:
            return Response(
                {"error": "Invalid year or month"},
                status=status.HTTP_400_BAD_REQUEST
            )

class ActivationViewSet(viewsets.ModelViewSet):
    serializer_class = ActivationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['inverter']
    ordering_fields = ['activation_time']

    def get_queryset(self):
        return (
            Activation.objects.select_related("inverter")
            .filter(user=self.request.user)
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class InverterDataViewSet(viewsets.ModelViewSet):
    serializer_class = InverterDataSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['inverter', 'grid_connected']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']  # default latest first

    def get_queryset(self):
        qs = (
            InverterData.objects
            .select_related("inverter__manufacturer")
            .filter(inverter__user=self.request.user)
        )

        # --- Time filters ---
        start = self.request.query_params.get("start")
        end = self.request.query_params.get("end")

        if start:
            start_dt = parse_datetime(start)
            if start_dt:
                qs = qs.filter(timestamp__gte=start_dt)

        if end:
            end_dt = parse_datetime(end)
            if end_dt:
                qs = qs.filter(timestamp__lte=end_dt)

        return qs
        
        
class PowerGenerationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Secure Power Generation APIs
    """
    serializer_class = PowerGenerationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PowerGeneration.objects.filter(
            inverter__user=self.request.user
        ).select_related("inverter", "inverter__manufacturer")

    # ---------------- CREATE POWER DATA ----------------
    @action(detail=False, methods=['post'], url_path='create')
    def create_power(self, request):
        data = request.data

        required_fields = ["inverter_serial", "energy_generated"]
        for field in required_fields:
            if field not in data:
                return Response(
                    {"error": f"Missing field: {field}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        try:
            inverter = Inverter.objects.get(
                serial_number=data["inverter_serial"],
                user=request.user
            )
        except Inverter.DoesNotExist:
            return Response(
                {"error": "Inverter not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        measurement_time = data.get("measurement_time")
        measurement_time = (
            parse_datetime(measurement_time)
            if measurement_time else timezone.now()
        )

        if measurement_time is None:
            return Response(
                {"error": "Invalid datetime format"},
                status=status.HTTP_400_BAD_REQUEST
            )

        power = PowerGeneration.objects.create(
            inverter=inverter,
            energy_generated=data["energy_generated"],
            measurement_time=measurement_time
        )

        return Response(
            {
                "status": "success",
                "id": power.id,
                "measurement_time": power.measurement_time,
                "energy_generated": float(power.energy_generated),
            },
            status=status.HTTP_201_CREATED
        )

    # ---------------- ANALYTICS ----------------
    @action(detail=False, methods=['get'], url_path='analytics')
    def analytics(self, request):
        hours = int(request.query_params.get("hours", 24))
        inverter_id = request.query_params.get("inverter_id")
        aggregation = request.query_params.get("aggregation", "hourly")

        end_time = timezone.now()
        start_time = end_time - timedelta(hours=hours)

        queryset = self.get_queryset().filter(
            measurement_time__gte=start_time,
            measurement_time__lte=end_time
        )

        if inverter_id:
            queryset = queryset.filter(inverter__serial_number=inverter_id)

        if aggregation == "raw":
            data = self._raw_data(queryset)
        elif aggregation == "daily":
            data = self._daily_data(queryset)
        else:
            data = self._hourly_data(queryset)

        return Response(
            {
                "status": "success",
                "data": data,
                "summary": self._summary(queryset),
            }
        )

    # ---------------- HELPERS ----------------
    def _raw_data(self, queryset):
        return [
            {
                "time": r.measurement_time,
                "inverter": r.inverter.serial_number,
                "energy": float(r.energy_generated),
            }
            for r in queryset
        ]

    def _hourly_data(self, queryset):
        return list(
            queryset.annotate(hour=TruncHour("measurement_time"))
            .values("hour", "inverter__serial_number")
            .annotate(total=Sum("energy_generated"))
            .order_by("hour")
        )

    def _daily_data(self, queryset):
        return list(
            queryset.annotate(day=TruncDay("measurement_time"))
            .values("day", "inverter__serial_number")
            .annotate(total=Sum("energy_generated"))
            .order_by("day")
        )

    def _summary(self, queryset):
        agg = queryset.aggregate(
            total=Sum("energy_generated"),
            avg=Avg("energy_generated"),
            max=Max("energy_generated"),
            min=Min("energy_generated"),
            count=Count("id")
        )
        return {
            "records": agg["count"],
            "total_energy": float(agg["total"] or 0),
            "average_energy": float(agg["avg"] or 0),
            "max_energy": float(agg["max"] or 0),
            "min_energy": float(agg["min"] or 0),
        }
    
    @action(detail=False, methods=["get"], url_path="user-total")
    def user_total(self, request):
        """
        Total energy generated by ALL inverters of the logged-in user
        """
        qs = self.get_queryset()

        agg = qs.aggregate(
            total_energy=Sum("energy_generated"),
            inverter_count=Count("inverter", distinct=True)
        )

        return Response({
            "user_id": request.user.id,
            "total_inverters": agg["inverter_count"],
            "total_energy_kwh": float(agg["total_energy"] or 0),
        })
    
    @action(detail=False, methods=["get"], url_path="user-summary")
    def user_summary(self, request):
        """
        Per-inverter totals + grand total (dashboard ready)
        """
        qs = self.get_queryset()

        per_inverter = (
            qs.values(
                "inverter__serial_number",
                "inverter__name"
            )
            .annotate(total_energy=Sum("energy_generated"))
            .order_by("inverter__name")
        )

        grand_total = qs.aggregate(
            total=Sum("energy_generated")
        )["total"] or 0

        return Response({
            "total_energy_kwh": float(grand_total),
            "inverters": [
                {
                    "serial_number": row["inverter__serial_number"],
                    "name": row["inverter__name"],
                    "energy_kwh": float(row["total_energy"]),
                }
                for row in per_inverter
            ]
        })

class MQTTViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def publish(self, request):
        topic = request.data.get("topic")
        message = request.data.get("message")

        if not topic or not message:
            return Response(
                {"error": "topic and message required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not mqtt_client or not mqtt_client.is_connected():
            return Response(
                {"error": "MQTT not connected"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        mqtt_client.publish(topic, message)
        return Response({"status": "published"})

    @action(detail=False, methods=['get'])
    def health(self, request):
        return Response(
            {
                "connected": bool(mqtt_client and mqtt_client.is_connected()),
                "last_message": get_last_message_timestamp(),
            }
        )


class HealthViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def db(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return Response({"database": "ok"})
        except Exception as exc:
            return Response(
                {"database": "error", "details": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )   