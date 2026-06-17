
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
# pyrefly: ignore [missing-import]
from . import views

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.response import Response
from rest_framework import status
from core.models import AppUser

class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except AppUser.DoesNotExist:
            return Response({"error": "User account no longer exists"}, status=status.HTTP_401_UNAUTHORIZED)

# pyrefly: ignore [missing-import]
from .views import admin_banner_detail, admin_manage_banners, delete_user, get_hit_stats, get_users, list_homepage_banners, record_hit, update_user, user_notifications, vendor_my_turfs, vendor_profile, vendor_requests, user_retire_request, admin_retire_requests, admin_retire_action, restore_account, list_events, admin_events, admin_event_detail, book_event

from core.views import (
    booking_detail,
    booking_summary,
    vendor_create,
    delete_vendor,
    get_vendor,
    location_list,
    select_location,
    send_email_otp_view,
    test_select_location,
    turf_slots,
    user_all_bookings,
    user_latest_booking,
    vendor_status_toggle,
    verify_email_otp_view,
    create_account_view,
    login_view,
    home,
    send_reset_otp,
    list_turfs,
    popular_turfs,
    turf_details,
    ground_availability,
    nearby_turfs,
    add_to_cart,
    confirm_booking,
    submit_contact_message,
    list_contact_messages,
    create_payment_order,
    verify_payment,
    turf_games,
    admin_login,
    users_list,
    vendor_requests,
    user_toggle_active,
    turfs_list,
    bookings_list,
    booking_cancel,
    payments_list,
    vendors_list,
    vendor_approve,
    vendor_reject,
    turfs_approve,
    turfs_reject,
    vendor_create_slots,
    vendor_dashboard,
    vendor_list_slots,
    vendor_list_turfs,
    vendor_add_turf,
    vendor_booking_list,
    vendor_update_booking_status,
    vendor_list_discounts,
    vendor_create_discount,
    vendor_list,
    admin_add_turf,
    update_turf_priority,
    vendor_set_peak_hour,
    vendor_set_bulk_peak_hours,
    vendor_delete_peak_hour,
    reset_password,
    change_password,
    update_user_profile,
    update_vendor_by_code,
    submit_issue,
    admin_issues_list,
    admin_resolve_issue,
    user_notifications,
    admin_forgot_password,
    admin_reset_password,
    vendor_turf_detail,
    vendor_edit_turf,
    vendor_toggle_maintenance,
    admin_get_vendor_turfs,
    admin_set_bulk_peak_hours,
    admin_edit_turf,
    toggle_favorite,
    my_favorite_turfs,
    turf_booked_slots_by_date,
    booking_receipt,
)

urlpatterns = [

    # -------- USER AUTH --------
    path("send-otp/", send_email_otp_view),
    path("verify-otp/", verify_email_otp_view),
    path("signup/", create_account_view),
    path("login/", login_view),
    path("send-reset-otp/", send_reset_otp),
    path("home/", home),
    path("reset-password/", reset_password),
    path("user/change-password/", change_password),
    path("user/profile/", update_user_profile),
    path("token/", TokenObtainPairView.as_view()),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),

    path("turfs/<int:turf_id>/games", turf_games),

    # -------- TURFS --------
    path("turf-slots/", turf_slots, name="turf-slots"),
    path("turfs/", list_turfs),
    path("turfs/popular-turfs/",popular_turfs),
    path("turfs/<int:turf_id>/", turf_details),
    path("grounds/<int:ground_id>/availability/", ground_availability),
    path("turfs/nearby/", nearby_turfs),

    # -------- FAVORITES --------
    path("favorites/toggle/<int:turf_id>/", toggle_favorite),
    path("favorites/me/", my_favorite_turfs),

    # -------- BOOKINGS --------
    path("cart/add/", add_to_cart),
    path("booking/confirm/", confirm_booking),
    path("booking/<int:booking_id>/", booking_detail),
    path("turf/booked-slots/<int:turf_id>/", turf_booked_slots_by_date),
    path("booking/<int:booking_id>/receipt/", booking_receipt),

    # -------- PAYMENTS --------
    path("payment/create-order/", create_payment_order),
    path("payment/verify/", verify_payment),

    # -------- ADMIN --------
    path("admin/login/", admin_login),
    path("admin/forgot-password/send-otp/", admin_forgot_password),
    path("admin/forgot-password/reset/", admin_reset_password),
    path("admin/dashboard/", views.admin_dashboard_main),

    path("admin/vendors/", vendors_list),
    path("vendors/approve/<int:id>/", vendor_approve),
    path("vendors/reject/<int:id>/", vendor_reject),

    path("admin/users/", users_list),
    path("admin/users/<int:user_id>/toggle-active/", user_toggle_active),

    path("admin/turfs/", turfs_list),
    path("turf-slots/", turf_slots),
    
    path("admin/turfs/create/", admin_add_turf),
    path("admin/turfs/<int:turf_id>/priority/",update_turf_priority),
    path("admin/turfs/<int:turf_id>/", admin_edit_turf),


    path("admin/turfs/<int:turf_id>/approve/", turfs_approve),
    path("admin/turfs/<int:turf_id>/reject/", turfs_reject),
    path("booking/<int:booking_id>/", booking_detail),
    path("admin/bookings/", bookings_list),
    path("admin/bookings/<int:booking_id>/cancel/", booking_cancel),

    path("admin/payments/", payments_list),

    # -------- VENDOR MANAGEMENT --------
    path("vendors/", vendor_list),
    path("vendors/pending/", vendor_requests),
    path("vendors/create/", vendor_create),
    path("vendors/id/<int:id>/", delete_vendor),
    path("vendors/code/<str:vendor_id>/", get_vendor),
    path("vendors/update/<str:vendor_id>/", update_vendor_by_code),
    path("vendors/status/<str:vendor_id>/", vendor_status_toggle),

    # -------- VENDOR PANEL --------
    path("vendor/dashboard/", vendor_dashboard),
    path("vendor/turfs/", vendor_list_turfs),
    path("vendor/turfs/create/", vendor_add_turf),

    path("vendor/bookings/", vendor_booking_list),
    path("vendor/bookings/update/", vendor_update_booking_status),

    path("vendor/slots/", vendor_list_slots),
    path("vendor/slots/create/", vendor_create_slots),
    path("vendor/set-peak-hour/", vendor_set_peak_hour),
    path("vendor/set-bulk-peak-hours/", vendor_set_bulk_peak_hours),
    path("vendor/delete-peak/<int:peak_id>/", vendor_delete_peak_hour),
    path("vendor/discounts/", vendor_list_discounts),
    path("vendor/discounts/create/", vendor_create_discount),

    # -----------------------location-----------------------
    path("locations/", location_list),
    path("select-location/", select_location),
    path("test-select-location/", test_select_location),

    #--------------booking status update----------------
    path("booking/summary/<int:booking_id>/", booking_summary),
    path("booking/my-summary/", user_latest_booking),
    path("booking/my-bookings/", user_all_bookings),
    
    # -------- USER ISSUES / SUPPORT ---------
    path("issues/submit/", submit_issue),
    path("admin/issues/", admin_issues_list),
    path("admin/issues/<int:issue_id>/resolve/", admin_resolve_issue),

    #-------------contact---------------------
    path("contact/submit/", submit_contact_message),
    path("contact/list/", list_contact_messages),

    # -------------Bannner Management----------------
    path("banners/", list_homepage_banners),
    path("admin/banners/", admin_manage_banners),
    path("admin/banners/<int:pk>/", admin_banner_detail),

    # ----------------hit----------------------
    # -------- LOVE ADUGALAM --------
    path("hit-stats/", get_hit_stats),
    path("record-hit/", record_hit),

    # -------- EVENTS --------
    path("events/", list_events),
    path("events/<int:event_id>/reviews/", views.event_reviews_list),
    path("admin/events/", admin_events),
    path("admin/events/<int:pk>/", admin_event_detail),
    path("admin/event-reviews/", views.admin_event_reviews),
    path("admin/event-reviews/<int:review_id>/", views.admin_event_reviews),
    path("events/<int:pk>/book/", book_event),

    # ------------usermanagemnet in admin panel----------------
    path("users/", get_users),
    path("users/<uuid:user_id>/", update_user),
    path("users/<uuid:user_id>/delete/", delete_user),
    # ---- User Account Retire ----
    path("user/retire-request/", user_retire_request),
    path("user/restore-account/", restore_account),
    path("admin/retire-requests/", admin_retire_requests),
    path("admin/retire-requests/<uuid:user_id>/action/", admin_retire_action),
    #------- admin payment show---------
    path("payments/report/", views.payments_report),
    #-------- refund---------
    path("admin/bookings/", views.bookings_list),

    path("admin/bookings/<int:booking_id>/",views.admin_refund_booking),
    path("notifications/", user_notifications),
#---- full vendor code -----------
    path("vendor/profile/", vendor_profile),
    path("vendor/my-turfs/", vendor_my_turfs),
    path("vendor/turfs/<int:turf_id>/", vendor_turf_detail),
    path("vendor/turfs/<int:turf_id>/update/", vendor_edit_turf),
    path("vendor/turfs/<int:turf_id>/maintenance/", vendor_toggle_maintenance),
    path("admin/vendor-turfs/<str:vendor_id>/", admin_get_vendor_turfs),
    path("admin/set-peak-hours/", admin_set_bulk_peak_hours),
]





# -------- MEDIA FILES --------
# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)