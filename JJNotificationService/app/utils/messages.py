import logging

logger = logging.getLogger("billing")

# =====================================================
# --- Default Client Messages ---
# =====================================================

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

THROTTLE_NOTICE_TEMPLATE_TAGALOG = """\
NOTICE OF THROTTLE

Mahal na Kliyente,

Nais po naming ipaalam na ngayong araw ay ika-4 na araw na ng inyong hindi nabayarang balanse.

Alinsunod sa aming patakaran, ang inyong internet connection ay maaaaring ma-throttle sa loob ng 1 oras** kung hindi pa rin makatanggap ng bayad.

Hinihikayat po namin kayong agarang mag-settle ng inyong account upang maiwasan ang pagbaba ng internet speed.
Paki-send po ang inyong proof of payment sa aming official page o contact number para sa beripikasyon.

Kung nakapagbayad na po kayo, ang restoration ay matatapos sa loob ng 5–10 minuto.

Maraming salamat po sa inyong kooperasyon at patuloy na pagtitiwala.

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

DISCONNECTION_NOTICE_TEMPLATE_TAGALOG = """\
NOTICE OF SERVICE DISCONNECTION

Mahal na Kliyente,

Ipinapaalam po namin na ang inyong account ay 7 araw nang hindi nababayaran.

Alinsunod sa aming patakaran, kung hindi pa rin maisasagawa ang bayad, ang inyong internet connection ay maaaaring ma-disconnect sa loob ng 1 oras.

Hinihikayat po namin kayong agad na mag-settle ng inyong bayad upang maiwasan ang ganap na pagkaputol ng serbisyo.
Paki-send po ang inyong proof of payment sa aming official page o contact number para sa kumpirmasyon.

Kung nakapagbayad na po kayo, ang restoration ay matatapos sa loob ng 5–10 minuto.

Lubos po naming pinahahalagahan ang inyong maagap na aksyon sa usaping ito.

JJ Internet Service
"""

DUE_NOTICE_TEMPLATE = """\
Magandang araw, {client_display}!

Pinaaalalahanan po namin kayo na ang inyong bayad para sa internet account ay nakatakdang mag-due sa {due_date}, na may halagang {amount:,.2f} pesos.

Mahalagang Paalala:

• Kung hindi po matanggap ang bayad sa loob ng 4 na araw, ang inyong koneksyon ay maaaring ma-throttle at makaranas ng mabagal na internet speed.

• Kapag nanatiling hindi nababayaran pagkalipas ng 7 araw, ang inyong internet service ay ma-di-disconnect. Ang koneksyon ay ibabalik pagkatapos maisagawa ang bayad.

• Kung nakapagbayad na po kayo, maaari n’yo nang balewalain ang mensaheng ito.

Paraan ng Pagbabayad:

📱 GCash
• Number: 09272613343
• Name: John Rexcy Velez
Paki-send po ang screenshot ng inyong GCash transaction para sa beripikasyon.

🏡 Cash Payment
Maaari rin po kayong magbayad nang personal sa {payment_location}.

Maraming salamat po.
JJ Internet Service
"""

DUE_NOTICE_TEMPLATE_TAGALOG = """\
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
Note: Please send me a screenshot of your GCash transaction for us to verify.

🏡 Cash Payment
You may also pay in person at {payment_location}.

Thank you from JJ Internet Service.
"""

# =====================================================
# --- Client SPIKE Message ---
# =====================================================
SPIKE_NOTICE_TEMPLATE = """\
⚠️ NETWORK SPIKE DETECTED

Dear Valued Client,

We detected unusual connection instability for your network:
{connect_name}-{group_name}-SPIKE-{state}

Our system has automatically marked your connection as DOWN temporarily to protect stability.

Please monitor your connection. Restoration will be automatic once stable.

Thank you for your understanding.

– JJ Internet Service
"""

# =====================================================
# --- Admin Notifications ---
# =====================================================

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

ADMIN_SPIKE_NOTICE = """\
🚨 ADMIN ALERT: SPIKE DETECTED

Connection: {connect_name}-{group_name}-SPIKE-{state}

Multiple flips detected (3+ in 3 minutes).
Marked as DOWN to prevent instability.

Notify affected vendo or private owner as applicable.
"""

# =====================================================
# ✅ Safe Formatter
# =====================================================
def safe_format(template: str, **kwargs) -> str:
    try:
        return template.format(**kwargs)
    except Exception as e:
        logger.error(f"⚠️ Message format error: {e} | Template: {template[:100]}... | Data: {kwargs}")
        return template


# =====================================================
# ✅ Message Fetcher (with fallback)
# =====================================================
def get_messages(group_name: str, connect_name: str = None):
    """
    Returns the message templates for a specific group or connect type.
    Provides SPIKE, THROTTLE, DISCONNECTION, and DUE messages.
    Includes fallback defaults if not found.
    """
    group_name_clean = (group_name or "").upper().strip()
    connect_name_clean = (connect_name or "").upper().strip()

    # Default payment location (G1)
    payment_location = "Sitio Coronado, Malalag Cogon"
    if group_name_clean in ["G2", "ALIWANAY", "SURALLAH", "VELEZ"]:
        payment_location = "Sitio Aliwanay, Naci, Surallah, at Velez Compound"

    # 🧩 ADMIN messages
    if connect_name_clean == "ADMIN":
        return {
            "THROTTLE_NOTICE": ADMIN_THROTTLE_NOTICE,
            "DISCONNECTION_NOTICE": ADMIN_DISCONNECTION_NOTICE,
            "DUE_NOTICE": ADMIN_DUE_REMINDER,
            "SPIKE_NOTICE": ADMIN_SPIKE_NOTICE,
            "PAYMENT_LOCATION": payment_location,
        }

    # 👥 CLIENT messages (PRIVATE, vendo, etc.)
    return {
        "THROTTLE_NOTICE": THROTTLE_NOTICE_TEMPLATE_TAGALOG,
        "DISCONNECTION_NOTICE": DISCONNECTION_NOTICE_TEMPLATE_TAGALOG,
        "DUE_NOTICE": DUE_NOTICE_TEMPLATE_TAGALOG,
        "SPIKE_NOTICE": SPIKE_NOTICE_TEMPLATE,
        "PAYMENT_LOCATION": payment_location,
    }


# =====================================================
# ✅ Safe fallback accessor
# =====================================================
def get_message_template(msgs: dict, key: str):
    """
    Safe lookup for a message key from the given message dict.
    Falls back to a neutral notice if missing.
    """
    if key in msgs:
        return msgs[key]
    logger.warning(f"⚠️ Missing message template for key: {key}, using fallback.")
    return "⚠️ NOTICE: Template unavailable. Please contact administrator."
