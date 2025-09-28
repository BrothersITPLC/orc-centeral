from datetime import datetime, timedelta

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils.timezone import make_aware
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from analysis.views.helpers import (
    annotate_revenue_on_checkins,
    parse_and_validate_date_range,
)
from declaracions.models import Checkin


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def admin_combined_taxpayer_report(request):
    selected_date_type = request.query_params.get("selected_date_type")
    start_date = request.query_params.get("start_date")
    end_date = request.query_params.get("end_date")

    if not selected_date_type or not start_date or not end_date:
        return Response({"error": "Missing required parameters."}, status=400)

    validation_response = parse_and_validate_date_range(
        start_date, end_date, selected_date_type
    )
    if validation_response:
        return validation_response

    try:
        start_date = make_aware(datetime.strptime(start_date, "%Y-%m-%d"))
        end_date = make_aware(
            datetime.strptime(end_date, "%Y-%m-%d")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
    except ValueError:
        return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

    checkin_filters = Q(
        status__in=["pass", "paid", "success"],
        checkin_time__range=[start_date, end_date],
        declaracion__exporter__isnull=False,
    ) | Q(
        status__in=["pass", "paid", "success"],
        checkin_time__range=[start_date, end_date],
        localJourney__exporter__isnull=False,
    )

    base_checkins = Checkin.objects.filter(checkin_filters)

    checkins_with_revenue = annotate_revenue_on_checkins(base_checkins)

    report_data = (
        checkins_with_revenue.annotate(
            exporter_id=Coalesce(
                "declaracion__exporter__id", "localJourney__exporter__id"
            ),
            first_name=Coalesce(
                "declaracion__exporter__first_name",
                "localJourney__exporter__first_name",
            ),
            last_name=Coalesce(
                "declaracion__exporter__last_name", "localJourney__exporter__last_name"
            ),
            tin_number=Coalesce(
                "declaracion__exporter__tin_number",
                "localJourney__exporter__tin_number",
            ),
            unique_id=Coalesce(
                "declaracion__exporter__unique_id", "localJourney__exporter__unique_id"
            ),
            type_name=Coalesce(
                "declaracion__exporter__type__name",
                "localJourney__exporter__type__name",
            ),
        )
        .values(
            "exporter_id",
            "first_name",
            "last_name",
            "tin_number",
            "unique_id",
            "type_name",
        )
        .annotate(
            total_revenue=Sum("revenue"),
            total_amount=Sum("incremental_weight"),
            merchant_path_count=Count("declaracion_id", distinct=True),
            local_path_count=Count("localJourney_id", distinct=True),
        )
        .order_by("-total_revenue")
    )

    final_report = [
        {
            "TIN/uniqe_id": f"{item['tin_number']}/{item['unique_id']}",
            "type": item["type_name"],
            "exporter_name": f"{item['first_name']} {item['last_name']}",
            "total_amount": item["total_amount"],
            "total_revenue": round(item["total_revenue"], 2),
            "total_merchant_paths": item["merchant_path_count"],
            "total_local_paths": item["local_path_count"],
        }
        for item in report_data
    ]

    return Response(final_report)
