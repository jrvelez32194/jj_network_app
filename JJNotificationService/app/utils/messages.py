# messages.py

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

Thank you from @JJNet.
"""


# --- Function to get the proper messages based on group/location ---
def get_messages(group_name: str):
  """Return customized notices depending on client location."""

  # Default values (G1)
  payment_location = "Sitio Coronado, Malalag Cogon"

  if "Aliwanay" in group_name or "Surallah" in group_name or "Velez" in group_name:
    payment_location = "Sitio Aliwanay, Naci, Surallah, at Velez Compound"

  # Inject location into DUE_NOTICE
  due_notice = DUE_NOTICE_TEMPLATE.format(
    due_date="{due_date}",
    amount="{amount}",
    payment_location=payment_location,
  )

  return {
    "THROTTLE_NOTICE": THROTTLE_NOTICE_TEMPLATE,
    "DISCONNECTION_NOTICE": DISCONNECTION_NOTICE_TEMPLATE,
    "DUE_NOTICE": due_notice,
  }
