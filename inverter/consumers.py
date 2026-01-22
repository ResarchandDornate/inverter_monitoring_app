"""Channels consumer for streaming inverter data over WebSockets."""

import json
from datetime import timedelta

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import Avg, Max, Min
from django.utils import timezone

class InverterConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Join inverter updates group
        await self.channel_layer.group_add(
            'inverter_updates',
            self.channel_name
        )
        await self.accept()
        
        # Send initial data when client connects
        await self.send_latest_data()

    async def disconnect(self, close_code):
        # Leave inverter updates group
        await self.channel_layer.group_discard(
            'inverter_updates',
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'get_latest_data':
                await self.send_latest_data()
            elif message_type == 'get_historical_data':
                # Get historical data for charts
                hours = text_data_json.get('hours', 24)  # Default 24 hours
                await self.send_historical_data(hours)
            elif message_type == 'ping':
                # Respond to ping to keep connection alive
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': timezone.now().isoformat()
                }))
                
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    async def send_latest_data(self):
        """Send the latest inverter data"""
        try:
            latest_data = await self.get_latest_inverter_data()
            
            await self.send(text_data=json.dumps({
                'type': 'latest_data',
                'data': latest_data,
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Failed to get latest data: {str(e)}"
            }))

    async def send_historical_data(self, hours=24):
        """Send historical data for charts"""
        try:
            historical_data = await self.get_historical_inverter_data(hours)
            
            await self.send(text_data=json.dumps({
                'type': 'historical_data',
                'data': historical_data,
                'hours': hours,
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Failed to get historical data: {str(e)}"
            }))

    async def inverter_message(self, event):
        """Handle real-time inverter data from MQTT"""
        message = event['message']
        
        # Get the latest database record to send complete data
        try:
            latest_data = await self.get_latest_inverter_data()
            
            # Send real-time update to WebSocket
            await self.send(text_data=json.dumps({
                'type': 'real_time_update',
                'mqtt_data': {
                    'topic': message.get('topic'),
                    'raw_data': message.get('data'),
                    'esp32_timestamp': message.get('timestamp')
                },
                'database_data': latest_data,
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            # If database query fails, still send the MQTT data
            await self.send(text_data=json.dumps({
                'type': 'real_time_update',
                'mqtt_data': {
                    'topic': message.get('topic'),
                    'raw_data': message.get('data'),
                    'esp32_timestamp': message.get('timestamp')
                },
                'error': f"Database query failed: {str(e)}",
                'timestamp': timezone.now().isoformat()
            }))

    @database_sync_to_async
    def get_latest_inverter_data(self):
        """Get latest inverter data from database"""
        from .models import InverterData, Inverter

        # Eagerly load manufacturer to avoid N+1 queries when serialising.
        inverters = (
            Inverter.objects.select_related("manufacturer")
            .all()
        )

        inverters_data = []
        for inverter in inverters:
            latest_data = InverterData.objects.filter(
                inverter=inverter
            ).order_by("-timestamp").select_related("inverter", "inverter__manufacturer").first()
            
            if latest_data:
                inverters_data.append({
                    'inverter_id': inverter.serial_number,
                    'inverter_model': inverter.model,
                    'manufacturer': inverter.manufacturer.name,
                    'voltage': float(latest_data.voltage),
                    'current': float(latest_data.current),
                    'power': float(latest_data.power),
                    'temperature': latest_data.temperature,
                    'grid_connected': latest_data.grid_connected,
                    'timestamp': latest_data.timestamp.isoformat(),
                    'capacity': inverter.capacity,
                    'efficiency': round((float(latest_data.power) / inverter.capacity) * 100, 2) if inverter.capacity > 0 else 0
                })
        
        return inverters_data

    @database_sync_to_async
    def get_historical_inverter_data(self, hours=24):
        """Get historical inverter data for charts"""
        from .models import InverterData, Inverter
        
        # Calculate time range
        end_time = timezone.now()
        start_time = end_time - timedelta(hours=hours)
        
        historical_data = {}

        # Preload manufacturer to reduce per-inverter database hits.
        inverters = Inverter.objects.select_related("manufacturer").all()
        for inverter in inverters:
            # Get data points for the time range
            data_points = InverterData.objects.filter(
                inverter=inverter,
                timestamp__gte=start_time,
                timestamp__lte=end_time
            ).order_by("timestamp").select_related("inverter")
            
            # Convert to list for JSON serialization
            points = []
            for point in data_points:
                points.append({
                    'timestamp': point.timestamp.isoformat(),
                    'voltage': float(point.voltage),
                    'current': float(point.current),
                    'power': float(point.power),
                    'temperature': point.temperature,
                    'grid_connected': point.grid_connected
                })
            
            # Calculate statistics
            stats = data_points.aggregate(
                avg_power=Avg('power'),
                max_power=Max('power'),
                min_power=Min('power'),
                avg_voltage=Avg('voltage'),
                avg_current=Avg('current'),
                avg_temperature=Avg('temperature')
            )
            
            historical_data[inverter.serial_number] = {
                'inverter_info': {
                    'id': inverter.serial_number,
                    'model': inverter.model,
                    'manufacturer': inverter.manufacturer.name,
                    'capacity': inverter.capacity
                },
                'data_points': points,
                'statistics': {
                    'avg_power': float(stats['avg_power']) if stats['avg_power'] else 0,
                    'max_power': float(stats['max_power']) if stats['max_power'] else 0,
                    'min_power': float(stats['min_power']) if stats['min_power'] else 0,
                    'avg_voltage': float(stats['avg_voltage']) if stats['avg_voltage'] else 0,
                    'avg_current': float(stats['avg_current']) if stats['avg_current'] else 0,
                    'avg_temperature': float(stats['avg_temperature']) if stats['avg_temperature'] else 0,
                    'total_points': len(points)
                }
            }
        
        return historical_data
