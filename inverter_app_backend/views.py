from rest_framework.response import Response
from rest_framework.views import APIView

class Home(APIView):
    def get(self, request):
        return Response({
            "status": "ok",
            "service": "Inverter Monitoring API",
            "version": "1.0.0"
        })