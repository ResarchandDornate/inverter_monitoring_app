from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
from datetime import datetime
from datetime import timedelta 
from .models import Manufacturer, Inverter, Activation, InverterData, PowerGeneration
from .serializers import (
    ManufacturerSerializer, InverterSerializer, ActivationSerializer,
    InverterDataSerializer, PowerGenerationSerializer
)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count
from django.db.models import Sum, Avg, Max, Min

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
        return Inverter.objects.filter(user=self.request.user)

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

class ActivationViewSet(viewsets.ModelViewSet):
    serializer_class = ActivationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['inverter']
    ordering_fields = ['activation_time']

    def get_queryset(self):
        return Activation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class InverterDataViewSet(viewsets.ModelViewSet):
    serializer_class = InverterDataSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['inverter', 'grid_connected']
    ordering_fields = ['timestamp']

    def get_queryset(self):
        return InverterData.objects.filter(inverter__user=self.request.user)

class PowerGenerationViewSet(viewsets.ModelViewSet):
    serializer_class = PowerGenerationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['inverter']
    ordering_fields = ['measurement_time']

    def get_queryset(self):
        return PowerGeneration.objects.filter(inverter__user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent power generation data"""
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timedelta(hours=hours)
        
        queryset = self.get_queryset().filter(measurement_time__gte=since)
        
        # Get summary
        summary = calculate_power_generation_summary(queryset)
        
        # Get recent records
        recent_records = queryset[:10]
        serializer = self.get_serializer(recent_records, many=True)
        
        return Response({
            'summary': summary,
            'recent_records': serializer.data,
            'total_records': queryset.count()
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get PowerGeneration statistics"""
        queryset = self.get_queryset()
        
        # Overall stats
        total_records = queryset.count()
        
        # Recent stats (last 24 hours)
        recent_queryset = queryset.filter(
            measurement_time__gte=timezone.now() - timedelta(hours=24)
        )
        recent_count = recent_queryset.count()
        
        # Latest record
        latest_record = queryset.first()
        
        return Response({
            'total_records': total_records,
            'recent_24h_records': recent_count,
            'latest_record': {
                'id': latest_record.id if latest_record else None,
                'measurement_time': latest_record.measurement_time if latest_record else None,
                'energy_generated': latest_record.energy_generated if latest_record else None,
                'inverter_name': latest_record.inverter.name if latest_record else None,
            } if latest_record else None,
            'inverter_count': queryset.values('inverter').distinct().count()
        })
        
        
@api_view(['GET'])
def power_generation_api(request):
    """
    API endpoint for power generation data
    Query parameters:
    - hours: Number of hours to look back (default: 24)
    - inverter_id: Specific inverter serial number (optional)
    - aggregation: 'hourly', 'daily', or 'raw' (default: 'hourly')
    """
    try:
        # Get query parameters
        hours = int(request.GET.get('hours', 24))
        inverter_id = request.GET.get('inverter_id')
        aggregation = request.GET.get('aggregation', 'hourly')
        
        # Calculate time range
        end_time = timezone.now()
        start_time = end_time - timedelta(hours=hours)
        
        # Base queryset using PowerGeneration model
        queryset = PowerGeneration.objects.filter(
            measurement_time__gte=start_time,
            measurement_time__lte=end_time
        )
        
        # Filter by specific inverter if requested
        if inverter_id:
            queryset = queryset.filter(inverter__serial_number=inverter_id)
        
        # Get aggregated data based on request
        if aggregation == 'raw':
            data = get_raw_power_generation_data(queryset)
        elif aggregation == 'daily':
            data = get_daily_power_generation_data(queryset, start_time, end_time)
        else:  # hourly (default)
            data = get_hourly_power_generation_data(queryset, start_time, end_time)
        
        # Calculate summary statistics
        summary = calculate_power_generation_summary(queryset)
        
        return Response({
            'status': 'success',
            'data': data,
            'summary': summary,
            'parameters': {
                'hours': hours,
                'inverter_id': inverter_id,
                'aggregation': aggregation,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def get_raw_power_generation_data(queryset):
    """Get raw power generation data"""
    data = []
    for record in queryset.select_related('inverter'):
        data.append({
            'measurement_time': record.measurement_time.isoformat(),
            'inverter_id': record.inverter.serial_number,
            'inverter_name': record.inverter.name,
            'energy_generated': float(record.energy_generated),
            'inverter_capacity': record.inverter.inverter_capacity,
            'efficiency_factor': record.inverter.efficiency_factor,
            'location': f"{record.inverter.city}, {record.inverter.state}",
            'manufacturer': record.inverter.manufacturer.company_name if record.inverter.manufacturer else 'Unknown'
        })
    return data

def get_hourly_power_generation_data(queryset, start_time, end_time):
    """Get hourly aggregated power generation data"""
    from django.db.models.functions import TruncHour
    
    hourly_data = queryset.annotate(
        hour=TruncHour('measurement_time')
    ).values('hour', 'inverter__serial_number', 'inverter__name').annotate(
        total_energy=Sum('energy_generated'),
        avg_energy=Avg('energy_generated'),
        max_energy=Max('energy_generated'),
        min_energy=Min('energy_generated'),
        count_records=Count('id')
    ).order_by('hour', 'inverter__serial_number')
    
    data = []
    for record in hourly_data:
        data.append({
            'hour': record['hour'].isoformat(),
            'inverter_id': record['inverter__serial_number'],
            'inverter_name': record['inverter__name'],
            'total_energy_kwh': float(record['total_energy']) if record['total_energy'] else 0,
            'avg_energy_kwh': float(record['avg_energy']) if record['avg_energy'] else 0,
            'max_energy_kwh': float(record['max_energy']) if record['max_energy'] else 0,
            'min_energy_kwh': float(record['min_energy']) if record['min_energy'] else 0,
            'data_points': record['count_records']
        })
    return data

def get_daily_power_generation_data(queryset, start_time, end_time):
    """Get daily aggregated power generation data"""
    from django.db.models.functions import TruncDay
    
    daily_data = queryset.annotate(
        day=TruncDay('measurement_time')
    ).values('day', 'inverter__serial_number', 'inverter__name').annotate(
        total_energy=Sum('energy_generated'),
        avg_energy=Avg('energy_generated'),
        max_energy=Max('energy_generated'),
        min_energy=Min('energy_generated'),
        count_records=Count('id')
    ).order_by('day', 'inverter__serial_number')
    
    data = []
    for record in daily_data:
        data.append({
            'date': record['day'].date().isoformat(),
            'inverter_id': record['inverter__serial_number'],
            'inverter_name': record['inverter__name'],
            'total_energy_kwh': float(record['total_energy']) if record['total_energy'] else 0,
            'avg_energy_kwh': float(record['avg_energy']) if record['avg_energy'] else 0,
            'max_energy_kwh': float(record['max_energy']) if record['max_energy'] else 0,
            'min_energy_kwh': float(record['min_energy']) if record['min_energy'] else 0,
            'data_points': record['count_records']
        })
    return data

def calculate_power_generation_summary(queryset):
    """Calculate summary statistics for power generation"""
    summary = queryset.aggregate(
        total_records=Count('id'),
        total_energy=Sum('energy_generated'),
        avg_energy=Avg('energy_generated'),
        max_energy=Max('energy_generated'),
        min_energy=Min('energy_generated')
    )
    
    # Get inverter count
    inverter_count = queryset.values('inverter').distinct().count()
    
    # Get time range
    time_range = queryset.aggregate(
        earliest=Min('measurement_time'),
        latest=Max('measurement_time')
    )
    
    return {
        'total_records': summary['total_records'] or 0,
        'inverter_count': inverter_count,
        'total_energy_kwh': float(summary['total_energy']) if summary['total_energy'] else 0,
        'avg_energy_kwh': float(summary['avg_energy']) if summary['avg_energy'] else 0,
        'max_energy_kwh': float(summary['max_energy']) if summary['max_energy'] else 0,
        'min_energy_kwh': float(summary['min_energy']) if summary['min_energy'] else 0,
        'earliest_measurement': time_range['earliest'].isoformat() if time_range['earliest'] else None,
        'latest_measurement': time_range['latest'].isoformat() if time_range['latest'] else None
    }

# Additional API endpoint to create power generation data
@api_view(['POST'])
def create_power_generation_data(request):
    """
    API endpoint to create new power generation data
    Expected JSON payload:
    {
        "inverter_serial": "TEST123",
        "energy_generated": 25.5,
        "measurement_time": "2024-01-15T10:30:00Z"  # Optional, defaults to now
    }
    """
    try:
        data = request.data
        
        # Get inverter by serial number
        try:
            inverter = Inverter.objects.get(serial_number=data['inverter_serial'])
        except Inverter.DoesNotExist:
            return Response({
                'status': 'error',
                'message': f"Inverter with serial number '{data['inverter_serial']}' not found"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get measurement time (default to now if not provided)
        measurement_time = data.get('measurement_time')
        if measurement_time:
            from django.utils.dateparse import parse_datetime
            measurement_time = parse_datetime(measurement_time)
            if not measurement_time:
                return Response({
                    'status': 'error',
                    'message': 'Invalid measurement_time format. Use ISO format: YYYY-MM-DDTHH:MM:SSZ'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            measurement_time = timezone.now()
        
        # Create power generation record
        power_gen = PowerGeneration.objects.create(
            inverter=inverter,
            energy_generated=data['energy_generated'],
            measurement_time=measurement_time
        )
        
        return Response({
            'status': 'success',
            'message': 'Power generation data created successfully',
            'data': {
                'id': power_gen.id,
                'inverter_serial': inverter.serial_number,
                'inverter_name': inverter.name,
                'energy_generated': float(power_gen.energy_generated),
                'measurement_time': power_gen.measurement_time.isoformat()
            }
        }, status=status.HTTP_201_CREATED)
        
    except KeyError as e:
        return Response({
            'status': 'error',
            'message': f'Missing required field: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)