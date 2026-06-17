import secrets
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import ValidationError

def generate_otp():
    return str(secrets.randbelow(900000) + 100000)

def send_email_otp(email, otp):
    subject = "Your OTP Verification Code - Adugalam"
    
    message = f"""
Your OTP for account verification is:

{otp}

🔒 Do not share with anyone.

If you did not request this, please ignore this email.

- Adugalam Security Team
"""

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False
        )
    except Exception as e:
        raise ValidationError(f"Email service failed: {str(e)}")


def send_vendor_approval_email(email, vendor, password):
    """
    Send a professional approval notification to the vendor.
    `vendor` is a Vendor model instance.
    """
    subject = "🎉 Congratulations! Your Vendor Application is Approved – Adugalam"

    message = f"""
Dear {vendor.ownername},

We are thrilled to let you know that your vendor application for Adugalam has been
reviewed and APPROVED!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  YOUR LOGIN DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Email Address : {email}
  Password      : {password}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NEXT STEPS
----------
1. Log in to the Adugalam Vendor Portal using your registered email address.
2. Use your Vendor ID ({vendor.vendor_id}) to set up and manage your turf listings.
3. Add your turf details, images, available time slots, and pricing.
4. Once your turf is listed, customers can start discovering and booking your venue!

NEED HELP?
----------
If you have any questions or need assistance getting started, feel free to
reach out to our support team at support@adugalam.com or reply to this email.

We look forward to a successful partnership with you.

Warm regards,
The Adugalam Team
www.adugalam.com
"""

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False
        )
    except Exception as e:
        print(f"[Adugalam] Vendor approval email failed for {email}: {str(e)}")


def send_vendor_rejection_email(email, vendor):
    """
    Send a polite rejection notification to the vendor.
    `vendor` is a Vendor model instance.
    """
    subject = "Update on Your Vendor Application – Adugalam"

    message = f"""
Dear {vendor.ownername},

Thank you for your interest in partnering with Adugalam and for taking the time
to submit your vendor application for "{vendor.venuename}".

After careful review, we regret to inform you that we are unable to approve your
application at this time.

This decision may be due to incomplete information, location coverage limitations,
or other operational requirements. We encourage you to re-apply in the future once
the concerns have been addressed.

WHAT YOU CAN DO
---------------
- Review our vendor registration guidelines on our website.
- Ensure all details (venue info, documents, contact details) are complete and accurate.
- Re-submit your application at any time via the Adugalam website.

If you believe this decision was made in error or would like more information,
please contact our support team at support@adugalam.com.

We appreciate your understanding and hope to work with you in the future.

Best regards,
The Adugalam Team
www.adugalam.com
"""

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False
        )
    except Exception as e:
        print(f"[Adugalam] Vendor rejection email failed for {email}: {str(e)}")


def send_account_deletion_approved_email(email, name):
    """Notify user their account deletion has been approved — account deleted, can re-register fresh."""
    subject = "Your Account Has Been Deleted – Adugalam"
    message = f"""Dear {name},

Your account deletion request has been APPROVED by the Adugalam admin team.

Your account and all associated data have been permanently removed from the Adugalam platform.

WANT TO JOIN AGAIN?
You are always welcome back! You can register fresh at any time with the same or a new email.
Visit: www.adugalam.com/signup

If this was a mistake, please contact us at support@adugalam.com.

Warm regards,
The Adugalam Team
"""
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
    except Exception as e:
        print(f"[Adugalam] Deletion approved email failed for {email}: {str(e)}")


def send_account_deletion_rejected_email(email, name):
    """Notify user their account deletion request was rejected — account restored, can login."""
    subject = "Your Account Deletion Request Has Been Rejected – Adugalam"
    message = f"""Dear {name},

Your account deletion request has been REJECTED by the Adugalam admin team.

YOUR ACCOUNT IS ACTIVE AGAIN
Your account has been fully restored. You can log in at any time:
Visit: www.adugalam.com/login

If you still wish to delete your account, please contact us at support@adugalam.com.

Best regards,
The Adugalam Team
"""
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
    except Exception as e:
        print(f"[Adugalam] Deletion rejected email failed for {email}: {str(e)}")



