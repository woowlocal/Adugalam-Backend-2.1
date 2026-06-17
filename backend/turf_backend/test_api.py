import os
import django
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "turf_backend.settings")
django.setup()

from core.models import Turf, Booking, AppUser

owner = AppUser.objects.get(email="charles9025032966@gmail.com")

turfs = Turf.objects.filter(owner=owner)
turf_ids = list(turfs.values_list("id", flat=True))

qs = (
    Booking.objects.select_related("user", "turf", "game")
    .prefetch_related("slots")
    .filter(turf_id__in=turf_ids)
    .order_by("-created_at")
)

data = []
for b in qs:
    slots = list(b.slots.all().order_by("start_time"))
    if slots:
        time_str = f"{slots[0].start_time.strftime('%I:%M %p')} - {slots[-1].end_time.strftime('%I:%M %p')}"
    else:
        time_str = "-"

    if hasattr(b, 'payment') and getattr(b, 'payment', None):
        payment_status = "Paid" if b.payment.status == "SUCCESS" else b.payment.status.capitalize()
    else:
        payment_status = "Pending"

    data.append({
        "id": f"#BK{b.id}",
        "raw_id": b.id,
        "player": b.user.name if getattr(b, 'user', None) else "-",
        "turf": b.turf.name if getattr(b, 'turf', None) else "-",
        "game": b.game.game_name if hasattr(b, "game") and getattr(b, "game", None) else "-",
        "date": b.date.strftime("%d-%m-%Y") if getattr(b, 'date', None) else "-",
        "time": time_str,
        "payment": payment_status,
        "refund": "Refunded" if getattr(b, 'status', None) == "REFUNDED" else "-",
        "status": getattr(b, 'status', "Pending").capitalize() if getattr(b, 'status', None) else "Pending"
    })

print(json.dumps(data, indent=2))
