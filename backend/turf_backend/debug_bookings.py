import os
import django
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "turf_backend.settings")
django.setup()

from core.models import Turf, Booking

turfs = Turf.objects.all()
res = []
for t in turfs:
    res.append({
        "turf_id": t.id,
        "name": t.name,
        "owner_email": t.owner.email if t.owner else None,
        "vendor_email": t.vendor.email if t.vendor else None,
        "vendor_code": t.vendor_code
    })

bookings = Booking.objects.all()
b_res = []
for b in bookings:
    b_res.append({
        "booking_id": b.id,
        "turf_id": b.turf_id,
        "turf_name": b.turf.name if b.turf else None,
        "turf_owner": b.turf.owner.email if (b.turf and b.turf.owner) else None,
        "turf_vendor_email": b.turf.vendor.email if (b.turf and b.turf.vendor) else None,
        "user_email": b.user.email if b.user else None,
        "status": b.status
    })

with open('debug_output.json', 'w') as f:
    json.dump({"turfs": res, "bookings": b_res}, f, indent=2)
