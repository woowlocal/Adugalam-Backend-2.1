import random
import secrets
from datetime import timedelta, datetime
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password
from math import radians, cos, sin, asin, sqrt
from django.db.models import F, Q
from django.contrib.auth import authenticate
from rest_framework.decorators import api_view, parser_classes
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt

import razorpay
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.generics import ListAPIView
# pyrefly: ignore [missing-import]
from .utils.email_service import (
    send_email_otp,
    generate_otp,
    send_vendor_approval_email,
    send_vendor_rejection_email,
    send_account_deletion_approved_email,
    send_account_deletion_rejected_email,
)
# from core.utils.whatsapp_service import send_whatsapp

from django.contrib.auth import get_user_model

User = get_user_model()

from core.serializers import (
    SlotSerializer,
    TurfSerializer,
    BookingListSerializer,
    VendorTurfCreateSerializer,
    AdminTurfCreateSerializer,
    UserIssueSerializer,
)
from core.models import (
    AppUser,
    UserManager,
    EmailOTP,
    Cart,
    Booking,
    Payment,
    Turf,
    Ground,
    Slot,
    AdminUser,
    Game,
    PeakHour,
    UserIssue,
)
# from core.utils.whatsapp_service import send_whatsapp


@api_view(["GET"])
def home(request):
    return Response({"message": "Home API working", "status": "ok"})


@api_view(["POST"])
def send_email_otp_view(request):
    email = request.data.get("email")

    # Check if an ACTIVE account already exists (retire=0 means active)
    if AppUser.objects.filter(email=email, retire=0).exists():
        return Response({"error": "Email already registered"}, status=400)

    # Check if account is pending deletion (retire=1)
    if AppUser.objects.filter(email=email, retire=1).exists():
        return Response(
            {
                "error": "Your account deletion request is pending admin approval. Please contact support."
            },
            status=400,
        )

    otp = generate_otp()

    EmailOTP.objects.update_or_create(
        email=email, defaults={"otp": otp, "is_verified": False}
    )

    send_email_otp(email, otp)

    return Response({"message": "OTP sent to email"})


#  VERIFY OTP
@api_view(["POST"])
def verify_email_otp_view(request):
    email = request.data.get("email")
    otp = request.data.get("otp")

    if not email or not otp:
        return Response({"error": "Email and OTP required"}, status=400)

    try:
        record = EmailOTP.objects.get(
            email=email,
            otp=otp,
            is_verified=False,  # 🔥 IMPORTANT FIX
        )

        if record.is_expired():
            record.delete()
            return Response({"error": "OTP expired"}, status=400)

        record.is_verified = True
        record.save()

        return Response({"message": "OTP verified"})

    except EmailOTP.DoesNotExist:
        return Response({"error": "Invalid OTP"}, status=400)


#  CREATE ACCOUNT
@api_view(["POST"])
def create_account_view(request):
    name = request.data.get("name")
    email = request.data.get("email")
    mobile = request.data.get("mobile")
    password = request.data.get("password")
    confirm_password = request.data.get("confirm_password")

    #  Basic validation
    if not all([name, email, mobile, password, confirm_password]):
        return Response({"error": "All fields are required"}, status=400)

    #  Password match check
    if password != confirm_password:
        return Response({"error": "Passwords do not match"}, status=400)

    #  OTP verification check
    otp_record = EmailOTP.objects.filter(email=email, is_verified=True).first()
    if not otp_record:
        return Response({"error": "OTP not verified"}, status=400)

    #  Create user
    user = AppUser.objects.create_user(
        email=email, password=password, name=name, mobile=mobile, is_verified=True
    )

    #  Cleanup OTP
    otp_record.delete()

    return Response({"message": "Account created successfully"})


#  LOGIN
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["POST"])
def login_view(request):
    email = request.data.get("email")
    password = request.data.get("password")

    user = authenticate(request, email=email, password=password)

    if not user:
        return Response({"error": "Invalid credentials"}, status=401)

    # Block login if account deletion is pending
    if getattr(user, "retire", 0) == 1:
        return Response(
            {
                "error": "Your account deletion request is pending admin approval. Contact support if this was a mistake."
            },
            status=403,
        )

    refresh = RefreshToken.for_user(user)

    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "mobile": user.mobile,
            },
        }
    )


@api_view(["POST"])
def send_reset_otp(request):
    email = request.data.get("email")

    user = AppUser.objects.filter(email=email).first()
    if not user:
        return Response({"error": "User not found"}, status=404)

    if user.retire == 1:
        return Response(
            {"error": "Account disabled. Please contact myadugalam@gmail.com for assistance."},
            status=403
        )

    EmailOTP.objects.filter(email=email).delete()  # clear old OTPs

    otp = generate_otp()
    EmailOTP.objects.create(email=email, otp=otp, is_verified=False)

    send_email_otp(email, otp)

    return Response({"message": "Reset OTP sent"})


@api_view(["GET"])
def list_turfs(request):
    game = request.GET.get("game")

    qs = (
        Turf.objects.select_related("owner", "vendor")
        .prefetch_related("banners", "gallery", "slot_items", "game_items")
        .filter(is_approved=True, is_maintenance=False, retire=0)
    )

    if game:
        qs = qs.filter(
            Q(games__icontains=game) | Q(game_items__game_name__icontains=game)
        ).distinct()

    qs = qs.order_by("-id")

    data = []

    for t in qs:
        available_slots = []

        # ✅ NEW SLOTS (SHOW ALL 24 HOURS — DO NOT FILTER)
        if hasattr(t, "slot_items") and t.slot_items.exists():
            # 🔥 IMPORTANT CHANGE: removed filter(is_available=True)
            slots_qs = t.slot_items.all().order_by("start_time")

            for slot in slots_qs:
                available_slots.append(
                    {
                        "id": slot.id,
                        "start_time": slot.start_time.strftime("%H:%M"),
                        "end_time": slot.end_time.strftime("%H:%M"),
                        "time_display": f"{slot.start_time.strftime('%I:%M %p')} - {slot.end_time.strftime('%I:%M %p')}",
                        "price_display": f"₹{slot.price}",
                        "price": slot.price,
                        "is_available": slot.is_available,  # frontend will grey if False
                    }
                )

        else:
            # Legacy JSON fallback
            for slot in t.slots or []:
                available_slots.append(
                    {
                        "id": slot.get("id"),
                        "start_time": slot.get("start_time", ""),
                        "end_time": slot.get("end_time", ""),
                        "time_display": slot.get("slot_display", ""),
                        "price": slot.get("price", t.price_per_hour),
                        "price_display": f"₹{slot.get('price', t.price_per_hour)}",
                        "is_available": not slot.get("is_booked", False),
                    }
                )

        data.append(
            {
                "id": t.id,
                "name": t.name,
                "location": t.location,
                "latitude": t.latitude,
                "longitude": t.longitude,
                "price_per_hour": t.price_per_hour,
                "description": t.description or "",
                "games": t.games
                if t.games
                else [g.game_name for g in t.game_items.all()],
                "amenities": t.amenities or [],
                "features": t.features or [],
                "banner_images": [img.image.url for img in t.banners.all()],
                "gallery_images": [img.image.url for img in t.gallery.all()],
                "slots": available_slots,
                "vendor": {
                    "vendor_id": getattr(t.vendor, "vendor_id", None)
                    if t.vendor
                    else None,
                    "venuename": getattr(t.vendor, "venuename", None)
                    if t.vendor
                    else None,
                },
                "owner": {
                    "id": t.owner.id if t.owner else None,
                    "username": t.owner.name if t.owner else None,
                    "email": t.owner.email if t.owner else None,
                }
                if t.owner
                else {"id": None, "username": None, "email": None},
                "is_approved": t.is_approved,
            }
        )

    return Response(data)


@api_view(["GET"])
def popular_turfs(request):
    game = request.GET.get("game")

    qs = Turf.objects.filter(is_approved=True, is_popular=True, is_maintenance=False, retire=0)

    if game:
        qs = qs.filter(
            Q(games__icontains=game) | Q(game_items__game_name__icontains=game)
        ).distinct()

    # Prefetch game_items to avoid N+1 issues
    qs = qs.prefetch_related("game_items", "banners")

    qs = qs.order_by("priority")

    data = []

    for t in qs:
        games_list = t.games if t.games else [g.game_name for g in t.game_items.all()]

        data.append(
            {
                "id": t.id,
                "name": t.name,
                "location": t.location,
                "price_per_hour": t.price_per_hour,
                "games": games_list,
                "banner_images": [img.image.url for img in t.banners.all()],
            }
        )

    return Response(data)


from rest_framework.decorators import api_view
from rest_framework.response import Response
# pyrefly: ignore [missing-import]
from .models import ContactMessage, HomepageBanner, LoveAdugalam, Turf
from django.db import models


@api_view(["GET"])
def turf_details(request, turf_id):

    try:
        # Prefetch all related rows in one DB round-trip (no extra queries)
        turf = Turf.objects.prefetch_related(
            "banners", "gallery", "slot_items", "game_items"
        ).get(id=turf_id, retire=0)
    except Turf.DoesNotExist:
        return Response({"error": "Turf not found"}, status=404)

    # Build slot list — price uses turf.price_per_hour (single source of truth)
    slots = [
        {
            "id": s.id,
            "start_time": s.start_time.strftime("%H:%M"),
            "end_time":   s.end_time.strftime("%H:%M"),
            "time_display": (
                f"{s.start_time.strftime('%I:%M %p')} - "
                f"{s.end_time.strftime('%I:%M %p')}"
            ),
            "price": turf.price_per_hour,
            "is_available": s.is_available,
        }
        for s in turf.slot_items.all().order_by("start_time")
    ]

    return Response(
        {
            "id": turf.id,
            "name": turf.name,
            "location": turf.location,
            "price_per_hour": turf.price_per_hour,
            # ── Detail fields (new) ──
            "description": turf.description or "",
            "amenities":   turf.amenities   or [],
            "features":    turf.features    or [],
            "games": [g.game_name for g in turf.game_items.all()],
            "slots": slots,
            # ── Images ──
            "banner_images": [
                request.build_absolute_uri(img.image.url)
                for img in turf.banners.all()
            ],
            "gallery_images": [
                request.build_absolute_uri(img.image.url)
                for img in turf.gallery.all()
            ],
        }
    )

@api_view(["GET"])
def ground_availability(request):
    turf_id = request.query_params.get("turf_id")
    game_type = request.query_params.get("game")
    if not turf_id or not game_type:
        return Response({"error": "turf_id and game required"}, status=400)
    grounds = Ground.objects.filter(turf_id=turf_id, game_type=game_type)
    data = []
    for ground in grounds:
        slots = Slot.objects.filter(ground=ground, is_booked=False).values()

        data.append(
            {
                "ground_id": ground.id,
                "ground_name": ground.name,
                "game": ground.game_type,
                "slots": list(slots),
            }
        )

    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_to_cart(request):

    turf_id = request.data.get("turf_id")
    date = request.data.get("date")
    slot_ids = request.data.get("slot_ids", [])

    if not turf_id or not date or not slot_ids:
        return Response({"error": "Missing fields"}, status=400)

    carts = []

    for slot_id in slot_ids:
        cart = Cart.objects.create(
            user=request.user, turf_id=turf_id, date=date, slot_id=slot_id
        )
        carts.append(cart.id)

    return Response({"message": "Added to cart", "cart_ids": carts})


from django.db import transaction
from django.db import transaction
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal


from django.db import transaction
from django.db import transaction
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def confirm_booking(request):
    turf_id = request.data.get("turf_id")
    game_id = request.data.get("game_id")
    slot_ids = request.data.get("slot_ids", [])
    date = request.data.get("date")

    if not all([turf_id, slot_ids, date]):
        return Response({"error": "Missing fields"}, status=400)

    # Validate or assign default game_id
    if not game_id or not Game.objects.filter(id=game_id, turf_id=turf_id).exists():
        first_game = Game.objects.filter(turf_id=turf_id).first()
        if first_game:
            game_id = first_game.id
        else:
            return Response({"error": "No games available for this turf"}, status=400)

    with transaction.atomic():
        # 🔥 CHECK AVAILABILITY (don't lock yet)
        available_slots = Slot.objects.select_for_update().filter(
            id__in=slot_ids, turf_id=turf_id, is_available=True
        )

        if available_slots.count() != len(slot_ids):
            return Response({"error": "Some slots already unavailable"}, status=400)

        # 🔥 NEW: Check for date-specific slot conflicts
        conflicts = Booking.objects.filter(
            turf_id=turf_id, date=date, status="CONFIRMED", slots__id__in=slot_ids
        )

        if conflicts.exists():
            return Response(
                {"error": "Some slots are already booked for this date"}, status=400
            )

        # ✅ 1️⃣ ORIGINAL AMOUNT (Respect Peak Hours)
        original_amount = Decimal("0.00")
        for s in available_slots:
            peak = PeakHour.objects.filter(turf_id=turf_id, slot=s, date=date).first()

            if peak:
                original_amount += Decimal(str(peak.peak_price))
            else:
                original_amount += Decimal(str(s.price))

        # ✅ 2️⃣ 30% ADVANCE
        advance_amount = Decimal(original_amount) * Decimal("0.30")

        # ✅ 3️⃣ SERVICE CHARGE
        service_charge = Decimal("3.00")

        # ✅ 4️⃣ TOTAL PAYABLE (Advance + Service)
        total_payable = advance_amount + service_charge

        # 🔥 CREATE PENDING BOOKING (slots stay available)
        booking = Booking.objects.create(
            user=request.user,
            user_name=request.user.name,
            user_email=request.user.email,
            user_mobile=request.user.mobile,
            turf_id=turf_id,
            game_id=game_id,
            date=date,
            original_amount=original_amount,
            advance_amount=advance_amount,
            service_charge=service_charge,
            total_payable=total_payable,
            status="PENDING",
        )

        booking.slots.set(available_slots)

    return Response(
        {
            "success": True,
            "booking_id": booking.id,
            "original_amount": float(original_amount),
            "advance_amount": float(advance_amount),
            "service_charge": float(service_charge),
            "total_payable": float(total_payable),
        },
        status=201,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def booking_detail(request, booking_id):

    try:
        booking = Booking.objects.prefetch_related("slots").get(
            id=booking_id, user=request.user
        )
    except Booking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=404)

    # Return all pricing fields correctly
    return Response(
        {
            "id": booking.id,
            "turf_name": booking.turf.name,
            "date": booking.date,
            "status": booking.status,
            "original_amount": booking.original_amount,
            "advance_amount": booking.advance_amount,
            "service_charge": booking.service_charge,
            "total_price": booking.total_payable,  # ✅ Use total_payable (advance + service)
            "slots": [
                {
                    "time_display": f"{s.start_time.strftime('%I:%M %p')} - {s.end_time.strftime('%I:%M %p')}",
                    "price": s.price,
                }
                for s in booking.slots.all()
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_payment_order(request):
    try:
        booking_id = request.data.get("booking_id")
        amount = request.data.get("amount")

        if not booking_id or not amount:
            return Response({"error": "Booking ID and amount required"}, status=400)

        booking = Booking.objects.get(id=booking_id, user=request.user)

        #  Prevent duplicate successful payment
        if hasattr(booking, "payment") and booking.payment.status == "SUCCESS":
            return Response({"error": "Payment already completed"}, status=400)

        #  Razorpay client
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        #  Create Razorpay order
        razorpay_order = client.order.create(
            {
                "amount": amount,  # already in paise
                "currency": "INR",
                "payment_capture": "1",
            }
        )

        #  Create or Update Payment (safe for OneToOne)
        payment, created = Payment.objects.update_or_create(
            booking=booking,
            defaults={
                "user": request.user,
                "razorpay_order_id": razorpay_order["id"],
                "amount": amount,
                "status": "PENDING",
            },
        )

        return Response({"order_id": razorpay_order["id"], "amount": amount})

    except Booking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=404)

    except Exception as e:
        print("Payment Order Error:", str(e))
        return Response({"error": "Something went wrong"}, status=500)

import threading
from django.core.mail import send_mail
from django.conf import settings

def send_booking_emails(booking):
    try:
        slots_str = ", ".join([f"{s.start_time.strftime('%I:%M %p')} - {s.end_time.strftime('%I:%M %p')}" for s in booking.slots.all()])
        user_name = booking.user_name or (booking.user.first_name if booking.user else "User")
        user_email = booking.user_email or (booking.user.email if booking.user else None)
        
        turf_name = booking.turf.name
        date_str = booking.date.strftime("%B %d, %Y") if booking.date else "TBD"
        amount = booking.total_payable

        # 1. Email to User
        if user_email:
            user_subject = f"Booking Confirmed at {turf_name}"
            user_message = f"Hello {user_name},\n\nYour booking at {turf_name} is confirmed!\n\nDetails:\nDate: {date_str}\nTime: {slots_str}\nTotal Paid: ₹{amount}\n\nEnjoy your game!\nAdugalam Team"
            send_mail(user_subject, user_message, settings.EMAIL_HOST_USER, [user_email], fail_silently=True)

        # 2. Email to Vendor
        vendor_email = None
        if booking.turf.vendor and booking.turf.vendor.email:
            vendor_email = booking.turf.vendor.email
            
        if vendor_email:
            vendor_subject = f"New Booking Alert: {turf_name}"
            vendor_message = f"Hello Vendor,\n\nA new booking has been made at {turf_name}.\n\nDetails:\nPlayer: {user_name}\nDate: {date_str}\nTime: {slots_str}\nAmount Paid: ₹{amount}\n\nPlease check your vendor dashboard for more details."
            send_mail(vendor_subject, vendor_message, settings.EMAIL_HOST_USER, [vendor_email], fail_silently=True)

        # 3. Email to Admin
        admin_subject = f"Admin Alert: New Booking at {turf_name}"
        admin_message = f"A new booking was successfully processed.\n\nTurf: {turf_name}\nPlayer: {user_name} ({user_email})\nDate: {date_str}\nTime: {slots_str}\nAmount: ₹{amount}"
        send_mail(admin_subject, admin_message, settings.EMAIL_HOST_USER, [settings.EMAIL_HOST_USER], fail_silently=True)

    except Exception as e:
        print("Error sending confirmation emails:", str(e))

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_payment(request):

    booking_id = request.data.get("booking_id")
    payment_id = request.data.get("payment_id")

    with transaction.atomic():
        booking = (
            Booking.objects.select_for_update()
            .select_related("turf")
            .get(id=booking_id, user=request.user)
        )

        payment = Payment.objects.get(booking=booking)

        payment.razorpay_payment_id = payment_id
        payment.amount = int(booking.total_payable * 100)
        payment.status = "SUCCESS"
        payment.save()

        # 🔥 NOW lock the slots (only on SUCCESS payment)
        # booking.slots.update(is_available=False)

        booking.status = "CONFIRMED"
        booking.vendor_status = "ACTIVE"
        booking.save()

    # Trigger emails asynchronously
    threading.Thread(target=send_booking_emails, args=(booking,)).start()

    #     send_whatsapp(
    #         booking.user.mobile,
    #         f"""Booking Confirmed! 🎉
    #
    # Turf: {booking.turf.name}
    # Date: {booking.date}
    #
    # Enjoy your game!"""
    #     )

    return Response({"success": True})

@api_view(["GET"])
def nearby_turfs(request):
    lat = request.query_params.get("lat")
    lng = request.query_params.get("lng")
    radius_km = float(request.query_params.get("radius", 10))
    game = request.query_params.get("game")

    if not lat or not lng:
        return Response({"error": "lat and lng required"}, status=400)

    lat = float(lat)
    lng = float(lng)

    qs = Turf.objects.filter(is_approved=True, is_maintenance=False, retire=0)

    if game:
        qs = qs.filter(
            Q(games__icontains=game) | Q(game_items__game_name__icontains=game)
        ).distinct()

    qs = qs.prefetch_related("game_items", "banners")

    results = []
    for turf in qs:
        if turf.latitude is None or turf.longitude is None:
            continue

        # Haversine distance
        dlat = radians(turf.latitude - lat)
        dlon = radians(turf.longitude - lng)
        a = (
            sin(dlat / 2) ** 2
            + cos(radians(lat)) * cos(radians(turf.latitude)) * sin(dlon / 2) ** 2
        )
        c = 2 * asin(sqrt(a))
        distance = 6371 * c  # km

        if distance <= radius_km:
            games_list = [g.game_name for g in turf.game_items.all()]
            results.append(
                {
                    "id": turf.id,
                    "name": turf.name,
                    "location": turf.location,
                    "distance_km": round(distance, 2),
                    "price_per_hour": turf.price_per_hour,
                    "games": games_list,
                    "banner_images": [img.image.url for img in turf.banners.all()],
                }
            )

    return Response(results)

@api_view(["GET"])
def turf_games(request, turf_id):
    games = Ground.objects.filter(turf_id=turf_id).values("game_type").distinct()
    return Response(list(games))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_bookings(request):

    bookings = Booking.objects.filter(user=request.user).select_related(
        "turf", "slot", "game"
    )

    data = []

    for b in bookings:
        data.append(
            {
                "id": b.id,
                "turf_name": b.turf.name,
                "game": b.game.game_name,
                "date": b.date,
                "start_time": b.slot.start_time,
                "end_time": b.slot.end_time,
                "status": b.status,
            }
        )

    return Response(data)


from django.contrib.auth.hashers import make_password
from rest_framework.decorators import api_view
from rest_framework.response import Response
from core.models import AppUser, EmailOTP


@api_view(["POST"])
def reset_password(request):
    email = request.data.get("email")
    new_password = request.data.get("password")
    otp = request.data.get("otp")

    if not all([email, new_password, otp]):
        return Response({"error": "Missing fields"}, status=400)

    # 1️⃣ Verify OTP
    try:
        otp_obj = EmailOTP.objects.get(email=email, otp=otp, is_verified=True)
    except EmailOTP.DoesNotExist:
        return Response({"error": "Invalid or unverified OTP"}, status=400)

    # 2️⃣ Get user
    try:
        user = AppUser.objects.get(email=email)
    except AppUser.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

    # 3️⃣ Reset password
    user.password = make_password(new_password)
    user.save()

    # 4️⃣ Invalidate OTP
    otp_obj.delete()

    return Response({"message": "Password reset successful"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    old_password = request.data.get("old_password")
    new_password = request.data.get("new_password")

    if not old_password or not new_password:
        return Response({"error": "Both old and new password are required"}, status=400)

    user = request.user

    # Verify old password using Django's hashed-password check
    if not check_password(old_password, user.password):
        return Response({"error": "Old password is incorrect"}, status=400)

    if len(new_password) < 6:
        return Response(
            {"error": "New password must be at least 6 characters"}, status=400
        )

    # Save new hashed password
    user.password = make_password(new_password)
    user.save()

    return Response({"message": "Password changed successfully"})


class TurfListView(ListAPIView):
    queryset = Turf.objects.all()
    serializer_class = TurfSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context


# -------------------Admin Views ---------------------------#

from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model


@api_view(["POST"])
def admin_login(request):
    password = request.data.get("password")
    email = request.data.get("email")
    phone = request.data.get("phone")

    User = get_user_model()
    user = None

    # 1. Try AppUser first (canonical model)
    try:
        if email:
            user = User.objects.get(email=email)
        elif phone:
            user = User.objects.get(mobile=phone)

        if user and user.check_password(password):
            # Success! AppUser exists and password matches
            pass
        else:
            user = None
    except User.DoesNotExist:
        user = None

    # 2. Fallback to AdminUser if AppUser failed or doesn't exist yet
    if not user:
        try:
            if email:
                admin = AdminUser.objects.get(email=email)
            elif phone:
                admin = AdminUser.objects.get(phone=phone)
            else:
                return Response({"error": "Email or phone required"}, status=400)

            if not check_password(password, admin.password):
                return Response({"error": "Invalid credentials"}, status=400)

            # Sync AdminUser to AppUser if missing
            user, created = User.objects.get_or_create(
                email=admin.email,
                defaults={
                    "name": admin.name,
                    "mobile": admin.phone,
                    "role": "ADMIN",
                    "is_staff": True,
                    "is_superuser": True,
                    "is_verified": True,
                },
            )
            if created:
                user.set_password(password)
                user.save()
        except AdminUser.DoesNotExist:
            return Response({"error": "Invalid credentials"}, status=400)

    # 3. Final Role and Activation Check
    if not user.role:
        user.role = "ADMIN"
        user.is_staff = True
        user.save()

    refresh = RefreshToken.for_user(user)

    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "role": user.role,
            "name": user.name,
            "message": "Admin login successful",
        }
    )


# -------------------- USER ISSUE SUBMISSION (Public) --------------------
@api_view(["POST"])
@permission_classes([AllowAny])
def submit_issue(request):
    """Users submit support issues - notifies all admins via WhatsApp"""
    serializer = UserIssueSerializer(data=request.data)
    if serializer.is_valid():
        issue = serializer.save()

        # Notify ALL active admins via WhatsApp
        admins = AdminUser.objects.filter(is_active=True)
        for admin in admins:
            message = f"""
NEW USER ISSUE RECEIVED

Title: {issue.title}
User: {issue.name} ({issue.phone})
Email: {issue.email}
Details: {issue.description[:200]}...

Issue ID: {issue.id}
View: /admin/issues/
"""
            # send_whatsapp(admin.phone, message)

        return Response(
            {
                "success": True,
                "message": "Issue submitted & admin notified!",
                "issue_id": issue.id,
            }
        )
    return Response(serializer.errors, status=400)


# -------------------- ADMIN ISSUE MANAGEMENT --------------------
@api_view(["GET"])
@staff_member_required
def admin_issues_list(request):
    """Admin list all user issues"""
    issues = UserIssue.objects.select_related("user").order_by("-created_at")
    serializer = UserIssueSerializer(issues, many=True)
    return Response({"issues": serializer.data})


@api_view(["PATCH"])
@staff_member_required
def admin_resolve_issue(request, issue_id):
    """Admin mark issue as resolved"""
    try:
        issue = UserIssue.objects.get(id=issue_id)
        issue.status = "RESOLVED"
        issue.resolved_at = timezone.now()
        issue.save()
        return Response({"success": True, "message": "Issue marked as resolved"})
    except UserIssue.DoesNotExist:
        return Response({"error": "Issue not found"}, status=404)


@api_view(["GET"])
@permission_classes([AllowAny])
def admin_dashboard_main(request):
    try:
        from core.models import Turf, Booking, Payment, Vendor
        from django.contrib.auth import get_user_model
        from django.db.models.functions import TruncDate
        from django.db.models import Count, Sum
        from django.utils import timezone

        User = get_user_model()

        total_users = User.objects.count()
        total_vendors = Vendor.objects.count()
        total_turfs = Turf.objects.count()
        total_bookings = Booking.objects.count()

        today = timezone.localdate()
        start = today - timezone.timedelta(days=6)

        today_bookings = Booking.objects.filter(created_at__date=today).count()

        today_new_users = 0
        if hasattr(User, "date_joined"):
            today_new_users = User.objects.filter(date_joined__date=today).count()
        elif hasattr(User, "created_at"):
            today_new_users = User.objects.filter(created_at__date=today).count()

        today_new_vendors = (
            Vendor.objects.filter(created_at__date=today).count()
            if hasattr(Vendor, "created_at")
            else 0
        )

        today_revenue_paise = (
            Payment.objects.filter(status="SUCCESS", created_at__date=today).aggregate(
                s=Sum("amount")
            )["s"]
            or 0
        )

        days = [start + timezone.timedelta(days=i) for i in range(7)]

        booking_counts_qs = (
            Booking.objects.filter(
                created_at__date__gte=start, created_at__date__lte=today
            )
            .annotate(d=TruncDate("created_at"))
            .values("d")
            .annotate(c=Count("id"))
        )
        booking_counts = {row["d"]: row["c"] for row in booking_counts_qs}

        revenue_qs = (
            Payment.objects.filter(
                status="SUCCESS",
                created_at__date__gte=start,
                created_at__date__lte=today,
            )
            .annotate(d=TruncDate("created_at"))
            .values("d")
            .annotate(s=Sum("amount"))
        )
        revenue = {row["d"]: row["s"] for row in revenue_qs}

        weekly_data = []
        for d in days:
            weekly_data.append(
                {
                    "day": d.strftime("%a"),
                    "bookings": int(booking_counts.get(d, 0) or 0),
                    "revenue": int(revenue.get(d, 0) or 0) / 100,
                }
            )

        payload = {
            "success": True,
            "stats": {
                "users": total_users,
                "vendors": total_vendors,
                "turfs": total_turfs,
                "bookings": total_bookings,
            },
            "today": {
                "bookings": today_bookings,
                "revenue": float(today_revenue_paise / 100),
                "users": today_new_users,
                "vendors": today_new_vendors,
            },
            "weekly": weekly_data,
        }
        return Response(payload)
    except Exception as e:
        import traceback

        return Response(
            {"success": False, "error": str(e), "traceback": traceback.format_exc()}
        )


@staff_member_required
def dashboard_weekly(request):
    """Returns last 7 days booking counts and revenue totals for chart."""
    today = timezone.localdate()
    start = today - timezone.timedelta(days=6)
    days = [start + timezone.timedelta(days=i) for i in range(7)]

    booking_counts = {
        row["d"]: row["c"]
        for row in Booking.objects.filter(
            created_at__date__gte=start, created_at__date__lte=today
        )
        .extra(select={"d": "date(created_at)"})
        .values("d")
        .annotate(c=Count("id"))
    }

    revenue = {
        row["d"]: row["s"]
        for row in Payment.objects.filter(
            status="SUCCESS", created_at__date__gte=start, created_at__date__lte=today
        )
        .extra(select={"d": "date(created_at)"})
        .values("d")
        .annotate(s=Sum("amount"))
    }

    payload = {
        "labels": [d.strftime("%a") for d in days],
        "bookings": [int(booking_counts.get(d, 0)) for d in days],
        "revenue_paise": [int(revenue.get(d, 0) or 0) for d in days],
    }
    return JsonResponse(payload)


@staff_member_required
def users_list(request):
    qs = User.objects.all().order_by("-date_joined")
    data = [
        {
            "id": u.id,
            "username": u.username,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "email": u.email,
            "is_active": u.is_active,
            "date_joined": u.date_joined,
        }
        for u in qs
    ]
    return JsonResponse({"results": data})


@staff_member_required
def user_toggle_active(request, user_id: int):
    if request.method not in ("POST", "PATCH"):
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    try:
        u = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"detail": "User not found"}, status=404)
    u.is_active = not u.is_active
    u.save(update_fields=["is_active"])
    return JsonResponse({"id": u.id, "is_active": u.is_active})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def turfs_list(request):
    date_str = request.GET.get("date")

    # Filter: only show turfs from APPROVED vendors (or no vendor)
    qs = (
        Turf.objects.select_related("owner", "vendor")
        .prefetch_related("banners", "gallery", "slot_items", "game_items")
        .filter(is_approved=True, retire=0)
        .exclude(
            vendor__status="Inactive"  # Exclude turfs from inactive vendors
        )
        .order_by("-id")
    )

    data = []
    for t in qs:
        available_slots = []

        # NEW SLOTS ✅
        if hasattr(t, "slot_items") and t.slot_items.exists():
            slots_qs = t.slot_items.filter(is_available=True)

            # Date filter (if date field added later)
            if date_str:
                # slots_qs = slots_qs.filter(date=date_str)  # Add date field to Slot
                pass

            for slot in slots_qs:
                available_slots.append(
                    {
                        "id": slot.id,
                        "start_time": slot.start_time.strftime("%H:%M"),
                        "end_time": slot.end_time.strftime("%H:%M"),
                        "time_display": f"{slot.start_time.strftime('%I:%M %p')} - {slot.end_time.strftime('%I:%M %p')}",
                        "price_display": f"₹{slot.price}",
                        "price": slot.price,
                        "is_available": slot.is_available,
                    }
                )
        else:
            # Legacy JSON fallback
            for slot in t.slots or []:
                if not slot.get("is_booked", False):
                    available_slots.append(
                        {
                            "id": slot.get("id"),
                            "start_time": slot.get("start_time", ""),
                            "end_time": slot.get("end_time", ""),
                            "time_display": slot.get("slot_display", ""),
                            "price": slot.get("price", t.price_per_hour),
                            "price_display": f"₹{slot.get('price', t.price_per_hour)}",
                            "is_available": True,
                        }
                    )

        data.append(
            {
                "id": t.id,
                "name": t.name,
                "location": t.location,
                "latitude": t.latitude,
                "longitude": t.longitude,
                "price_per_hour": t.price_per_hour,
                "description": t.description or "",
                "games": [g.game_name for g in t.game_items.all()],
                "amenities": t.amenities or [],
                "features": t.features or [],
                "banner_images": [img.image.url for img in t.banners.all()],
                "gallery_images": [img.image.url for img in t.gallery.all()],
                "slots": available_slots,
                "vendor_code": getattr(t.vendor, "vendor_id", None)
                if t.vendor
                else None,
                # ✅ Dynamic slots ready
                # ✅ SAFE VENDOR ACCESS
                "vendor": {
                    "vendor_id": getattr(t.vendor, "vendor_id", None)
                    if t.vendor
                    else None,
                    "venuename": getattr(t.vendor, "venuename", None)
                    if t.vendor
                    else None,
                },
                # ✅ SAFE OWNER ACCESS
                "owner": {
                    "id": t.owner.id if t.owner else None,
                    "username": t.owner.name if t.owner else None,
                    "email": t.owner.email if t.owner else None,
                }
                if t.owner
                else {"id": None, "username": None, "email": None},
                "is_approved": t.is_approved,
            }
        )

    return Response({"results": data})


@api_view(["GET"])
def turf_detail(request, turf_id):
    """Single turf with all slots"""
    try:
        turf = Turf.objects.get(id=turf_id, is_approved=True)
        slots = Slot.objects.filter(turf=turf).order_by("start_time")

        return Response(
            {
                "id": turf.id,
                "name": turf.name,
                "location": turf.location,
                "price_per_hour": turf.price_per_hour,
                "description": turf.description,
                "games": [
                    {"id": g.id, "game_name": g.game_name, "price": g.price}
                    for g in turf.game_set.all()
                ],
                "amenities": turf.amenities,
                "features": turf.features,
                "slots": SlotSerializer(slots, many=True).data,
                "banners": [banner.image.url for banner in turf.banners.all()],
                "gallery": [img.image.url for img in turf.gallery.all()],
            }
        )
    except Turf.DoesNotExist:
        return Response({"error": "Turf not found"}, status=404)


from django.http import JsonResponse


def bookings_list(request):
    qs = (
        Booking.objects.select_related("user", "turf", "game")
        .prefetch_related("slots")
        .order_by("-created_at")
    )

    data = []

    for b in qs:
        # ✅ Get slot times
        slot_list = []
        for s in b.slots.all():
            slot_list.append({"start_time": s.start_time, "end_time": s.end_time})

        data.append(
            {
                "id": b.id,
                "player_name": b.user_name or (b.user.name if b.user else "-") or "-",
                "status": b.status,
                "created_at": b.created_at,
                "user": {
                    "id": b.user.id if b.user else None,
                    "username": b.user_name if b.user_name else (b.user.name if b.user else "-"),
                    "name": b.user_name if b.user_name else (b.user.name if b.user else "-"),
                    "email": b.user_email if b.user_email else (b.user.email if b.user else "-"),
                    "mobile": b.user_mobile if b.user_mobile else (b.user.mobile if b.user else "-"),
                },
                "turf": {
                    "id": b.turf.id,
                    "name": b.turf.name,
                },
                "game": {
                    "id": b.game.id,
                    "name": b.game.game_name,
                },
                "date": b.date,
                "amount": b.total_payable,
                # ✅ ADD SLOT DATA
                "slots": slot_list,
            }
        )

    return JsonResponse({"results": data})


@staff_member_required
def booking_cancel(request, booking_id: int):
    if request.method not in ("POST", "PATCH"):
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    try:
        b = Booking.objects.get(id=booking_id)
    except Booking.DoesNotExist:
        return JsonResponse({"detail": "Booking not found"}, status=404)
    b.status = "CANCELLED"
    b.save(update_fields=["status"])
    return JsonResponse({"id": b.id, "status": b.status})


@staff_member_required
def payments_list(request):
    qs = Payment.objects.select_related("user", "booking").order_by("-created_at")
    data = [
        {
            "id": p.id,
            "booking_id": p.booking_id,
            "user": {
                "id": p.user.id,
                "username": p.user.username,
                "email": p.user.email,
            },
            "razorpay_order_id": p.razorpay_order_id,
            "razorpay_payment_id": p.razorpay_payment_id,
            "amount": p.amount,
            "status": p.status,
            "created_at": p.created_at,
        }
        for p in qs
    ]
    return JsonResponse({"results": data})


# --- Vendor endpoints (stub) ---
# Your backend doesn't include a Vendor model yet.
# These endpoints exist so your Admin React flow won't break.


@staff_member_required
def vendors_list(request):
    return JsonResponse({"results": []})


@api_view(["PUT"])
def vendor_approve(request, id):
    try:
        vendor = Vendor.objects.get(id=id)

        # 1. Use existing password or generate a new one if missing
        random_password = vendor.vendor_password or secrets.token_urlsafe(8)

        # 2. Update Vendor Record
        vendor.status = "Approved"
        if not vendor.vendor_password:
            vendor.vendor_password = random_password
        vendor.save()

        # 3. Create Corresponding AppUser
        # Check if user already exists to avoid unique constraint errors
        if not AppUser.objects.filter(email=vendor.email).exists():
            AppUser.objects.create_user(
                email=vendor.email,
                password=random_password,
                name=vendor.ownername,
                mobile=vendor.phone,
                role="VENDOR",
                is_verified=True,
                last_login=timezone.now(),
            )
        else:
            # If user exists, ensure they have the vendor role and update password if needed
            user = AppUser.objects.get(email=vendor.email)
            # Re-set password only if we generated a new one or want to ensure it matches Vendor record
            user.set_password(random_password)
            user.role = "VENDOR"
            user.is_verified = True
            user.last_login = timezone.now()
            user.save()

        # ✅ Send approval email to vendor with the password
        if vendor.email:
            send_vendor_approval_email(vendor.email, vendor, random_password)

        return Response({"message": "Vendor Approved and User Account Created"})
    except Vendor.DoesNotExist:
        return Response({"error": "Vendor not found"}, status=404)


@api_view(["PUT"])
def vendor_reject(request, id):
    try:
        vendor = Vendor.objects.get(id=id)

        # ✅ Send rejection email BEFORE deleting the record
        if vendor.email:
            send_vendor_rejection_email(vendor.email, vendor)

        vendor.delete()
        return Response({"message": "Vendor Rejected and Removed"})
    except Vendor.DoesNotExist:
        return Response({"error": "Vendor not found"}, status=404)


@staff_member_required
def turfs_approve(request, turf_id):
    if request.method not in ("POST", "PATCH"):
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    try:
        turf = Turf.objects.get(id=turf_id)
    except Turf.DoesNotExist:
        return JsonResponse({"detail": "Turf not found"}, status=404)

    turf.is_approved = True
    turf.save(update_fields=["is_approved"])

    return JsonResponse(
        {"id": turf.id, "is_approved": True, "message": "Turf approved"}
    )


@staff_member_required
def turfs_reject(request, turf_id):
    if request.method not in ("POST", "PATCH"):
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    try:
        turf = Turf.objects.get(id=turf_id)
    except Turf.DoesNotExist:
        return JsonResponse({"detail": "Turf not found"}, status=404)

    turf.is_approved = False
    turf.save(update_fields=["is_approved"])

    return JsonResponse(
        {"id": turf.id, "is_approved": False, "message": "Turf rejected"}
    )


# -----------------Vendor Views --------------------#

# --------- Helpers


def _ensure_vendor(user) -> bool:
    # Minimal vendor rule: must be authenticated. You can tighten this later.
    return user and user.is_authenticated


# --------- Vendor Dashboard


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vendor_dashboard(request):
    """Return stats for Vendor/Dashboard.jsx.

    Notes:
    - Your frontend currently uses dummy data; this endpoint gives real data
      based on turfs owned by the logged-in user.
    """

    if not _ensure_vendor(request.user):
        return Response({"detail": "Unauthorized"}, status=401)

    try:
        vendor = Vendor.objects.get(email=request.user.email)
        owned_turfs = Turf.objects.filter(vendor=vendor)
    except Vendor.DoesNotExist:
        owned_turfs = Turf.objects.filter(owner=request.user)

    turf_ids = list(owned_turfs.values_list("id", flat=True))

    # Bookings for owned turfs
    bookings_qs = Booking.objects.filter(turf_id__in=turf_ids)

    today = now().date()
    todays = bookings_qs.filter(date=today).count()
    upcoming = bookings_qs.filter(date__gt=today).count()

    # Earnings: sum successful payments for those bookings
    earnings = (
        Payment.objects.filter(booking__in=bookings_qs, status="SUCCESS")
        .aggregate(total=Sum("amount"))
        .get("total")
        or 0
    )

    pending_approvals = bookings_qs.filter(vendor_status__iexact="PENDING").count()

    data = {
        "stats": [
            {"title": "Total Turfs Owned", "value": owned_turfs.count(), "icon": "🏠"},
            {"title": "Today’s Bookings", "value": todays, "icon": "📅"},
            {"title": "Upcoming Bookings", "value": upcoming, "icon": "🗓️"},
            # amounts stored in paise; convert to rupees for display
            {
                "title": "Monthly Earnings",
                "value": round(earnings / 100, 2),
                "icon": "💲",
            },
            {"title": "Pending Approvals", "value": pending_approvals, "icon": "⏳"},
        ],
        # Keep these for UI compatibility (frontend shows these blocks)
        "coaches": [],
        "reviews": [],
    }

    return Response(data)


# --------- Turfs


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vendor_list_turfs(request):
    try:
        vendor = Vendor.objects.get(email=request.user.email)
        turfs = Turf.objects.filter(vendor=vendor, retire=0)
    except Vendor.DoesNotExist:
        turfs = Turf.objects.filter(owner=request.user, retire=0)
    return Response(TurfSerializer(turfs, many=True).data)


from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def vendor_add_turf(request):
    """Enhanced vendor turf creation with full features including images, games, slots"""
    ser = VendorTurfCreateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    payload = ser.validated_data

    turf_count = payload.get("turfCount") or 1

    # -------------------------
    # ✅ GET TURF NAME (support both name and turfName)
    # -------------------------
    turf_name = payload.get("turfName") or payload.get("name") or "Unnamed Turf"

    # -------------------------
    # ✅ GET VENDOR (if vendorId provided)
    # -------------------------
    vendor = None
    vendor_id = payload.get("vendorId")
    if vendor_id:
        try:
            vendor = Vendor.objects.get(vendor_id=vendor_id)
        except Vendor.DoesNotExist:
            pass

    # -------------------------
    # ✅ CREATE TURF (as per your requested format)
    # -------------------------
    turf = Turf.objects.create(
        name=turf_name,
        location=payload["location"],
        latitude=payload.get("latitude"),
        longitude=payload.get("longitude"),
        price_per_hour=payload["price"],
        description=payload.get("description", ""),
        amenities=payload.get("amenities", []),
        features=payload.get("features", []),
        vendor=vendor,
        vendor_code=vendor.vendor_id if vendor else None,
        owner=request.user,
        is_approved=True,
        role="vendor",
    )

    # -------------------------
    # ✅ CREATE GAMES
    # -------------------------
    games = payload.get("games", [])
    if isinstance(games, str):
        try:
            games = json.loads(games)
        except:
            games = []

    for game_name in games:
        Game.objects.create(turf=turf, game_name=game_name, price=turf.price_per_hour)

    # -------------------------
    # ✅ CREATE GROUNDS
    # -------------------------
    for i in range(1, turf_count + 1):
        Ground.objects.create(turf=turf, name=f"Ground {i}")

    # -------------------------
    # ✅ CREATE SLOTS
    # -------------------------
    slots = payload.get("slots", [])
    if isinstance(slots, str):
        try:
            slots = json.loads(slots)
        except:
            slots = []

    for s in slots:
        try:
            # ⭐ CONVERT STRING → TIME OBJECT
            start_time = datetime.strptime(s.get("from", ""), "%I:%M %p").time()
            end_time = datetime.strptime(s.get("to", ""), "%I:%M %p").time()

            Slot.objects.create(
                turf=turf,
                start_time=start_time,
                end_time=end_time,
                price=s.get("price", turf.price_per_hour),
                is_available=True,
            )
        except Exception as e:
            print(f"Slot creation error: {e}")
            continue

    # -------------------------
    # ✅ SAVE BANNERS (from request.FILES)
    # -------------------------
    for img in request.FILES.getlist("banner_images"):
        TurfBanner.objects.create(turf=turf, image=img)

    # -------------------------
    # ✅ SAVE GALLERY (from request.FILES)
    # -------------------------
    for img in request.FILES.getlist("gallery_images"):
        TurfGallery.objects.create(turf=turf, image=img)

    return Response(
        {"success": True, "turf_id": turf.id, "message": "Turf created successfully"}
    )


# -------------------------
# ✅ CALCULATE DISTANCE HELPER FUNCTION
# -------------------------
def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in kilometers using Haversine formula"""
    from math import radians, cos, sin, asin, sqrt

    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2

    c = 2 * asin(sqrt(a))

    r = 6371  # Radius of Earth in kilometers

    return c * r


# --------- Booking Management


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vendor_booking_list(request):
    """Return bookings belonging to vendor-owned turfs."""
    try:
        vendor = Vendor.objects.get(email=request.user.email)
        turfs = Turf.objects.filter(vendor=vendor)
    except Vendor.DoesNotExist:
        turfs = Turf.objects.filter(owner=request.user)

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

        payment_status = "Pending"
        try:
            if b.payment:
                payment_status = (
                    "Paid"
                    if b.payment.status == "SUCCESS"
                    else b.payment.status.capitalize()
                )
        except Exception:
            pass

        data.append(
            {
                "id": f"#BK{b.id}",
                "raw_id": b.id,
                "player_name": b.user_name or (b.user.name if b.user else "-") or "-",
                "player": b.user_name or (b.user.name if b.user else "-") or "-",
                "turf": b.turf.name if b.turf else "-",
                "game": b.game.game_name if hasattr(b, "game") and b.game else "-",
                "date": b.date.strftime("%d-%m-%Y") if b.date else "-",
                "time": time_str,
                "payment": payment_status,
                "refund": "Refunded" if b.status == "REFUNDED" else "-",
                "status": b.status.capitalize() if b.status else "Pending",
            }
        )

    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def vendor_update_booking_status(request):
    """Used by Vendor/BookingManagement.jsx (placeholder).

    Accepts:
      { bookingId: "#BK101" or 123, status: "Approved"|"Rejected"|"Cancelled" }
    We map this to Booking.vendor_status and optionally Booking.status.
    """
    booking_id = request.data.get("bookingId")
    status_text = (request.data.get("status") or "").strip()

    if not booking_id or not status_text:
        return Response(
            {"success": False, "error": "bookingId and status required"}, status=400
        )

    # bookingId may come as "#BK101" in UI dummy; try to parse digits
    if isinstance(booking_id, str) and booking_id.startswith("#"):
        digits = "".join([c for c in booking_id if c.isdigit()])
        booking_id = int(digits) if digits else None

    try:
        booking = Booking.objects.select_related("cart", "cart__turf").get(
            id=booking_id
        )
    except Exception:
        return Response({"success": False, "error": "Booking not found"}, status=404)

    # Ensure booking belongs to vendor
    if booking.cart.turf.owner_id != request.user.id:
        return Response({"success": False, "error": "Forbidden"}, status=403)

    normalized = status_text.upper()
    if normalized == "APPROVED":
        booking.vendor_status = "APPROVED"
        booking.status = "CONFIRMED"
    elif normalized == "REJECTED":
        booking.vendor_status = "REJECTED"
        booking.status = "CANCELLED"
    elif normalized == "CANCELLED":
        booking.vendor_status = "CANCELLED"
        booking.status = "CANCELLED"
    else:
        booking.vendor_status = status_text

    booking.save(update_fields=["vendor_status", "status"])
    return Response({"success": True})


# --------- Schedule Time (Slots)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vendor_list_slots(request):
    """List slots for a ground (and vendor must own the turf)."""
    ground_id = request.query_params.get("ground_id")
    if not ground_id:
        return Response({"error": "ground_id required"}, status=400)

    try:
        ground = Ground.objects.select_related("turf").get(id=ground_id)
    except Ground.DoesNotExist:
        return Response({"error": "Ground not found"}, status=404)

    if ground.turf.owner_id != request.user.id:
        return Response({"error": "Forbidden"}, status=403)

    slots = Slot.objects.filter(ground=ground).order_by("start_time")
    return Response(
        [
            {
                "id": s.id,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "is_booked": s.is_booked,
            }
            for s in slots
        ]
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def vendor_create_slots(request):
    """Create slots for a ground.

    Expected payload:
      { ground_id: 1, slots: [{start_time: "06:00", end_time: "07:00"}, ...] }
    """
    ground_id = request.data.get("ground_id")
    slots = request.data.get("slots") or []

    if not ground_id or not isinstance(slots, list) or not slots:
        return Response(
            {"success": False, "error": "ground_id and slots[] required"}, status=400
        )

    try:
        ground = Ground.objects.select_related("turf").get(id=ground_id)
    except Ground.DoesNotExist:
        return Response({"success": False, "error": "Ground not found"}, status=404)

    if ground.turf.owner_id != request.user.id:
        return Response({"success": False, "error": "Forbidden"}, status=403)

    created = 0
    for item in slots:
        st = item.get("start_time")
        et = item.get("end_time")
        if not st or not et:
            continue
        Slot.objects.create(ground=ground, start_time=st, end_time=et)
        created += 1

    return Response({"success": True, "created": created})


# --------- Discount (placeholder – no Discount model in backend yet)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vendor_list_discounts(request):
    """Placeholder: frontend has DiscountPage but backend has no Discount model.

    Returns empty list for now.
    """
    return Response([])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def vendor_create_discount(request):
    """Placeholder endpoint so frontend can submit Deal Request."""
    return Response({"success": True})


# ----------------adminlaa vendor add panna vendiya model-----------------
from rest_framework.decorators import api_view
from rest_framework.response import Response
# pyrefly: ignore [missing-import]
from .models import TurfBanner, TurfGallery, Vendor
from datetime import datetime
import requests
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
# pyrefly: ignore [missing-import]
from .models import Vendor


# # ---------------- WHATSAPP FUNCTION ----------------
# def send_whatsapp(phone, message):
#     print("WHATSAPP FUNCTION CALLED")
#     url = "https://api.goinfinity.ai/api/v1/whatsapp/send"

#     headers = {
#         "Authorization": f"Bearer {settings.GOINFINITY_TOKEN}",
#         "Content-Type": "application/json"
#     }

#     payload = {
#         "phone": phone,
#         "message": message
#     }

#     try:
#         response = requests.post(url, json=payload, headers=headers)
#         print("WhatsApp Response:", response.text)
#     except Exception as e:
#         print("WhatsApp Error:", str(e))

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
# pyrefly: ignore [missing-import]
from .models import Vendor
# pyrefly: ignore [missing-import]
from .utils.whatsapp import send_whatsapp_message


@csrf_exempt
def vendor_create(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            # ✅ Create Vendor
            vendor = Vendor.objects.create(
                venuename=data["venuename"],
                ownername=data["ownername"],
                email=data["email"],
                phone=data["phone"],
                location=data["location"],
                address=data["address"],
                pincode=data["pincode"],
                totalturf=data["totalturf"],
                availablegames=data["availablegames"],
                status="Pending",
            )

            print("✅ Vendor Created:", vendor.vendor_id)

            # ✅ Send WhatsApp
            whatsapp_result = send_whatsapp_message(
                phone=vendor.phone, vendor_id=vendor.vendor_id, location=vendor.location
            )

            print("📲 WhatsApp Result:", whatsapp_result)

            # ✅ Send Email to Admin (Myadugalam)
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                subject = f"New Partner Registration: {vendor.venuename}"
                message = (
                    f"A new partner has registered on Adugalam.\n\n"
                    f"Venue Name: {vendor.venuename}\n"
                    f"Owner Name: {vendor.ownername}\n"
                    f"Phone: {vendor.phone}\n"
                    f"Email: {vendor.email}\n"
                    f"Location: {vendor.location}\n"
                    f"Address: {vendor.address}\n\n"
                    f"Please check the admin dashboard to review and approve."
                )
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    ["Myadugalam@gmail.com"],
                    fail_silently=True,
                )
                print("✅ Email sent to Myadugalam@gmail.com")
            except Exception as e:
                print("❌ Email sending failed:", e)

            return JsonResponse(
                {
                    "vendor_id": vendor.vendor_id,
                    "message": "Vendor created successfully",
                    "whatsapp": whatsapp_result,
                }
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


# ------------add turf page laa vendor id kuduta name varnu------------------------------
@api_view(["GET"])
def get_vendor(request, vendor_id):
    try:
        vendor = Vendor.objects.get(vendor_id=vendor_id)

        return Response(
            {
                "id": vendor.id,
                "vendor_id": vendor.vendor_id,
                "venuename": vendor.venuename,
                "ownername": vendor.ownername,
                "phone": vendor.phone,
                "email": vendor.email,
                "location": vendor.location,
                "address": vendor.address,
                "pincode": vendor.pincode,
                "totalturf": vendor.totalturf,
                "availablegames": vendor.availablegames,
                "status": vendor.status,
            }
        )

    except Vendor.DoesNotExist:
        return Response({"error": "Vendor not found"}, status=404)


# ------------- vendor list------------------


@api_view(["GET"])
def vendor_list(request):

    vendors = Vendor.objects.filter(status__in=["Approved", "Inactive"]).order_by(
        "-created_at"
    )

    data = []
    for v in vendors:
        data.append(
            {
                "id": v.id,
                "vendor_id": v.vendor_id,
                "venuename": v.venuename,
                "ownername": v.ownername,
                "email": v.email,
                "phone": v.phone,
                "location": v.location,
                "totalturf": v.totalturf,
                "status": v.status,
            }
        )

    return Response(data)


@api_view(["GET"])
def vendor_requests(request):

    vendors = Vendor.objects.all().order_by("-created_at")

    data = []
    for v in vendors:
        data.append(
            {
                "id": v.id,
                "vendor_id": v.vendor_id,
                "venuename": v.venuename,
                "ownername": v.ownername,
                "email": v.email,
                "phone": v.phone,
                "location": v.location,
                "totalturf": v.totalturf,
                "status": v.status,
            }
        )

    return Response(data)


@api_view(["DELETE"])
def delete_vendor(request, id):
    try:
        vendor = Vendor.objects.get(vendor_id=id)
        vendor.delete()
        return Response({"message": "Deleted"})
    except Vendor.DoesNotExist:
        return Response({"error": "Not found"}, status=404)

@api_view(["PUT"])
def vendor_status_toggle(request, vendor_id):
    try:
        vendor = Vendor.objects.get(vendor_id=vendor_id)
        new_status = request.data.get("status")
        vendor.status = new_status
        vendor.save()

        # Also update all related turfs based on vendor status
        if new_status == "Approved":
            Turf.objects.filter(vendor=vendor).update(is_approved=True)
            send_whatsapp_message(
                phone=vendor.phone, vendor_id=vendor.vendor_id, location=vendor.location, status="Approved"
            )
        elif new_status in ["Inactive", "Rejected"]:
            Turf.objects.filter(vendor=vendor).update(is_approved=False)
            send_whatsapp_message(
                phone=vendor.phone, vendor_id=vendor.vendor_id, location=vendor.location, status="Rejected"
            )

        return Response({"message": "Status updated", "status": vendor.status})
    except Vendor.DoesNotExist:
        return Response({"error": "Vendor not found"}, status=404)


@api_view(["PUT"])
def update_vendor_by_code(request, vendor_id):
    """Update vendor details by vendor_id"""
    try:
        vendor = Vendor.objects.get(vendor_id=vendor_id)

        # Update fields if provided
        if request.data.get("venuename"):
            vendor.venuename = request.data.get("venuename")
        if request.data.get("ownername"):
            vendor.ownername = request.data.get("ownername")
        if request.data.get("phone"):
            vendor.phone = request.data.get("phone")
        if request.data.get("email"):
            vendor.email = request.data.get("email")
        if request.data.get("location"):
            vendor.location = request.data.get("location")
        if request.data.get("address"):
            vendor.address = request.data.get("address")
        if request.data.get("pincode"):
            vendor.pincode = request.data.get("pincode")
        if request.data.get("totalturf"):
            vendor.totalturf = request.data.get("totalturf")

        vendor.save()

        return Response(
            {"message": "Vendor updated successfully", "vendor_id": vendor.vendor_id}
        )
    except Vendor.DoesNotExist:
        return Response({"error": "Vendor not found"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=400)


# ------------------Admin Adding Turf through vendor id---------------------#
from datetime import datetime
import json
from rest_framework.parsers import MultiPartParser, FormParser


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def admin_add_turf(request):

    ser = AdminTurfCreateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    data = ser.validated_data

    # -------------------------
    # ✅ GET VENDOR
    # -------------------------
    vendor = Vendor.objects.get(vendor_id=data["vendorId"])

    # -------------------------
    # ✅ CREATE TURF
    # -------------------------
    turf = Turf.objects.create(
        name=data["name"],
        location=data["location"],
        latitude=data.get("latitude") or None,
        longitude=data.get("longitude") or None,
        price_per_hour=data["price"],
        description=data.get("description", ""),
        amenities=data.get("amenities", []),
        features=data.get("features", []),
        vendor=vendor,
        vendor_code=vendor.vendor_id,
        owner=request.user,
        is_approved=True,
        role="admin",
    )

    # -------------------------
    # ✅ CREATE GAMES (FIXED FOR YOUR FRONTEND)
    # -------------------------
    games = data.get("games", [])

    if isinstance(games, str):
        games = json.loads(games)

    for game_name in games:
        Game.objects.create(
            turf=turf,
            game_name=game_name,
            price=turf.price_per_hour,  # use turf price
        )

    # -------------------------
    # ✅ CREATE SLOT ROWS (FIXED)
    # -------------------------
    slots = data.get("slots", [])

    # FormData sends string
    if isinstance(slots, str):
        slots = json.loads(slots)

    for s in slots:
        # ⭐ CONVERT STRING → TIME OBJECT
        start_time = datetime.strptime(s["from"], "%I:%M %p").time()

        end_time = datetime.strptime(s["to"], "%I:%M %p").time()

        Slot.objects.create(
            turf=turf,
            start_time=start_time,
            end_time=end_time,
            price=s.get("price") or turf.price_per_hour, # ⭐ Inherit turf price if slot price is 0/missing
            is_available=True,
        )

    # -------------------------
    # ✅ SAVE BANNERS
    # -------------------------
    for img in request.FILES.getlist("banner_images"):
        TurfBanner.objects.create(turf=turf, image=img)

    # -------------------------
    # ✅ SAVE GALLERY
    # -------------------------
    for img in request.FILES.getlist("gallery_images"):
        TurfGallery.objects.create(turf=turf, image=img)
    #         send_whatsapp(
    #     vendor.phone,
    #     f"""
    # New Turf Added Successfully

    # Turf Name: {turf.name}
    # Location: {turf.location}
    # """
    # )

    return Response({"success": True, "turf_id": turf.id}, status=201)


@api_view(["PATCH"])
def update_turf_priority(request, turf_id):

    try:
        turf = Turf.objects.get(id=turf_id)
    except Turf.DoesNotExist:
        return Response({"error": "Turf not found"}, status=404)

    turf.is_popular = request.data.get("is_popular", turf.is_popular)
    turf.priority = request.data.get("priority", turf.priority)

    turf.save()

    return Response({"message": "Priority updated"})


@api_view(["GET", "PATCH", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def admin_edit_turf(request, turf_id):
    try:
        turf = Turf.objects.get(id=turf_id)
    except Turf.DoesNotExist:
        return Response({"error": "Turf not found"}, status=404)
        
    if request.method == "DELETE":
        turf.delete()
        return Response({"success": True, "message": "Turf deleted successfully"})
        
    if request.method == "GET":
        data = {
            "id": turf.id,
            "name": turf.name,
            "location": turf.location,
            "latitude": turf.latitude,
            "longitude": turf.longitude,
            "price_per_hour": turf.price_per_hour,
            "is_popular": turf.is_popular,
            "priority": turf.priority,
            "vendor_code": turf.vendor_code
            or (turf.vendor.vendor_id if turf.vendor else ""),
            "games": [g.game_name for g in turf.game_items.all()],
            "banner_images": [img.image.url for img in turf.banners.all()],
            "gallery_images": [img.image.url for img in turf.gallery.all()],
        }
        return Response(data)
    if request.method in ["PATCH", "PUT"]:
        turf.name = request.data.get("name", turf.name)
        turf.location = request.data.get("location", turf.location)

        if "latitude" in request.data:
            lat = request.data.get("latitude")
            turf.latitude = float(lat) if lat else None

        if "longitude" in request.data:
            lng = request.data.get("longitude")
            turf.longitude = float(lng) if lng else None
        if "price_per_hour" in request.data:
            new_price = int(request.data.get("price_per_hour"))
            turf.price_per_hour = new_price
            
            # 🔥 SYNC: Update associated slots and existing games to match the new price
            Slot.objects.filter(turf=turf).update(price=new_price)
            Game.objects.filter(turf=turf).update(price=new_price)

        is_popular = request.data.get("is_popular")
        if is_popular is not None:
            turf.is_popular = str(is_popular).lower() == "true"
        if "priority" in request.data:
            turf.priority = request.data.get("priority", turf.priority)

        turf.save()
        games_raw = request.data.get("games")
        if games_raw is not None:
            if isinstance(games_raw, str):
                try:
                    games_list = json.loads(games_raw)
                except json.JSONDecodeError:
                    games_list = [g.strip() for g in games_raw.split(",") if g.strip()]
            else:
                games_list = games_raw

            turf.games = games_list
            turf.save()  # Save the games JSON field

            # Update the related game_items table
            turf.game_items.all().delete()
            for game_name in games_list:
                Game.objects.create(
                    turf=turf, game_name=game_name, price=turf.price_per_hour
                )
        new_banners = request.FILES.getlist("banner_images")
        if new_banners:
            turf.banners.all().delete()
            for img in new_banners:
                TurfBanner.objects.create(turf=turf, image=img)
        new_gallery = request.FILES.getlist("gallery_images")
        if new_gallery:
            turf.gallery.all().delete()
            for img in new_gallery:
                TurfGallery.objects.create(turf=turf, image=img)
        return Response({"success": True, "message": "Turf updated successfully"})


@api_view(["POST"])
def book_slot(request):

    turf = Turf.objects.get(id=request.data["turf_id"])
    slot_id = request.data["slot_id"]

    slots = turf.slots

    for slot in slots:
        if slot["id"] == slot_id:
            if slot["is_booked"]:
                return Response({"error": "Already booked"}, status=400)

            slot["is_booked"] = True

    turf.slots = slots
    turf.save()

    return Response({"success": True})


from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime
from .models import Slot


@api_view(["GET"])
def turf_slots(request):

    turf_id = request.query_params.get("turf_id")
    date_str = request.query_params.get("date")

    if not turf_id:
        return Response({"error": "turf_id required"}, status=400)

    # Get ALL slots for this turf
    slots = Slot.objects.filter(turf_id=turf_id)

    selected_date = None
    booked_slot_ids = set()

    # ✅ DATE FILTER & BOOKING CHECK
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date"}, status=400)

        # 🚀 Find booked slots for this specific date
        bookings = Booking.objects.filter(
            turf_id=turf_id, date=selected_date, status__in=["CONFIRMED"]
        ).prefetch_related("slots")

        for booking in bookings:
            for s in booking.slots.all():
                booked_slot_ids.add(s.id)

    # ✅ HIDE PAST TIME
    today = timezone.localdate()

    if selected_date and selected_date == today:
        now_time = timezone.localtime().time()
        slots = slots.filter(start_time__gt=now_time)

    slots = slots.order_by("start_time")

    data = []

    # Fetch turf to get base price fallback if needed
    turf = Turf.objects.filter(id=turf_id).first()
    base_price = turf.price_per_hour if turf else 0

    for s in slots:
        # ⭐ Fallback to turf's base price if individual slot price is 0
        price = s.price if s.price > 0 else base_price

        # ⭐ PEAK PRICE CHECK
        if selected_date:
            peak = PeakHour.objects.filter(
                turf_id=turf_id, slot=s, date=selected_date
            ).first()

            if peak:
                price = peak.peak_price

        # ⭐ AVAILABILITY CHECK (Check global flag AND date-specific bookings)
        is_avail = s.is_available and (s.id not in booked_slot_ids)

        data.append(
            {
                "id": s.id,
                "start_time": s.start_time.strftime("%H:%M:%S"),
                "end_time": s.end_time.strftime("%H:%M:%S"),
                "time_display": f"{s.start_time.strftime('%I:%M %p')} - {s.end_time.strftime('%I:%M %p')}",
                "price": price,
                "is_available": is_avail,
            }
        )

    # ✅ IMPORTANT RETURN
    return Response(data)


# -----------------------peak hours -----------------------#
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def vendor_set_peak_hour(request):

    turf_id = request.data.get("turf_id")
    game_id = request.data.get("game_id")
    slot_id = request.data.get("slot_id")
    date = request.data.get("date")
    peak_price = request.data.get("price")

    if not all([turf_id, game_id, slot_id, date, peak_price]):
        return Response({"error": "All fields required"}, status=400)

    try:
        try:
            vendor = Vendor.objects.get(email=request.user.email)
            turf = Turf.objects.get(id=turf_id, vendor=vendor)
        except Vendor.DoesNotExist:
            turf = Turf.objects.get(id=turf_id, owner=request.user)

        slot = Slot.objects.get(id=slot_id, turf=turf)
        game = Game.objects.get(id=game_id, turf=turf)
    except:
        return Response({"error": "Invalid turf/game/slot or you do not have permission"}, status=400)

    peak, created = PeakHour.objects.update_or_create(
        turf=turf,
        slot=slot,
        date=date,
        defaults={
            "game": game,
            "from_time": slot.start_time,
            "to_time": slot.end_time,
            "peak_price": peak_price,
        },
    )

    return Response(
        {"success": True, "message": "Peak hour price set", "peak_id": peak.id}
    )


# ------------------- delete peak hours --------------------------#
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def vendor_delete_peak_hour(request, peak_id):

    try:
        try:
            vendor = Vendor.objects.get(email=request.user.email)
            peak = PeakHour.objects.get(id=peak_id, turf__vendor=vendor)
        except Vendor.DoesNotExist:
            peak = PeakHour.objects.get(id=peak_id, turf__owner=request.user)
            
        peak.delete()
        return Response({"success": True})
    except PeakHour.DoesNotExist:
        return Response({"error": "Not found or you do not have permission"}, status=404)


# ----------------------location--------------------------------------------
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Location
from .serializers import HomepageBannerSerializer, LocationSerializer


# GET all locations
@api_view(["GET"])
def location_list(request):
    locations = Location.objects.all()
    serializer = LocationSerializer(locations, many=True)
    return Response(serializer.data)


# DEBUG ENDPOINT - Test if the endpoint is reachable
@api_view(["GET", "POST"])
def test_select_location(request):
    return Response({"status": "ok", "method": request.method, "data": request.data})


# SELECT LOCATION - Fixed with auto-creation and better matching
@api_view(["POST"])
def select_location(request):
    city_name = request.data.get("city")

    print(f"DEBUG: Received city_name = {city_name}")  # Add debug print

    if not city_name:
        return Response({"error": "City required"}, status=400)

    # Normalize city name - capitalize first letter
    city_normalized = city_name.strip().title()

    try:
        # Try exact match first (case-insensitive)
        location = Location.objects.get(name__iexact=city_name)
        print(f"DEBUG: Found exact location = {location.name}")  # Add debug print

        return Response({"location_id": location.id, "location_name": location.name})

    except Location.DoesNotExist:
        print(
            f"DEBUG: Exact location not found, trying partial match for city = {city_name}"
        )  # Add debug print

        # Try partial match - city name contains or is contained by
        try:
            location = Location.objects.filter(name__icontains=city_name).first()

            if location:
                print(
                    f"DEBUG: Found partial match location = {location.name}"
                )  # Add debug print
                return Response(
                    {"location_id": location.id, "location_name": location.name}
                )
        except Exception as e:
            print(f"DEBUG: Partial match error: {e}")  # Add debug print

        # Last resort: Auto-create the location if it doesn't exist
        # This ensures the app works even without seeded location data
        try:
            location = Location.objects.create(name=city_normalized)
            print(f"DEBUG: Auto-created location = {location.name}")  # Add debug print

            return Response(
                {"location_id": location.id, "location_name": location.name}
            )

        except Exception as e:
            print(f"DEBUG: Auto-create error: {e}")  # Add debug print
            return Response({"error": "Location not available"}, status=404)


# --------------------booking summary------------------------------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def booking_summary(request, booking_id):
    try:
        booking = Booking.objects.select_related("payment", "game", "turf").get(
            id=booking_id, user=request.user
        )

        return Response(
            {
                "booking_id": booking.id,
                "date": booking.date,
                "turf_name": booking.turf.name,
                "game_name": booking.game.game_name,
                "slots": [
                    {
                        "start_time": s.start_time.strftime("%I:%M %p"),
                        "end_time": s.end_time.strftime("%I:%M %p"),
                        "price": s.price,
                    }
                    for s in booking.slots.all()
                ],
                "original_amount": booking.original_amount,
                "advance_amount": booking.advance_amount,
                "service_charge": booking.service_charge,
                "total_price": booking.total_payable,  # ✅ FIXED
                "payment": {
                    "status": booking.payment.status
                    if hasattr(booking, "payment")
                    else "N/A",
                    "amount": booking.payment.amount
                    if hasattr(booking, "payment")
                    else 0,
                    "razorpay_payment_id": booking.payment.razorpay_payment_id
                    if hasattr(booking, "payment")
                    else None,
                },
            }
        )

    except Booking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=404)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_latest_booking(request):
    try:
        booking = (
            Booking.objects.filter(user=request.user, status="CONFIRMED")
            .select_related("payment", "game", "turf")
            .order_by("-id")
            .first()
        )

        if not booking:
            return Response({"error": "No booking found"}, status=404)

        banner = booking.turf.banners.first()
        turf_image = request.build_absolute_uri(banner.image.url) if banner and banner.image else None

        return Response(
            {
                "booking_id": booking.id,
                "date": booking.date,
                "turf_name": booking.turf.name,
                "turfimage": turf_image,
                "game_name": booking.game.game_name,
                "slots": [
                    {
                        "start_time": s.start_time.strftime("%I:%M %p"),
                        "end_time": s.end_time.strftime("%I:%M %p"),
                        "price": s.price,
                    }
                    for s in booking.slots.all()
                ],
                "original_amount": booking.original_amount,
                "advance_amount": booking.advance_amount,
                "service_charge": booking.service_charge,
                "total_price": booking.total_payable,  # ✅ FIXED
                "payment": {
                    "status": booking.payment.status
                    if hasattr(booking, "payment")
                    else "N/A",
                    "razorpay_payment_id": booking.payment.razorpay_payment_id
                    if hasattr(booking, "payment")
                    else None,
                },
            }
        )

    except Exception as e:
        print("Summary error:", str(e))
        return Response({"error": "Something went wrong"}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_all_bookings(request):
    try:
        print("Logged in user:", request.user)
        print("User ID:", request.user.id)

        bookings = (
            Booking.objects.filter(user=request.user)
            .select_related("game", "turf", "payment")
            .prefetch_related("slots", "turf__banners")
            .order_by("-id")
        )

        if not bookings.exists():
            return Response([], status=200)  # 🔥 return empty list (not 404)

        booking_data = []

        for booking in bookings:
            # Get related payment from select_related
            payment = getattr(booking, 'payment', None)

            booking_data.append(
                {
                    "booking_id": booking.id,
                    "date": booking.date,
                    "turf_name": booking.turf.name,
                    "turf_image": request.build_absolute_uri(booking.turf.banners.first().image.url) if booking.turf.banners.exists() else None,
                    "turf_location": getattr(booking.turf, 'location', ''),
                    "game_name": booking.game.game_name,
                    "slots": [
                        f"{slot.start_time.strftime('%I:%M %p')} - {slot.end_time.strftime('%I:%M %p')}"
                        for slot in booking.slots.all()
                    ],
                    "total_price": booking.total_payable,
                    "payment_status": payment.status if payment else "PENDING",
                }
            )

        return Response(booking_data)

    except Exception as e:
        print("Booking list error:", str(e))
        return Response({"error": "Something went wrong"}, status=500)


# ----------------------user profile update------------------------------------------------
@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def update_user_profile(request):
    """
    GET  → Return current user profile data
    PUT  → Update name, mobile, email.
           If email changes — new JWT tokens are issued so user stays logged in.
    """
    user = request.user

    # ---- GET: return profile ----
    if request.method == "GET":
        return Response(
            {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "mobile": user.mobile,
            }
        )

    # ---- PUT: update profile ----
    try:
        name = request.data.get("name", "").strip()
        mobile = request.data.get("mobile", "").strip()
        email = request.data.get("email", "").strip()

        email_changed = False

        if name:
            user.name = name

        if mobile:
            user.mobile = mobile

        # Email update — check uniqueness first
        if email and email != user.email:
            if AppUser.objects.filter(email=email).exclude(id=user.id).exists():
                return Response(
                    {"error": "This email is already in use by another account."},
                    status=400,
                )
            user.email = email
            email_changed = True

        user.save()

        # Issue fresh tokens if email changed (old token's subject is now stale)
        refresh = RefreshToken.for_user(user)
        new_access = str(refresh.access_token)
        new_refresh = str(refresh)

        return Response(
            {
                "success": True,
                "email_changed": email_changed,
                "access": new_access,
                "refresh": new_refresh,
                "user": {
                    "id": str(user.id),
                    "name": user.name,
                    "email": user.email,
                    "mobile": user.mobile,
                },
            }
        )

    except Exception as e:
        print("Profile update error:", str(e))
        return Response({"error": "Failed to update profile"}, status=500)


@staff_member_required
@csrf_exempt
def admin_create_vendor(request):
    if request.method == "POST":
        data = json.loads(request.body)

        vendor = Vendor.objects.create(
            venuename=data["venuename"],
            ownername=data["ownername"],
            email=data["email"],
            phone=data["phone"],
            location=data["location"],
            address=data["address"],
            pincode=data["pincode"],
            totalturf=data["totalturf"],
            availablegames=data["availablegames"],
            status="Approved",  # 🔥 auto approve
        )

        return JsonResponse({"vendor_id": vendor.vendor_id})


# ---------------------contact----------------------------
@api_view(["POST"])
@permission_classes([AllowAny])
def submit_contact_message(request):
    data = request.data
    ContactMessage.objects.create(
        name=data.get("name"),
        email=data.get("email"),
        phone=data.get("phone"),
        subject=data.get("subject"),
        message=data.get("message"),
    )
    return Response(
        {"message": "Message submitted successfully"}, status=status.HTTP_201_CREATED
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_contact_messages(request):
    if request.user.role != "ADMIN":
        return Response({"error": "Forbidden"}, status=403)

    messages = ContactMessage.objects.all().order_by("-created_at")
    data = []
    for m in messages:
        data.append(
            {
                "id": m.id,
                "name": m.name,
                "email": m.email,
                "phone": m.phone,
                "subject": m.subject,
                "message": m.message,
                "created_at": m.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    return Response(data)


# ------------------- Homepage Banner Views ------------------- #


@api_view(["GET"])
def list_homepage_banners(request):
    """Public endpoint to list active banners for current path."""
    banners = (
        HomepageBanner.objects.filter(is_active=True)
        .filter(models.Q(category="all") | models.Q(category=request.path))
        .order_by("priority", "-created_at")
    )
    serializer = HomepageBannerSerializer(
        banners, many=True, context={"request": request}
    )
    return Response(serializer.data)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def admin_manage_banners(request):
    """Admin endpoint to list all banners or create a new one."""
    if request.user.role != "ADMIN":
        return Response({"error": "Forbidden"}, status=403)

    if request.method == "GET":
        banners = HomepageBanner.objects.all().order_by("priority", "-created_at")
        serializer = HomepageBannerSerializer(
            banners, many=True, context={"request": request}
        )
        return Response(serializer.data)

    elif request.method == "POST":
        # Create a mutable copy of request data
        data = request.data.copy()
        serializer = HomepageBannerSerializer(data=data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def admin_banner_detail(request, pk):
    """Admin endpoint to retrieve, update or delete a banner."""
    if request.user.role != "ADMIN":
        return Response({"error": "Forbidden"}, status=403)

    try:
        banner = HomepageBanner.objects.get(pk=pk)
    except HomepageBanner.DoesNotExist:
        return Response({"error": "Banner not found"}, status=404)

    if request.method == "GET":
        serializer = HomepageBannerSerializer(banner, context={"request": request})
        return Response(serializer.data)

    elif request.method == "PUT":
        serializer = HomepageBannerSerializer(
            banner, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        banner.delete()
        return Response(
            {"message": "Banner deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


# -------------------hit-----------------------
@api_view(["GET"])
def get_hit_stats(request):
    total_hits = LoveAdugalam.objects.count()
    has_hit = False

    if request.user.is_authenticated:
        has_hit = LoveAdugalam.objects.filter(user=request.user).exists()

    return Response({"total_hits": total_hits, "has_hit": has_hit})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def record_hit(request):
    if LoveAdugalam.objects.filter(user=request.user).exists():
        return Response({"error": "Already hit"}, status=400)

    LoveAdugalam.objects.create(user=request.user)
    return Response(
        {"message": "Hit recorded", "total_hits": LoveAdugalam.objects.count()}
    )


# ----------------------user management in admin panel----------------------
from rest_framework.decorators import api_view
from rest_framework.response import Response
from core.models import AppUser


# GET USERS
@api_view(["GET"])
def get_users(request):

    search = request.GET.get("search", "")

    users = AppUser.objects.filter(role="USER")

    if search:
        users = users.filter(name__icontains=search)

    data = []

    for u in users:
        data.append(
            {
                "id": str(u.id),
                "name": u.name,
                "email": u.email,
                "mobile": u.mobile,
                "is_active": u.is_active,
            }
        )

    return Response(data)


# UPDATE USER
@api_view(["PUT"])
def update_user(request, user_id):

    try:
        user = AppUser.objects.get(id=user_id)
    except AppUser.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

    user.name = request.data.get("name", user.name)
    user.mobile = request.data.get("mobile", user.mobile)
    user.is_active = request.data.get("is_active", user.is_active)

    user.save()

    return Response({"message": "User updated"})


# DELETE USER
@api_view(["DELETE"])
def delete_user(request, user_id):

    try:
        user = AppUser.objects.get(id=user_id)
        user.delete()
        return Response({"message": "User deleted"})
    except AppUser.DoesNotExist:
        return Response({"error": "User not found"}, status=404)


# ---- USER RETIRE REQUEST (User submits reason) ----
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def user_retire_request(request):
    """User requests account deletion with a reason. Sets retire=1."""
    reason = request.data.get("reason", "").strip()
    if not reason:
        return Response({"error": "Please provide a reason for deletion."}, status=400)

    user = request.user
    user.retire = 1
    user.retire_reason = reason
    user.retire_requested_at = timezone.now()
    user.save()

    return Response({"message": "Account deletion request submitted successfully."})


# ---- USER SELF-RESTORE (retired user wants to come back via signup page) ----
@api_view(["POST"])
def restore_account(request):
    """
    Called when a user with retire=1 chooses 'Restore Account' on the signup page.
    Resets retire=0 — account is fully active again, user can login normally.
    No auth required (user is logged out), only email needed.
    """
    email = request.data.get("email", "").strip()
    if not email:
        return Response({"error": "Email is required."}, status=400)

    try:
        user = AppUser.objects.get(email=email, retire=1)
    except AppUser.DoesNotExist:
        return Response(
            {"error": "No pending deletion request found for this email."}, status=404
        )

    user.retire = 0
    user.retire_reason = None
    user.retire_requested_at = None
    user.save()

    return Response({"message": "Account restored successfully. You can now log in."})


# ---- ADMIN: LIST RETIRE REQUESTS ----
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_retire_requests(request):
    """Admin views all users who requested account deletion (retire=1)."""
    if request.user.role != "ADMIN":
        return Response({"error": "Access denied."}, status=403)

    users = AppUser.objects.filter(retire=1).order_by("-retire_requested_at")
    data = []
    for u in users:
        data.append(
            {
                "id": str(u.id),
                "name": u.name,
                "email": u.email,
                "mobile": u.mobile,
                "retire_reason": u.retire_reason or "",
                "retire_requested_at": u.retire_requested_at,
                "is_active": u.is_active,
            }
        )
    return Response(data)


# ---- ADMIN: APPROVE RETIRE (permanently delete) or REJECT (reset retire=0) ----
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_retire_action(request, user_id):
    """Admin approves (delete account + send email) or rejects (restore + send email) retire request."""
    if request.user.role != "ADMIN":
        return Response({"error": "Access denied."}, status=403)

    action = request.data.get("action")  # "approve" or "reject"

    try:
        user = AppUser.objects.get(id=user_id)
    except AppUser.DoesNotExist:
        return Response({"error": "User not found."}, status=404)

    # Save name and email BEFORE deleting (for the email notification)
    user_name = user.name
    user_email = user.email

    if action == "approve":
        # 1. Send email to user BEFORE deleting
        try:
            send_account_deletion_approved_email(user_email, user_name)
        except Exception as e:
            print(f"[Retire Approve Email Error] {e}")

        # 2. Permanently delete the account
        #    retire naturally becomes 0 since the record is gone
        #    → user can sign up fresh with same email as a new account
        user.delete()
        return Response(
            {"message": f"Account deleted. Notification email sent to {user_email}."}
        )

    elif action == "reject":
        # 1. Reset retire to 0 (account fully restored, like a normal active user)
        user.retire = 0
        user.retire_reason = None
        user.retire_requested_at = None
        user.save()

        # 2. Send email to user telling them account is restored
        try:
            send_account_deletion_rejected_email(user_email, user_name)
        except Exception as e:
            print(f"[Retire Reject Email Error] {e}")

        return Response(
            {
                "message": f"Request rejected. Account restored. Notification email sent to {user_email}."
            }
        )

    else:
        return Response(
            {"error": "Invalid action. Use 'approve' or 'reject'."}, status=400
        )


# -------------- payment details admin shows-------
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum
from .models import Payment


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def payments_report(request):
    from django.db.models import Q, Sum
    from django.utils import timezone
    from datetime import timedelta
    from .serializers import PaymentTransactionSerializer, VendorEarningsSerializer

    # Filters
    status_filter = request.GET.get("status", "SUCCESS")
    date_from_str = request.GET.get("date_from")
    date_to_str = request.GET.get("date_to")
    vendor_id = request.GET.get("vendor_id")
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 20))
    offset = (page - 1) * limit

    # Base queryset
    payments_qs = Payment.objects.select_related(
        "user", "booking__turf", "booking__turf__vendor", "booking__game"
    ).prefetch_related("booking__slots")

    # Status filter
    if status_filter != "all":
        payments_qs = payments_qs.filter(status=status_filter.upper())

    # Date range filter
    if date_from_str:
        date_from = timezone.datetime.strptime(date_from_str, "%Y-%m-%d").date()
        payments_qs = payments_qs.filter(created_at__date__gte=date_from)
    if date_to_str:
        date_to = timezone.datetime.strptime(date_to_str, "%Y-%m-%d").date()
        payments_qs = payments_qs.filter(created_at__date__lte=date_to)

    # Vendor filter
    if vendor_id:
        payments_qs = payments_qs.filter(booking__turf__vendor__vendor_id=vendor_id)

    total_count = payments_qs.count()
    payments = payments_qs[offset : offset + limit]

    # Summary
    total_revenue_paise = payments_qs.aggregate(total=Sum("amount"))["total"] or 0
    total_revenue = total_revenue_paise / 100
    admin_commission = total_revenue * 0.10
    vendor_earnings = total_revenue - admin_commission

    # Transactions serialized
    transactions = PaymentTransactionSerializer(payments, many=True).data

    # Vendor breakdown
    vendor_breakdown = (
        payments_qs.values(
            "booking__turf__vendor__vendor_id", "booking__turf__vendor__venuename"
        )
        .annotate(total_amount=Sum("amount"), txn_count=Count("id"))
        .order_by("-total_amount")
    )

    vendor_earnings_data = []
    for v in vendor_breakdown:
        vdata = {
            "vendor_id": v["booking__turf__vendor__vendor_id"] or "NO_VENDOR",
            "vendor_name": v["booking__turf__vendor__venuename"] or "Independent Turf",
            "total_amount": v["total_amount"] / 100,
            "txn_count": v["txn_count"],
        }
        vendor_earnings_data.append(vdata)

    return Response(
        {
            "success": True,
            "filters": {
                "status": status_filter,
                "date_from": date_from_str,
                "date_to": date_to_str,
                "vendor_id": vendor_id,
                "page": page,
                "limit": limit,
                "total_count": total_count,
            },
            "summary": {
                "totalRevenue": round(total_revenue, 2),
                "vendorEarnings": round(vendor_earnings, 2),
                "adminCommission": round(admin_commission, 2),
                "totalTransactions": total_count,
                "avgTransaction": round(total_revenue / max(total_count, 1), 2),
            },
            "transactions": transactions,
            "vendor_breakdown": vendor_earnings_data,
            "pagination": {
                "current_page": page,
                "total_pages": (total_count + limit - 1) // limit,
                "has_next": offset + limit < total_count,
                "has_prev": page > 1,
            },
        }
    )


# --------- refund policy---------------
@api_view(["PUT"])
def admin_refund_booking(request, booking_id):

    try:
        booking = Booking.objects.get(id=booking_id)
    except Booking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=404)

    try:
        payment = Payment.objects.get(booking=booking)

        if payment.status != "SUCCESS":
            return Response({"error": "Payment not successful"}, status=400)

        if not payment.razorpay_payment_id:
            return Response({"error": "Payment ID missing"}, status=400)

        # Razorpay client
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        # Refund request
        refund = client.payment.refund(
            payment.razorpay_payment_id, {"amount": payment.amount}
        )

        # 🔹 Update booking status
        booking.status = "REFUNDED"
        booking.save()

        # 🔹 Update payment
        payment.status = "FAILED"
        payment.save()

        # 🔹 Unlock slots
        booking.slots.update(is_available=True)

        return Response(
            {
                "success": True,
                "message": "Refund successful",
                "refund_id": refund.get("id"),
            }
        )

    except Exception as e:
        print("Refund Error:", str(e))
        return Response({"error": "Refund failed", "details": str(e)}, status=500)


@api_view(["GET"])
@permission_classes([AllowAny])
def user_notifications(request):
    """
    Returns the most recent notifications for a user, combining:
    1. OTP records (from EmailOTP model)
    2. Booking confirmations (from Booking model)
    Sorted by most recent first.
    """
    email = request.query_params.get("email")
    if not email:
        return Response({"error": "Email required"}, status=400)

    email = email.strip()

    import typing

    results: list[dict[str, typing.Any]] = []

    # --- 1. Recent OTP notifications ---
    try:
        otps = EmailOTP.objects.filter(email__iexact=email).order_by("-created_at")[:5]
        for otp in otps:
            results.append(
                {
                    "id": f"otp-{otp.id}",
                    "type": "otp",
                    "otp": otp.otp,
                    "email": otp.email,
                    "timestamp": otp.created_at.isoformat(),
                    "created_at": otp.created_at,  # for sorting
                }
            )
    except Exception as e:
        pass

    # --- 2. Recent booking notifications ---
    try:
        user = AppUser.objects.filter(email__iexact=email).first()
        if user:
            bookings = (
                Booking.objects.filter(user=user)
                .select_related("turf", "game")
                .prefetch_related("slots")
                .order_by("-created_at")[:5]
            )
            for booking in bookings:
                slot_displays = [
                    f"{s.start_time.strftime('%I:%M %p')} - {s.end_time.strftime('%I:%M %p')}"
                    for s in booking.slots.all()
                ]
                results.append(
                    {
                        "id": f"booking-{booking.id}",
                        "type": "booking",
                        "turf_name": booking.turf.name,
                        "game_name": booking.game.game_name if booking.game else "N/A",
                        "date": str(booking.date),
                        "slots": slot_displays,
                        "status": booking.status,
                        "timestamp": booking.created_at.isoformat(),
                        "created_at": booking.created_at,  # for sorting
                    }
                )
    except Exception as e:
        pass

    # --- 3. Sort merged list by created_at descending ---
    results.sort(key=lambda x: x["created_at"], reverse=True)

    # Remove the temporary created_at object before returning
    for r in results:
        r.pop("created_at", None)

    print(f"DEBUG: Returning {len(results[:10])} notifications")
    return Response(results[:10])


# =========================
# ADMIN / VENDOR FORGOT PASSWORD
# =========================


@api_view(["POST"])
@permission_classes([AllowAny])
def admin_forgot_password(request):
    email = request.data.get("email")
    if not email:
        return Response({"error": "Email is required"}, status=400)

    # 1. Check if Vendor
    vendor = Vendor.objects.filter(email=email).first()
    if vendor:
        if vendor.status != "Approved":
            return Response(
                {"error": "You are not yet approved. Please wait for admin approval."},
                status=403,
            )
    else:
        # 2. Check if AdminUser or AppUser with role="ADMIN"
        admin_user = AdminUser.objects.filter(email=email).first()
        app_user = AppUser.objects.filter(email=email, role="ADMIN").first()

        if not admin_user and not app_user:
            return Response({"error": "Admin/Vendor account not found"}, status=404)

    # 3. Generate and send OTP
    EmailOTP.objects.filter(email=email).delete()
    otp = generate_otp()
    EmailOTP.objects.create(email=email, otp=otp, is_verified=False)
    send_email_otp(email, otp)

    return Response({"message": "OTP sent to your email"})


@api_view(["POST"])
@permission_classes([AllowAny])
def admin_reset_password(request):
    email = request.data.get("email")
    new_password = request.data.get("password")
    otp = request.data.get("otp")

    if not all([email, new_password, otp]):
        return Response({"error": "Missing fields"}, status=400)

    # 1. Verify OTP
    try:
        otp_obj = EmailOTP.objects.get(email=email, otp=otp, is_verified=True)
    except EmailOTP.DoesNotExist:
        return Response({"error": "Invalid or unverified OTP"}, status=400)

    # 2. Reset across models
    user_updated = False

    app_user = AppUser.objects.filter(email=email).first()
    if app_user:
        app_user.password = make_password(new_password)
        app_user.save()
        user_updated = True

    admin_user = AdminUser.objects.filter(email=email).first()
    if admin_user:
        admin_user.password = make_password(new_password)
        admin_user.save()
        user_updated = True

    vendor = Vendor.objects.filter(email=email).first()
    if vendor:
        vendor.vendor_password = make_password(new_password)
        vendor.save()
        user_updated = True

    if not user_updated:
        return Response(
            {"error": "Account not found for updating password"}, status=404
        )

    # Invalidate OTP
    otp_obj.delete()

    return Response({"message": "Password reset successful"})


# -----------------vendor--------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vendor_profile(request):

    if request.user.role != "VENDOR":
        return Response({"error": "Not a vendor"}, status=403)

    try:
        vendor = Vendor.objects.get(email=request.user.email)

        return Response(
            {
                "vendor_id": vendor.vendor_id,
                "venuename": vendor.venuename,
                "email": vendor.email,
                "phone": vendor.phone,
            }
        )

    except Vendor.DoesNotExist:
        return Response({"error": "Vendor not found"}, status=404)


# ---- vendor turflist-----------
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from core.models import Turf


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vendor_my_turfs(request):
    """
    Returns list of turfs owned by the logged-in vendor.
    Filtering is done via request.user.email.
    """
    if request.user.role != "VENDOR":
        return Response({"error": "Access denied. Vendor role required."}, status=403)

    try:
        # 🔥 Get vendor using logged-in user email
        try:
            vendor = Vendor.objects.get(email=request.user.email)
        except Vendor.DoesNotExist:
            return Response(
                {"error": f"Vendor profile not found for email: {request.user.email}"},
                status=404,
            )

        # 🔥 FILTER USING VENDOR (NOT owner), exclude retired turfs
        turfs = Turf.objects.filter(vendor=vendor, retire=0).prefetch_related(
            "banners", "gallery", "slot_items", "game_items"
        )

        data = []
        for t in turfs:
            try:
                data.append(
                    {
                        "id": t.id,
                        "name": t.name,
                        "location": t.location,
                        "latitude": t.latitude,
                        "longitude": t.longitude,
                        "price_per_hour": t.price_per_hour,
                        "description": t.description or "",
                        "games": (
                            # ✅ game_items table = always accurate after edit
                            [x.game_name for x in t.game_items.all()]
                            if t.game_items.exists()
                            else (
                                __import__('json').loads(t.games)
                                if isinstance(t.games, str) and t.games
                                else (t.games or [])
                            )
                        ),
                        "amenities": t.amenities or [],
                        "features": t.features or [],
                        # ✅ RELATIVE URLS handled by frontend getImageUrl
                        "banner_images": [img.image.url for img in t.banners.all()],
                        "gallery_images": [img.image.url for img in t.gallery.all()],
                        "slots": [
                            {
                                "time_display": f"{s.start_time.strftime('%I:%M %p')} - {s.end_time.strftime('%I:%M %p')}",
                                "price": s.price,
                            }
                            for s in t.slot_items.all()
                        ],
                        "is_approved": t.is_approved,
                        "is_maintenance": t.is_maintenance,
                    }
                )
            except Exception as e:
                print(f"Error processing turf {t.id}: {e}")
                continue

        return Response(data)

    except Exception as e:
        print(f"Vendor My Turfs Error: {e}")
        return Response(
            {"error": "An internal server error occurred while loading turfs."},
            status=500,
        )


# ---- vendor turf detail (for edit form pre-fill) ----
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vendor_turf_detail(request, turf_id):
    """Returns full detail of a single turf for the vendor edit form."""
    if request.user.role != "VENDOR":
        return Response({"error": "Access denied."}, status=403)

    try:
        vendor = Vendor.objects.get(email=request.user.email)
    except Vendor.DoesNotExist:
        return Response({"error": "Vendor profile not found."}, status=404)

    try:
        turf = Turf.objects.prefetch_related(
            "banners", "gallery", "slot_items", "game_items"
        ).get(id=turf_id, vendor=vendor)
    except Turf.DoesNotExist:
        return Response({"error": "Turf not found."}, status=404)

    return Response(
        {
            "id": turf.id,
            "name": turf.name,
            "location": turf.location,
            "latitude": turf.latitude,
            "longitude": turf.longitude,
            "price_per_hour": turf.price_per_hour,
            "description": turf.description or "",
            "games": turf.games
            if turf.games
            else [g.game_name for g in turf.game_items.all()],
            "amenities": turf.amenities or [],
            "features": turf.features or [],
            "banner_images": [
                request.build_absolute_uri(img.image.url) for img in turf.banners.all()
            ],
            "gallery_images": [
                request.build_absolute_uri(img.image.url) for img in turf.gallery.all()
            ],
            "slots": [
                {
                    "time_display": f"{s.start_time.strftime('%I:%M %p')} - {s.end_time.strftime('%I:%M %p')}",
                    "price": s.price,
                }
                for s in turf.slot_items.all()
            ],
            "is_approved": turf.is_approved,
            "is_maintenance": turf.is_maintenance,
        }
    )


# ---- vendor edit turf ----
from rest_framework.parsers import MultiPartParser, FormParser
from core.models import TurfBanner, TurfGallery
import json as _json


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def vendor_edit_turf(request, turf_id):
    """Allows a vendor to update or soft-delete their own turf."""
    if request.user.role != "VENDOR":
        return Response({"error": "Access denied."}, status=403)

    try:
        vendor = Vendor.objects.get(email=request.user.email)
    except Vendor.DoesNotExist:
        return Response({"error": "Vendor profile not found."}, status=404)

    try:
        turf = Turf.objects.get(id=turf_id, vendor=vendor, retire=0)
    except Turf.DoesNotExist:
        return Response({"error": "Turf not found."}, status=404)

    # ── DELETE: soft-delete by setting retire=1 ──
    if request.method == "DELETE":
        turf.retire = 1
        turf.save()
        return Response({"success": True, "message": "Turf deleted successfully."})

    # ── PATCH: update fields ──
    data = request.data

    # Update scalar fields if provided
    if "location" in data:
        turf.location = data["location"]
    if "latitude" in data:
        turf.latitude = data["latitude"] or None
    if "longitude" in data:
        turf.longitude = data["longitude"] or None
    if "price" in data:
        new_price = int(data["price"])
        turf.price_per_hour = new_price
        # Update associated slots and games to maintain consistency
        Slot.objects.filter(turf=turf).update(price=new_price)
        Game.objects.filter(turf=turf).update(price=new_price)
    if "description" in data:
        turf.description = data["description"]
    if "games" in data:
        try:
            new_games = _json.loads(data["games"])
        except Exception:
            new_games = data.getlist("games")
        # ✅ Update JSON field
        turf.games = new_games
        # ✅ Smart sync: remove old games not in new list, add new games
        existing_game_names = list(turf.game_items.values_list("game_name", flat=True))
        # Remove games that are no longer selected
        turf.game_items.filter(game_name__in=[g for g in existing_game_names if g not in new_games]).delete()
        # Add games that are newly selected
        for game_name in new_games:
            if game_name not in existing_game_names:
                Game.objects.create(
                    turf=turf,
                    game_name=game_name,
                    price=turf.price_per_hour or 0,
                )
    if "amenities" in data:
        try:
            turf.amenities = _json.loads(data["amenities"])
        except Exception:
            turf.amenities = data.getlist("amenities")
    if "features" in data:
        try:
            turf.features = _json.loads(data["features"])
        except Exception:
            turf.features = data.getlist("features")

    turf.save()

    # Handle new banner images (append or replace)
    new_banners = request.FILES.getlist("banner_images")
    if new_banners:
        # Replace all banners if new ones provided
        turf.banners.all().delete()
        for img in new_banners:
            TurfBanner.objects.create(turf=turf, image=img)

    # Handle new gallery images (append or replace)
    new_gallery = request.FILES.getlist("gallery_images")
    if new_gallery:
        turf.gallery.all().delete()
        for img in new_gallery:
            TurfGallery.objects.create(turf=turf, image=img)

    return Response({"success": True, "message": "Turf updated successfully."})



# ---- vendor toggle maintenance mode ----
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def vendor_toggle_maintenance(request, turf_id):
    """Toggles is_maintenance for a vendor's turf."""
    if request.user.role != "VENDOR":
        return Response({"error": "Access denied."}, status=403)

    try:
        vendor = Vendor.objects.get(email=request.user.email)
    except Vendor.DoesNotExist:
        return Response({"error": "Vendor profile not found."}, status=404)

    try:
        turf = Turf.objects.get(id=turf_id, vendor=vendor)
    except Turf.DoesNotExist:
        return Response({"error": "Turf not found."}, status=404)

    turf.is_maintenance = not turf.is_maintenance
    turf.save()

    return Response(
        {
            "success": True,
            "is_maintenance": turf.is_maintenance,
            "message": f"Maintenance mode {'enabled' if turf.is_maintenance else 'disabled'} for '{turf.name}'.",
        }
    )


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

            slots = Slot.objects.filter(
                turf=turf, start_time__gte=start_t, end_time__lte=end_t
            )

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
                    },
                )

        return Response({"success": True})
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def vendor_set_bulk_peak_hours(request):
    turf_id = request.data.get("turf_id")
    configs = request.data.get("configs", [])

    try:
        try:
            vendor = Vendor.objects.get(email=request.user.email)
            turf = Turf.objects.get(id=turf_id, vendor=vendor)
        except Vendor.DoesNotExist:
            turf = Turf.objects.get(id=turf_id, owner=request.user)
            
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

            slots = Slot.objects.filter(
                turf=turf, start_time__gte=start_t, end_time__lte=end_t
            )

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
                    },
                )

        return Response({"success": True})
    except Turf.DoesNotExist:
        return Response(
            {"error": "Turf not found or you do not have permission."}, status=403
        )
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
            data.append(
                {
                    "id": t.id,
                    "name": t.name,
                    "location": t.location,
                }
            )

        return Response(data)
    except Vendor.DoesNotExist:
        return Response({"error": "Vendor not found."}, status=404)


# -------------------- FAVORITE TURF VIEWS --------------------
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import FavoriteTurf, Turf
from .serializers import FavoriteTurfSerializer


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def toggle_favorite(request, turf_id):
    user = request.user
    turf = get_object_or_404(Turf, id=turf_id)

    favorite = FavoriteTurf.objects.filter(user=user, turf=turf).first()

    if favorite:
        favorite.delete()
        return Response({"status": "removed"})
    else:
        FavoriteTurf.objects.create(user=user, turf=turf)
        return Response({"status": "added"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_favorite_turfs(request):
    user = request.user
    favorites = FavoriteTurf.objects.filter(user=user).select_related("turf")
    serializer = FavoriteTurfSerializer(
        favorites, many=True, context={"request": request}
    )
    return Response(serializer.data)



# ==================== EVENTS ====================
from .models import Event
from .serializers import EventSerializer

@api_view(["GET"])
@permission_classes([AllowAny])
def list_events(request):
    """Public: List events with optional status filter (computed from dates)"""
    from datetime import date as dt_date
    status_filter = request.query_params.get("status", "").lower()
    events = Event.objects.filter(is_active=True)
    today = dt_date.today()
    result = []

    for event in events:
        start = event.start_date
        end = event.end_date

        if event.status == "featured":
            computed_status = "featured"
        elif not start:
            computed_status = "upcoming"
        elif start > today:
            computed_status = "upcoming"
        elif end and end >= today >= start:
            computed_status = "ongoing"
        elif end and end < today:
            computed_status = "completed"
        else:
            computed_status = "upcoming"

        if status_filter and computed_status != status_filter:
            continue

        data = EventSerializer(event, context={"request": request}).data
        data["status"] = computed_status
        result.append(data)

    return Response(result)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser])
def admin_events(request):
    """Admin: List all events or create a new event"""
    if request.method == "GET":
        qs = Event.objects.all().order_by("-created_at")
        serializer = EventSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    # POST - Create event
    data = request.data.copy()

    def parse_time(hour, minute, ampm):
        try:
            hr = int(hour)
            if ampm == "PM" and hr != 12:
                hr += 12
            if ampm == "AM" and hr == 12:
                hr = 0
            return f"{hr:02d}:{minute or '00'}:00"
        except Exception:
            return None

    start_hour = data.get("startTime_hour") or data.get("start_hour", "")
    start_min = data.get("startTime_minute") or data.get("start_minute", "00")
    start_ampm = data.get("startTime_ampm") or data.get("start_ampm", "AM")
    end_hour = data.get("endTime_hour") or data.get("end_hour", "")
    end_min = data.get("endTime_minute") or data.get("end_minute", "00")
    end_ampm = data.get("endTime_ampm") or data.get("end_ampm", "AM")

    event_data = {
        "title": data.get("eventName") or data.get("title", ""),
        "category": data.get("eventCategory") or data.get("category", "Sports"),
        "location": data.get("location", ""),
        "address": data.get("address", ""),
        "organized_by": data.get("organizedBy") or data.get("organized_by", ""),
        "start_date": data.get("startDate") or data.get("start_date") or None,
        "end_date": data.get("endDate") or data.get("end_date") or None,
        "start_time": parse_time(start_hour, start_min, start_ampm),
        "end_time": parse_time(end_hour, end_min, end_ampm),
        "amount": data.get("amount", 0) or 0,
        "is_free": str(data.get("amount", "0")) == "0",
        "agenda": data.get("agenda", ""),
        "vips": data.get("vips", ""),
        "total_seats": int(data.get("total_seats", 0) or 0),
        "status": data.get("status", "upcoming"),
        "is_active": True,
    }

    if not event_data["start_time"]:
        del event_data["start_time"]
    if not event_data["end_time"]:
        del event_data["end_time"]
    if not event_data["start_date"]:
        del event_data["start_date"]
    if not event_data["end_date"]:
        del event_data["end_date"]

    serializer = EventSerializer(data=event_data, context={"request": request})
    if serializer.is_valid():
        event = serializer.save()
        if "banner" in request.FILES:
            event.image = request.FILES["banner"]
            event.save()
        return Response(EventSerializer(event, context={"request": request}).data, status=201)

    return Response(serializer.errors, status=400)


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser])
def admin_event_detail(request, pk):
    """Admin: Get, update or delete a specific event"""
    try:
        event = Event.objects.get(pk=pk)
    except Event.DoesNotExist:
        return Response({"error": "Event not found"}, status=404)

    if request.method == "GET":
        serializer = EventSerializer(event, context={"request": request})
        return Response(serializer.data)

    if request.method == "PUT":
        data = request.data
        event.title = data.get("eventName") or data.get("title", event.title)
        event.category = data.get("eventCategory") or data.get("category", event.category)
        event.location = data.get("location", event.location)
        event.address = data.get("address", event.address)
        event.organized_by = data.get("organizedBy") or data.get("organized_by", event.organized_by)
        event.start_date = data.get("startDate") or data.get("start_date", event.start_date) or None
        event.end_date = data.get("endDate") or data.get("end_date", event.end_date) or None
        event.amount = data.get("amount", event.amount)
        event.is_free = str(data.get("amount", event.amount)) == "0"
        event.agenda = data.get("agenda", event.agenda)
        event.vips = data.get("vips", event.vips)
        event.total_seats = int(data.get("total_seats", event.total_seats) or 0)
        event.status = data.get("status", event.status)
        event.is_active = data.get("is_active", event.is_active)

        if "banner" in request.FILES:
            event.image = request.FILES["banner"]

        event.save()
        return Response(EventSerializer(event, context={"request": request}).data)

    if request.method == "DELETE":
        event.delete()
        return Response({"message": "Event deleted"})


@api_view(["POST"])
@permission_classes([AllowAny])
def book_event(request, pk):
    """Book an event seat - increments booked_seats"""
    try:
        event = Event.objects.get(pk=pk)
    except Event.DoesNotExist:
        return Response({"error": "Event not found"}, status=404)

    if event.total_seats > 0 and event.booked_seats >= event.total_seats:
        return Response({"error": "Slot Full! All seats are booked."}, status=400)

    event.booked_seats += 1
    event.save()

    seats_left = max(event.total_seats - event.booked_seats, 0)
    return Response({
        "message": "Successfully Booked!",
        "booked_seats": event.booked_seats,
        "total_seats": event.total_seats,
        "seats_left": seats_left,
    })


# ==================== EVENT REVIEWS ====================
from .models import EventReview
from .serializers import EventReviewSerializer

@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def event_reviews_list(request, event_id):
    """Public: Get reviews for an event or post a new review"""
    try:
        event = Event.objects.get(pk=event_id)
    except Event.DoesNotExist:
        return Response({"error": "Event not found"}, status=404)

    if request.method == "GET":
        reviews = EventReview.objects.filter(event=event)
        serializer = EventReviewSerializer(reviews, many=True)
        return Response(serializer.data)

    # POST
    data = request.data.copy()
    data['event'] = event.id
    serializer = EventReviewSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)


@api_view(["GET", "DELETE"])
@permission_classes([AllowAny])
def admin_event_reviews(request, review_id=None):
    """Admin: Get all reviews across all events or delete a specific review"""
    if request.method == "GET":
        event_id = request.query_params.get("event_id")
        if event_id:
            reviews = EventReview.objects.filter(event_id=event_id)
        else:
            reviews = EventReview.objects.all()
        serializer = EventReviewSerializer(reviews, many=True)
        return Response(serializer.data)

    if request.method == "DELETE":
        if not review_id:
            return Response({"error": "Review ID required"}, status=400)
        try:
            review = EventReview.objects.get(pk=review_id)
            review.delete()
            return Response(status=204)
        except EventReview.DoesNotExist:
            return Response({"error": "Review not found"}, status=404)


@api_view(["GET"])
@permission_classes([AllowAny])
def turf_booked_slots_by_date(request, turf_id):
    date = request.GET.get("date")
    if not date:
        return Response({"error": "Missing date parameter"}, status=400)
 
    # Get all confirmed or pending bookings for this turf on this date
    # Statuses usually include 'CONFIRMED' or 'PENDING'
    booked_slots = Booking.objects.filter(
        turf_id=turf_id,
        date=date,
        status__in=["CONFIRMED", "PENDING"]
    ).values_list('slots__id', flat=True)
 
    return Response({
        "turf_id": turf_id,
        "date": date,
        "booked_slot_ids": list(set(booked_slots))
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def booking_receipt(request, booking_id):
    try:
        booking = Booking.objects.select_related("turf").prefetch_related("slots").get(
            id=booking_id, user=request.user
        )
        payment = Payment.objects.get(booking=booking, status="SUCCESS")
    except (Booking.DoesNotExist, Payment.DoesNotExist):
        return Response({"error": "Receipt not found"}, status=404)
        
    return Response({
        "booking_id": booking.id,
        "turf_name": booking.turf.name,
        "date": booking.date,
        "payment_id": payment.razorpay_payment_id,
        "amount_paid": float(payment.amount)/100 if payment.amount else 0,
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
        "slots": [
             f"{s.start_time.strftime('%I:%M %p')} - {s.end_time.strftime('%I:%M %p')}"
             for s in booking.slots.all()
        ]
    })
