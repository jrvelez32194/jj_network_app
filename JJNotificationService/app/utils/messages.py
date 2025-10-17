import logging
logger = logging.getLogger("billing")

# --- Default Messages ---
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
Good day!

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

# =====================================================
# ✅ Safe Message Formatter
# =====================================================
def safe_format(template: str, **kwargs) -> str:
    """
    Safely formats message templates to prevent crashes when placeholders
    or format types are incorrect (e.g., '{amount:.2f}' on a string).
    """
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
def get_messages(group_name: str):
    """Return customized notices depending on client location."""
    group_name_clean = (group_name or "").upper().strip()

    payment_location = "Sitio Coronado, Malalag Cogon"  # default G1
    if group_name_clean in ["G2", "ALIWANAY", "SURALLAH", "VELEZ"]:
      payment_location = "Sitio Aliwanay, Naci, Surallah, at Velez Compound"

    return {
      "THROTTLE_NOTICE": THROTTLE_NOTICE_TEMPLATE,
      "DISCONNECTION_NOTICE": DISCONNECTION_NOTICE_TEMPLATE,
      "DUE_NOTICE": DUE_NOTICE_TEMPLATE,  # keep placeholders intact
      "PAYMENT_LOCATION": payment_location,  # pass separately
    }
