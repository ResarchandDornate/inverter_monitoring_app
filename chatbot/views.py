from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.utils import timezone
from django.db.models import Sum, Avg
from datetime import timedelta
from .nlp import detect_intent
import re

from inverter.models import (
    Inverter,
    InverterData,
    PowerGeneration,
    Manufacturer
)

class ChatbotAPIView(APIView):
    """
    Grammar-aware, rule-based chatbot for inverter monitoring.
    NO LLM, answers only from DB and backend logic.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        message = request.data.get("message", "")
        text = message.lower().strip()
        now = timezone.now()

        intent = detect_intent(text)

        # --------------------------------------------------
        # TODAY ENERGY
        # --------------------------------------------------
        if intent == "today_energy":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            total = PowerGeneration.objects.filter(
                inverter__user=user,
                measurement_time__gte=start
            ).aggregate(total=Sum("energy_generated"))["total"] or 0

            return Response({
                "reply": f"Today total energy generated is {round(float(total), 2)} kWh."
            })

        # --------------------------------------------------
        # WEEKLY ENERGY
        # --------------------------------------------------
        if intent == "weekly_energy":
            start = now - timedelta(days=7)

            total = PowerGeneration.objects.filter(
                inverter__user=user,
                measurement_time__gte=start
            ).aggregate(total=Sum("energy_generated"))["total"] or 0

            return Response({
                "reply": f"Energy generated in the last 7 days is {round(float(total), 2)} kWh."
            })

        # --------------------------------------------------
        # MONTHLY ENERGY
        # --------------------------------------------------
        if intent == "monthly_energy":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            total = PowerGeneration.objects.filter(
                inverter__user=user,
                measurement_time__gte=start
            ).aggregate(total=Sum("energy_generated"))["total"] or 0

            return Response({
                "reply": f"This month total energy generated is {round(float(total), 2)} kWh."
            })

        # --------------------------------------------------
        # YEARLY ENERGY
        # --------------------------------------------------
        if intent == "yearly_energy":
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0)

            total = PowerGeneration.objects.filter(
                inverter__user=user,
                measurement_time__gte=start
            ).aggregate(total=Sum("energy_generated"))["total"] or 0

            return Response({
                "reply": f"This year total energy generated is {round(float(total), 2)} kWh."
            })

        # --------------------------------------------------
        # PER-INVERTER ENERGY (SERIAL NUMBER)
        # --------------------------------------------------
        serial_match = re.search(r"inverter\s+([a-z0-9\-]+)", text)
        if serial_match and "energy" in text:
            serial = serial_match.group(1)

            try:
                inverter = Inverter.objects.get(
                    serial_number__iexact=serial,
                    user=user
                )
            except Inverter.DoesNotExist:
                return Response({
                    "reply": f"Inverter with serial number {serial} not found."
                })

            total = inverter.power_generation.aggregate(
                total=Sum("energy_generated")
            )["total"] or 0

            return Response({
                "reply": f"Inverter {serial} has generated {round(float(total), 2)} kWh in total."
            })

        # --------------------------------------------------
        # INVERTER STATUS / OFFLINE
        # --------------------------------------------------
        if intent == "status":
            inverters = Inverter.objects.filter(user=user)

            offline = [
                inv.serial_number
                for inv in inverters
                if not inv.is_grid_connected()
            ]

            if not offline:
                return Response({
                    "reply": "All your inverters are currently online."
                })

            return Response({
                "reply": f"{len(offline)} inverter(s) are offline: {', '.join(offline)}."
            })

        # --------------------------------------------------
        # TEMPERATURE
        # --------------------------------------------------
        if intent == "temperature":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            avg_temp = InverterData.objects.filter(
                inverter__user=user,
                timestamp__gte=start
            ).aggregate(avg=Avg("temperature"))["avg"]

            if avg_temp is None:
                return Response({
                    "reply": "No temperature data available for today."
                })

            return Response({
                "reply": f"Average inverter temperature today is {round(avg_temp, 1)}°C."
            })

        # --------------------------------------------------
        # LIST INVERTERS
        # --------------------------------------------------
        if intent == "list_inverters":
            inverters = Inverter.objects.filter(user=user)

            if not inverters.exists():
                return Response({
                    "reply": "You do not have any registered inverters."
                })

            return Response({
                "reply": "Your inverters:\n" + "\n".join(
                    f"- {inv.name} ({inv.serial_number})"
                    for inv in inverters
                )
            })

        # --------------------------------------------------
        # MANUFACTURERS
        # --------------------------------------------------
        if intent == "manufacturer":
            manufacturers = Manufacturer.objects.values_list(
                "company_name", flat=True
            ).distinct()

            return Response({
                "reply": "Manufacturers:\n" + ", ".join(manufacturers)
            })

        # --------------------------------------------------
        # FALLBACK
        # --------------------------------------------------
        return Response({
            "reply": (
                "I didn’t fully understand that.\n\n"
                "You can ask:\n"
                "• Today / weekly / monthly / yearly energy\n"
                "• Energy of inverter SN123\n"
                "• Inverter status\n"
                "• Temperature\n"
                "• List my inverters\n"
                "• Manufacturer details"
            )
        })