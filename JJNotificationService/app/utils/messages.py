import logging
logger = logging.getLogger("billing")

# --- Default Client Messages ---
THROTTLE_NOTICE_TEMPLATE = """\
NOTICE OF THROTTLE

Dear Valued Client,

This is to inform you that today marks your 4th day of unpaid balance.

As part of our policy, your internet connection will be throttled within 1 hour if payment is not received.

Please settle your account immediately to avoid reduced internet speed.
Send your proof of payment to our official page or contact number for verification.

If payment has been made, restoration will come after 5–10 minutes.

Thank you for your cooperation and continued trust.

Best regards,
JJ Internet Service
"""

DISCONNECTION_NOTICE_TEMPLATE = """\
NOTICE OF SERVICE DISCONNECTION

Dear Valued Client,

This is to inform you that your account has been unpaid for 7 days.

If payment is not settled, your internet connection will be disconnected within 1 hour as per our policy.

Please make your payment immediately to avoid service interruption and send your proof of payment to our official page or contact number for confirmation.

If payment has been made, restoration will come after 5–10 minutes.

We appreciate your immediate attention to this matter.

Sincerely,
JJ Internet Service
"""

DUE_NOTICE_TEMPLATE = """\
Good day {client_display}!

This is a friendly reminder that your internet account payment is due on {due_date}, amounting to {amount:,.2f} pesos only.

Please note the following:

If payment is not received within 4 days, your connection may be throttled, resulting in slower internet speeds.

If payment remains unpaid after 7 days, your internet service will be disconnected. Once payment is made, your connection will be restored.

If you have already made the payment, kindly disregard this message.

Payment Options:
📱 GCash
• Number: 09272613343
• Name: John Rexcy Velez
Note: Please send me a screenshot of your gcash transaction for us to verify.

🏡 Cash Payment
You may also pay in person at {payment_location}.

Thank you from JJ Internet Service.
"""

# --- Admin Notifications (for connect_name == "ADMIN") ---
ADMIN_THROTTLE_NOTICE = """\
⚙️ ADMIN NOTICE: CLIENT THROTTLING ALERT

Client has reached 4 days of unpaid balance.
Throttle will be applied within 1 hour if payment is not confirmed.

Client: {client_display}
Group: {group_name}
Due Date: {due_date}
Amount: {amount:,.2f} pesos
"""

ADMIN_DISCONNECTION_NOTICE = """\
⚙️ ADMIN NOTICE: CLIENT DISCONNECTION ALERT

Client account is now 7 days overdue.
Disconnection will occur within 1 hour if payment is still not made.

Client: {client_display}
Group: {group_name}
Due Date: {due_date}
Amount: {amount:,.2f} pesos
"""

ADMIN_DUE_REMINDER = """\
📢 ADMIN REMINDER: CLIENT BILLING NOTICE SENT

Client: {client_display}
Group: {group_name}
Due Date: {due_date}
Amount: {amount:,.2f} pesos

A due notice has been sent to the client. Monitor for payment confirmation.
"""

# =====================================================
# ✅ Safe Message Formatter
# =====================================================
def safe_format(template: str, **kwargs) -> str:
    """Safely formats message templates to prevent crashes on format errors."""
    try:
        return template.format(**kwargs)
    except Exception as e:
        logger.error(
            f"⚠️ Message format error: {e} | Template: {template[:100]}... | Data: {kwargs}"
        )
        return template  # Return unformatted message to avoid breaking billing


# =====================================================
# ✅ Get messages by group/location
# =====================================================
def get_messages(group_name: str, connect_name: str = None):
    """Return customized notices depending on client group and role."""
    group_name_clean = (group_name or "").upper().strip()
    connect_name_clean = (connect_name or "").upper().strip()

    payment_location = "Sitio Coronado, Malalag Cogon"  # Default G1
    if group_name_clean in ["G2", "ALIWANAY", "SURALLAH", "VELEZ"]:
        payment_location = "Sitio Aliwanay, Naci, Surallah, at Velez Compound"

    # 🧩 Admin messages
    if connect_name_clean == "ADMIN":
        return {
            "THROTTLE_NOTICE": ADMIN_THROTTLE_NOTICE,
            "DISCONNECTION_NOTICE": ADMIN_DISCONNECTION_NOTICE,
            "DUE_NOTICE": ADMIN_DUE_REMINDER,
            "PAYMENT_LOCATION": payment_location,
        }

    # 👥 Client messages
    return {
        "THROTTLE_NOTICE": THROTTLE_NOTICE_TEMPLATE,
        "DISCONNECTION_NOTICE": DISCONNECTION_NOTICE_TEMPLATE,
        "DUE_NOTICE": DUE_NOTICE_TEMPLATE,
        "PAYMENT_LOCATION": payment_location,
    }
