from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils.timezone import make_aware
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from analysis.views.helpers import parse_and_validate_date_range
from declaracions.models import Checkin


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def admin_combined_taxpayer_report(request):
    selected_date_type = request.query_params.get("selected_date_type")
    start_date_str = request.query_params.get("start_date")
    end_date_str = request.query_params.get("end_date")

    if not selected_date_type or not start_date_str or not end_date_str:
        return Response(
            {"error": "Missing required parameters."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        start_date, inclusive_end_date = parse_and_validate_date_range(
            start_date_str, end_date_str, selected_date_type
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    checkin_filters = Q(
        status__in=["pass", "paid", "success"],
        checkin_time__range=[start_date, inclusive_end_date],
        declaracion__exporter__isnull=False,
    ) | Q(
        status__in=["pass", "paid", "success"],
        checkin_time__range=[start_date, inclusive_end_date],
        localJourney__exporter__isnull=False,
    )

    # Get checkins with related data to avoid N+1 queries
    checkins = (
        Checkin.objects.filter(checkin_filters)
        .select_related("declaracion__exporter__type", "localJourney__exporter__type")
        .order_by("declaracion_id", "localJourney_id", "checkin_time")
    )

    # Dictionary to store aggregated data by exporter
    exporter_data = defaultdict(
        lambda: {
            "total_revenue": Decimal("0"),
            "total_amount": Decimal("0"),
            "merchant_paths": set(),
            "local_paths": set(),
            "first_name": "",
            "last_name": "",
            "tin_number": "",
            "unique_id": "",
            "type_name": "",
        }
    )

    # Track previous weights for each journey to calculate incremental weight
    previous_weights = {}

    for checkin in checkins:
        # Determine exporter and journey info
        if checkin.declaracion and checkin.declaracion.exporter:
            exporter = checkin.declaracion.exporter
            journey_key = f"decl_{checkin.declaracion_id}"
            journey_type = "merchant"
        elif checkin.localJourney and checkin.localJourney.exporter:
            exporter = checkin.localJourney.exporter
            journey_key = f"local_{checkin.localJourney_id}"
            journey_type = "local"
        else:
            continue  # Skip if no exporter

        exporter_id = exporter.id

        # Initialize exporter data if this is the first time we see this exporter
        if not exporter_data[exporter_id]["first_name"]:
            exporter_data[exporter_id].update(
                {
                    "first_name": exporter.first_name or "",
                    "last_name": exporter.last_name or "",
                    "tin_number": exporter.tin_number or "",
                    "unique_id": exporter.unique_id or "",
                    "type_name": exporter.type.name if exporter.type else "",
                }
            )

        # Calculate incremental weight
        previous_weight = previous_weights.get(journey_key, Decimal("0"))
        current_weight = checkin.net_weight or Decimal("0")
        incremental_weight = max(current_weight - previous_weight, Decimal("0"))

        # Update previous weight for next iteration
        previous_weights[journey_key] = current_weight

        # Calculate revenue for this checkin
        unit_price = checkin.unit_price or Decimal("0")
        rate = checkin.rate or Decimal("0")
        revenue = (
            incremental_weight * (unit_price / Decimal("100")) * (rate / Decimal("100"))
        )

        # Aggregate data
        exporter_data[exporter_id]["total_revenue"] += revenue
        exporter_data[exporter_id]["total_amount"] += incremental_weight

        # Track unique paths
        if journey_type == "merchant" and checkin.declaracion_id:
            exporter_data[exporter_id]["merchant_paths"].add(checkin.declaracion_id)
        elif journey_type == "local" and checkin.localJourney_id:
            exporter_data[exporter_id]["local_paths"].add(checkin.localJourney_id)

    # Convert to final report format
    final_report = []
    for exporter_id, data in exporter_data.items():
        final_report.append(
            {
                "TIN/uniqe_id": f"{data['tin_number']}/{data['unique_id']}",
                "type": data["type_name"],
                "exporter_name": f"{data['first_name']} {data['last_name']}".strip(),
                "total_amount": float(data["total_amount"]),
                "total_revenue": round(float(data["total_revenue"]), 2),
                "total_merchant_paths": len(data["merchant_paths"]),
                "total_local_paths": len(data["local_paths"]),
            }
        )

    # Sort by total revenue descending
    final_report.sort(key=lambda x: x["total_revenue"], reverse=True)

    return Response(final_report)
