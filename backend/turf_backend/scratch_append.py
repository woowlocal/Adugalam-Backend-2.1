import os

views_path = r"e:\Adugalam_Main Updated on 25.03.26\Backend\turf_backend\core\views.py"

content = """
# ---- Admin Bulk Peak Hours ----
from datetime import datetime
from .models import PeakHour, Slot, Game

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_set_bulk_peak_hours(request):
    if request.user.role != "ADMIN":
        return Response({"error": "Access denied."}, status=403)

    turf_id = request.data.get("turf_id")
    configs = request.data.get("configs", [])

    try:
        turf = Turf.objects.get(id=turf_id)
        game = Game.objects.filter(turf=turf).first()

        for conf in configs:
            date = conf.get("date")
            start_str = conf.get("start")
            end_str = conf.get("end")
            amount = conf.get("amount")

            if not all([date, start_str, end_str, amount]):
                continue

            try:
                start_t = datetime.strptime(start_str, "%H:%M").time()
                end_t = datetime.strptime(end_str, "%H:%M").time()
            except ValueError:
                try:
                    start_t = datetime.strptime(start_str, "%H:%M:%S").time()
                    end_t = datetime.strptime(end_str, "%H:%M:%S").time()
                except:
                    continue

            slots = Slot.objects.filter(turf=turf, start_time__gte=start_t, end_time__lte=end_t)
            
            for slot in slots:
                PeakHour.objects.update_or_create(
                    turf=turf,
                    slot=slot,
                    date=date,
                    defaults={
                        "game": game,
                        "from_time": slot.start_time,
                        "to_time": slot.end_time,
                        "peak_price": amount,
                    }
                )

        return Response({"success": True})
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_get_vendor_turfs(request, vendor_id):
    if request.user.role != "ADMIN":
        return Response({"error": "Access denied."}, status=403)
        
    try:
        vendor = Vendor.objects.get(vendor_id=vendor_id)
        turfs = Turf.objects.filter(vendor=vendor)
        
        data = []
        for t in turfs:
            data.append({
                "id": t.id,
                "name": t.name,
                "location": t.location,
            })
            
        return Response(data)
    except Vendor.DoesNotExist:
        return Response({"error": "Vendor not found."}, status=404)
        
"""
with open(views_path, "a") as f:
    f.write(content)
