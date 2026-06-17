# ------------location-----------------------------------


from rest_framework import serializers
from .models import Location

class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "name"]
# -------------------------------------------------------
from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Turf, TurfBanner, TurfGallery, Ground, Slot, Booking, Payment, AdminUser


class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "email",
            "mobile",
            "is_verified",
        ]


class TurfBannerSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(use_url=True)
    
    class Meta:
        model = TurfBanner
        fields = ["id", "image"]


class TurfGallerySerializer(serializers.ModelSerializer):
    image = serializers.ImageField(use_url=True)
    
    class Meta:
        model = TurfGallery
        fields = ["id", "image"]


class TurfSerializer(serializers.ModelSerializer):
    banners = TurfBannerSerializer(many=True, read_only=True)
    gallery = TurfGallerySerializer(many=True, read_only=True)
    # Keep image for backward compatibility - returns first banner
    image = serializers.SerializerMethodField()

    class Meta:
        model = Turf
        fields = "__all__"
    
    def get_image(self, obj):
        # Return first banner image for backward compatibility
        banner = obj.banners.first()
        if banner:
            return banner.image.url
        return None



class VendorTurfCreateSerializer(serializers.Serializer):
    # Support both 'name' and 'turfName' for compatibility
    turfName = serializers.CharField(required=False)
    name = serializers.CharField(required=False)
    location = serializers.CharField()
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False
    )
    turfCount = serializers.IntegerField(required=False)
    price = serializers.IntegerField()
    description = serializers.CharField(required=False, allow_blank=True)
    amenities = serializers.ListField(child=serializers.CharField(), required=False)
    features = serializers.ListField(child=serializers.CharField(), required=False)
    games = serializers.ListField(child=serializers.CharField(), required=False)
    slots = serializers.JSONField(required=False)
    vendorId = serializers.CharField(required=False)
    banner_images = serializers.ListField(
        child=serializers.ImageField(), required=False
    )
    gallery_images = serializers.ListField(
        child=serializers.ImageField(), required=False
    )


class GroundSerializer(serializers.ModelSerializer):
    turf = TurfSerializer(read_only=True)

    class Meta:
        model = Ground
        fields = ["id", "turf", "turf_id", "name","game_type"]


class SlotSerializer(serializers.ModelSerializer):
    # Frontend-க்கு readable time format
    time_display = serializers.SerializerMethodField()
    # Price field add pannanum
    price_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Slot
        fields = [
            "id", 
            "turf",  # ✅ turf FK instead of ground_id
            "start_time", 
            "end_time", 
            "price",  # ✅ Added price field
            "is_available",  # ✅ is_available instead of is_booked
            "time_display",
            "price_display"
        ]
    
    
    def get_time_display(self, obj):
        """Frontend-friendly time format"""
        return f"{obj.start_time.strftime('%I:%M %p')} - {obj.end_time.strftime('%I:%M %p')}"
    
    def get_price_display(self, obj):
        """₹ formatted price"""
        return f"₹{obj.price}"


class BookingListSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)
    turf_name = serializers.CharField(source="cart.turf.name", read_only=True)
    ground_name = serializers.CharField(source="cart.ground.name", read_only=True)
    date = serializers.DateField(source="cart.date", read_only=True)
    slot_start = serializers.TimeField(source="cart.slot.start_time", read_only=True)
    slot_end = serializers.TimeField(source="cart.slot.end_time", read_only=True)
    amount = serializers.SerializerMethodField()

    def get_amount(self, obj):
        # In your backend, price is stored on Turf as price_per_hour.
        try:
            return obj.cart.turf.price_per_hour
        except Exception:
            return None

    class Meta:
        model = Booking
        fields = [
            "id",
            "user",
            "status",
            "created_at",
            "turf_name",
            "ground_name",
            "date",
            "slot_start",
            "slot_end",
            "amount",
        ]


class PaymentListSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)
    booking_id = serializers.IntegerField(source="booking.id", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "booking_id",
            "user",
            "razorpay_order_id",
            "razorpay_payment_id",
            "amount",
            "status",
            "created_at",
        ]
# ----------------adminserilization


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminUser
        fields = "__all__"

class AdminTurfCreateSerializer(serializers.Serializer):
    vendorId = serializers.CharField()
    name = serializers.CharField()
    location = serializers.CharField()
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    price = serializers.IntegerField()

    games = serializers.ListField(child=serializers.CharField(), required=False)
    amenities = serializers.ListField(child=serializers.CharField(), required=False)
    features = serializers.ListField(child=serializers.CharField(), required=False)
    description = serializers.CharField(required=False)

    banner = serializers.ListField(
        child=serializers.ImageField(), required=False
    )
    gallery = serializers.ListField(
        child=serializers.ImageField(), required=False
    )

    slots = serializers.JSONField(required=False)


from rest_framework import serializers
from .models import Booking, Slot, UserIssue
from .serializers import SlotSerializer  # ✅ Your existing SlotSerializer import

class UserIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserIssue
        fields = "__all__"
    def create(self, validated_data):
        """Auto-set resolved_at=None when creating"""
        validated_data['resolved_at'] = None
        return super().create(validated_data)

class BookingDetailSerializer(serializers.ModelSerializer):
    turf_name = serializers.CharField(source='turf.name')
    slots = SlotSerializer(many=True, read_only=True)  # ✅ Your SlotSerializer use pannum
    
    class Meta:
        model = Booking
        fields = [
            'id', 
            'turf_name', 
            'date', 
            'total_price', 
            'slots',  # ✅ time_display, price_display automatic varum
            'original_amount', 
            'advance_amount', 
            'service_charge'
        ]

class PaymentTransactionSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name')
    user_id = serializers.CharField(source='user.id')
    booking = BookingDetailSerializer()
    turf_name = serializers.CharField(source='booking.turf.name')
    vendor_name = serializers.SerializerMethodField()
    vendor_id = serializers.SerializerMethodField()
    game_name = serializers.CharField(source='booking.game.game_name')
    booking_date = serializers.DateField(source='booking.date')

    class Meta:
        model = Payment
        fields = [
            'id', 'razorpay_payment_id', 'amount', 'status', 'created_at',
            'user_id', 'user_name', 'booking', 'turf_name', 'vendor_name', 'vendor_id', 
            'game_name', 'booking_date'
        ]

    def get_vendor_name(self, obj):
        vendor = obj.booking.turf.vendor
        return vendor.venuename if vendor else None

    def get_vendor_id(self, obj):
        vendor = obj.booking.turf.vendor
        return vendor.vendor_id if vendor else None

class VendorEarningsSerializer(serializers.Serializer):
    vendor_id = serializers.CharField()
    vendor_name = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    txn_count = serializers.IntegerField()

# ------------------Banner Serializer------------------
from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Turf, TurfBanner, TurfGallery, Ground, Slot, Booking, Payment, AdminUser, HomepageBanner

class HomepageBannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = HomepageBanner
        fields = "__all__"

# ------------------Favorite Turf Serializer------------------
from .models import FavoriteTurf

class FavoriteTurfSerializer(serializers.ModelSerializer):
    turf = TurfSerializer(read_only=True)

    class Meta:
        model = FavoriteTurf
        fields = ["id", "user", "turf", "created_at"]


# ------------------Event Serializer------------------
from .models import Event

class EventSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(use_url=True, required=False, allow_null=True)
    price = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id", "title", "category", "location", "address",
            "organized_by", "start_date", "end_date", "start_time",
            "end_time", "amount", "is_free", "image", "agenda",
            "vips", "status", "is_active", "bg_color", "total_seats", "booked_seats", "created_at", "price"
        ]

    def get_price(self, obj):
        if obj.is_free or obj.amount == 0:
            return "Free"
        return f"₹{int(obj.amount)}"

from .models import EventReview

class EventReviewSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source='event.title', read_only=True)
    user_id = serializers.UUIDField(source='user.id', read_only=True, allow_null=True)
    
    class Meta:
        model = EventReview
        fields = ['id', 'event', 'event_title', 'user', 'user_id', 'name', 'rating', 'text', 'created_at']