import razorpay

# --------------location ----------------


from django.db import models

class Location(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
# --------------------------------------


from django.db import models
from django.contrib.auth.models import User
from django.conf import settings



# -------------------- ACCOUNTS --------------------

import uuid
from django.db import models
from django.contrib.auth.models import User


# =========================
# TURF
# =========================
class Turf(models.Model):

    name = models.CharField(max_length=100)

    location = models.CharField(max_length=255)

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    price_per_hour = models.IntegerField()

    description = models.TextField(null=True, blank=True)

    games = models.JSONField(default=list, blank=True)
    amenities = models.JSONField(default=list, blank=True)
    features = models.JSONField(default=list, blank=True)

    slots = models.JSONField(default=list, blank=True)

    is_popular = models.BooleanField(default=False)

    priority = models.IntegerField(
        default=1,
        help_text="Lower number = higher priority")

    vendor = models.ForeignKey(
        "Vendor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    vendor_code = models.CharField(max_length=20, blank=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    is_approved = models.BooleanField(default=False)
    is_maintenance = models.BooleanField(default=False)
    retire = models.IntegerField(default=0)
    ROLE_CHOICES = (
        ("vendor", "Vendor"),
        ("admin", "Admin"),
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="admin",
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    # AUTO SLOT ID FOR JSON (legacy)
    def save(self, *args, **kwargs):

        updated_slots = []

        for slot in self.slots or []:
            if not isinstance(slot, dict):
                continue

            if not slot.get("id"):
                slot["id"] = str(uuid.uuid4())

            slot.setdefault("is_booked", False)
            updated_slots.append(slot)

        self.slots = updated_slots

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# =========================
# SLOT TABLE (NEW ✅)
# =========================
class Slot(models.Model):

    turf = models.ForeignKey(
        Turf,
        on_delete=models.CASCADE,
        related_name="slot_items"   # ⭐ IMPORTANT FIX
    )

    start_time = models.TimeField()
    end_time = models.TimeField()
    price = models.IntegerField()

    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.turf.name} {self.start_time}-{self.end_time}"


# =========================
# IMAGES
# =========================
class TurfBanner(models.Model):
    turf = models.ForeignKey(
        Turf,
        on_delete=models.CASCADE,
        related_name="banners"  
    )
    image = models.ImageField(upload_to="turf/banners/")

    def __str__(self):
        return f"Banner - {self.turf.name}"


class TurfGallery(models.Model):
    turf = models.ForeignKey(
        Turf,
        on_delete=models.CASCADE,
        related_name="gallery"
    )
    image = models.ImageField(upload_to="turf/gallery/")

    def __str__(self):
        return f"Gallery - {self.turf.name}"

# =========================
# GAME TABLE (NEW ✅)
# =========================
class Game(models.Model):

    game_name = models.CharField(max_length=100)

    turf = models.ForeignKey(
        Turf,
        on_delete=models.CASCADE,
        related_name="game_items"
    )

    price = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.game_name} - {self.turf.name}"


# ----------------adminlaa vendor add panna vendiya model-----------------
from django.db import models
from datetime import datetime

class Vendor(models.Model):
    venuename = models.CharField(max_length=200)
    ownername = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)

    location = models.CharField(max_length=100)
    address = models.TextField()
    pincode = models.CharField(max_length=10)

    totalturf = models.IntegerField()

    availablegames = models.JSONField()

    vendor_id = models.CharField(max_length=20, unique=True, blank=True)
    STATUS_CHOICES = (
    ("Pending", "Pending"),
    ("Rejected", "Rejected"),
    ("Approved", "Approved"),
)
    status = models.CharField(
    max_length=20,
    choices=STATUS_CHOICES,
    default="Pending"
)
    vendor_password = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.vendor_id:
            prefix = self.email[:3].upper()
            year = datetime.now().year

            base_id = f"{prefix}{year}"

            count = Vendor.objects.filter(
                vendor_id__startswith=base_id
            ).count()

            if count == 0:
                self.vendor_id = base_id
            else:
                self.vendor_id = f"{base_id}-{count+1}"

        super().save(*args, **kwargs)


class Ground(models.Model):
    GAME_CHOICES = (
        ("football", "Football"),
        ("cricket", "Cricket"),
        ("badminton", "Badminton"),
        ("tennis", "Tennis"),
    )
    turf = models.ForeignKey(Turf, on_delete=models.CASCADE, related_name="grounds")
    name = models.CharField(max_length=100)
    game_type = models.CharField(max_length=50, choices=GAME_CHOICES)

    def __str__(self):
        return f"{self.turf.name} - {self.game_type}- {self.name}"


# class Slot(models.Model):
#     ground = models.ForeignKey(Ground, on_delete=models.CASCADE, related_name="slots")
#     start_time = models.TimeField()
#     end_time = models.TimeField()
#     is_booked = models.BooleanField(default=False)

#     def __str__(self):
#         return f"{self.start_time} - {self.end_time}"
#--------------------------------------------------------------#



# -------------------- BOOKINGS --------------------

class Cart(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    turf = models.ForeignKey(Turf, on_delete=models.CASCADE)
    slot = models.ForeignKey(Slot, on_delete=models.CASCADE)
    date = models.DateField()

    def __str__(self):
        return f"Cart - {self.user.username}"


# =========================
# BOOKINGS (UPDATED )
# =========================

from django.db import models
from django.contrib.auth.models import User


class Booking(models.Model):

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("CONFIRMED", "Confirmed"),
        ("CANCELLED", "Cancelled"),
        ("REFUNDED", "Refunded"),
    )

    # ================= USER =================
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings"
    )

    # ================= USER DETAILS (CAPTURED AT BOOKING) =================
    user_name = models.CharField(max_length=100, blank=True, null=True)
    user_email = models.EmailField(blank=True, null=True)
    user_mobile = models.CharField(max_length=15, blank=True, null=True)

    # ================= TURF =================
    turf = models.ForeignKey(
        "Turf",
        on_delete=models.CASCADE,
        related_name="bookings"
    )

    # ================= GAME =================
    game = models.ForeignKey(
        "Game",
        on_delete=models.CASCADE,
        related_name="bookings"
    )

    # ================= SLOTS =================
    slots = models.ManyToManyField(
        "Slot",
        related_name="bookings"
    )

    # ================= DATE =================
    date = models.DateField()

    # ================= PRICING =================
    original_amount = models.DecimalField(max_digits=10, decimal_places=2)
    advance_amount = models.DecimalField(max_digits=10, decimal_places=2)
    service_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=20.00
    )
    total_payable = models.DecimalField(max_digits=10, decimal_places=2)

    # optional (you used in API)
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    # ================= STATUS =================
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    vendor_status = models.CharField(
        max_length=20,
        default="PENDING"
    )

    # ================= TIMESTAMP =================
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Booking {self.id} - {self.user.username}"
    
# -------------------- PAYMENTS --------------------

class Payment(models.Model):
    PAYMENT_STATUS = (
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE)

    razorpay_order_id = models.CharField(max_length=200)
    razorpay_payment_id = models.CharField(max_length=200, null=True, blank=True)
    razorpay_signature = models.CharField(max_length=300, null=True, blank=True)

    amount = models.IntegerField() 
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.booking.id} - {self.status}"



# -------------------- Admin --------------------

# Adminotp Model


class AdminUser(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=10, unique=True)
    password = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


#____________---------------------peak hours ----------------------#
# =========================
# PEAK HOURS (NEW ✅)
# =========================

class PeakHour(models.Model):

    turf = models.ForeignKey(
        Turf,
        on_delete=models.CASCADE,
        related_name="peak_hours"
    )

    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="peak_hours"
    )

    slot = models.ForeignKey(
        Slot,
        on_delete=models.CASCADE,
        related_name="peak_hours"
    )

    date = models.DateField()

    from_time = models.TimeField()
    to_time = models.TimeField()

    peak_price = models.IntegerField()

    updated_time = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("turf", "slot", "date")

    def __str__(self):
        return f"Peak {self.turf.name} - {self.date}"
    

    # --------------------- SMTP ----------------------

from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
import uuid

class UserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'ADMIN')

        return self.create_user(email, password, **extra_fields)


class AppUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ("USER", "User"),
        ("ADMIN", "Admin"),
        ("VENDOR", "Vendor"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    mobile = models.CharField(max_length=15, blank=True, null=True)

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="USER")

    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)   # Django admin panel
    is_superuser = models.BooleanField(default=False)

    # Account retirement (soft-delete request)
    retire = models.IntegerField(default=0)  # 0 = active, 1 = delete requested
    retire_reason = models.TextField(blank=True, null=True)
    retire_requested_at = models.DateTimeField(blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    objects = UserManager()

    def __str__(self):
        return self.email

class EmailOTP(models.Model):
    email = models.EmailField(db_index=True)
    otp = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.created_at + timezone.timedelta(minutes=5)
    def __str__(self):
        return f"{self.email}-{self.otp}"

# -------------------- USER ISSUES / SUPPORT TICKETS --------------------
class UserIssue(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("RESOLVED", "Resolved"),
        ("IN_PROGRESS", "In Progress"),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="issues",
        null=True, blank=True
    )
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.title} - {self.name}"
    
# -------------------- CONTACT MESSAGES --------------------
class ContactMessage(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

# -------------------- HOMEPAGE BANNERS --------------------
class HomepageBanner(models.Model):
    title = models.CharField(max_length=200, blank=True)
    text = models.TextField(blank=True)
    button_text = models.CharField(max_length=50, default="Book Now")
    image = models.ImageField(upload_to="banners/")
    link_path = models.CharField(max_length=200, default="/Bookhome")
    priority = models.IntegerField(default=1, help_text="Lower number = higher priority")
    category = models.CharField(
        max_length=200, 
        default="all", 
        help_text="Page path (e.g. '/play') or 'all' for all pages"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['priority', '-created_at']

    def __str__(self):
        return self.title or f"Banner {self.id}"
    
# ---------------------------hit-------------------------
class LoveAdugalam(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='love_hit')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Love from {self.user.email} username {self.user.name}'

# -------------------- FAVORITE TURF --------------------
class FavoriteTurf(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorite_turfs')
    turf = models.ForeignKey('Turf', on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'turf')

    def __str__(self):
        return f"{self.user.name} - {self.turf.name}"


# -------------------- EVENTS --------------------
class Event(models.Model):
    STATUS_CHOICES = (
        ("upcoming", "Upcoming"),
        ("ongoing", "Ongoing"),
        ("featured", "Featured"),
        ("completed", "Completed"),
    )

    CATEGORY_CHOICES = (
        ("Conference", "Conference"),
        ("Workshop", "Workshop"),
        ("Festival", "Festival"),
        ("Sports", "Sports"),
        ("Other", "Other"),
    )

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default="Sports")
    location = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    organized_by = models.CharField(max_length=200, blank=True)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_free = models.BooleanField(default=False)

    total_seats = models.IntegerField(default=0)
    booked_seats = models.IntegerField(default=0)

    image = models.ImageField(upload_to="events/banners/", null=True, blank=True)

    agenda = models.TextField(blank=True)
    vips = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="upcoming")
    is_active = models.BooleanField(default=True)

    bg_color = models.CharField(max_length=20, default="#a5b4fc", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_date', '-created_at']

    def __str__(self):
        return self.title


class EventReview(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=100)
    rating = models.IntegerField(default=5)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.event.title} ({self.rating} Stars)"
