from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.utils import timezone


def money(value):
    return value or Decimal("0.00")


def decimal_payload(value):
    return str(money(value).quantize(Decimal("0.01")))


def parse_date_param(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def selected_month_range(request):
    today = timezone.localdate()
    month = request.GET.get("mes", today.strftime("%Y-%m"))
    try:
        year, month_number = [int(part) for part in month.split("-", 1)]
        first_day = date(year, month_number, 1)
    except (TypeError, ValueError):
        first_day = today.replace(day=1)
        month = first_day.strftime("%Y-%m")
    last_day = first_day.replace(day=monthrange(first_day.year, first_day.month)[1])
    return month, first_day, last_day
