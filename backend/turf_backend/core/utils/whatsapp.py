import requests
from django.conf import settings


def send_whatsapp_message(phone, vendor_id, location, status="Pending"):
    try:
        # ✅ Format phone number
        phone = str(phone)
        if not phone.startswith("91"):
            phone = "91" + phone

        # ✅ Select Template based on status
        if status == "Approved":
            template = f"1720835~Vendor~{vendor_id}~{location}"
        elif status in ["Rejected", "Inactive"]:
            template = f"1720836~Vendor~{vendor_id}~{location}"
        else:
            template = f"1717530~Vendor~{vendor_id}~{location}"

        payload = {
            "apiver": "1.0",
            "user": {"userid": settings.WHATSAPP_USER_ID},
            "whatsapp": {
                "ver": "2.0",
                "dlr": {"url": ""},
                "messages": [
                    {
                        "coding": 1,
                        "id": "15",
                        "msgtype": 1,
                        "templateinfo": template,
                        "addresses": [
                            {
                                "seq": "1",
                                "to": phone,
                                "from": settings.WHATSAPP_FROM_NUMBER,
                                "tag": f"vendor_id:{vendor_id}",
                            }
                        ],
                    }
                ],
            },
        }

        headers = {
            "x-client-id": settings.WHATSAPP_CLIENT_ID,
            "x-client-password": settings.WHATSAPP_CLIENT_PASSWORD,
            "Content-Type": "application/json",
        }

        response = requests.post(
            settings.WHATSAPP_API_URL, headers=headers, json=payload, timeout=10
        )

        return {"status_code": response.status_code, "response": response.text}

    except Exception as e:
        return {"error": str(e)}
