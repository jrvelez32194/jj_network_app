from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from enum import Enum

# ------------------------------
# 🚀 Network state enum
# ------------------------------
class ConnectionState(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"
    SPIKING = "SPIKING"

# ------------------------------
# 🚀 Billing status enum
# ------------------------------
class BillingStatus(str, Enum):
    PAID = "PAID"        # normal access
    UNPAID = "UNPAID"    # overdue but still open
    LIMITED = "LIMITED"  # throttled speed
    CUTOFF = "CUTOFF"    # fully blocked


# ===============================
# 🚀 Clients
# ===============================
class ClientCreate(BaseModel):
    name: str
    messenger_id: str
    group_name: Optional[str] = None
    connection_name: Optional[str] = None
    state: Optional[ConnectionState] = ConnectionState.UNKNOWN

    # 🔥 Billing fields
    billing_date: Optional[date] = None   # replaced billing_day, month, year
    status: Optional[BillingStatus] = BillingStatus.PAID
    speed_limit: Optional[str] = "unlimited"
    amt_monthly: Optional[float] = 0.0   # ✅ new column


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    messenger_id: Optional[str] = None
    group_name: Optional[str] = None
    connection_name: Optional[str] = None
    state: Optional[ConnectionState] = None

    # 🔥 Billing fields
    billing_date: Optional[date] = None
    status: Optional[BillingStatus] = None
    speed_limit: Optional[str] = None
    amt_monthly: Optional[float] = None  # ✅ new column


class ClientResponse(BaseModel):
    id: int
    name: Optional[str] = None
    messenger_id: Optional[str] = None
    group_name: Optional[str] = None
    connection_name: Optional[str] = None
    state: Optional[ConnectionState] = None

    # 🔥 Billing fields
    billing_date: Optional[date] = None
    status: Optional[BillingStatus] = None
    speed_limit: Optional[str] = None
    amt_monthly: Optional[float] = None  # ✅ new column

    class Config:
        orm_mode = True


# ===============================
# 🚀 Templates
# ===============================
class TemplateBase(BaseModel):
    title: str
    content: str


class TemplateCreate(TemplateBase):
    pass


class TemplateUpdate(TemplateBase):
    pass


class TemplateResponse(TemplateBase):
    id: int

    class Config:
        orm_mode = True


# ===============================
# 🚀 Message Logs
# ===============================
class MessageLogResponse(BaseModel):
    id: int
    client_id: int
    template_id: Optional[int]
    status: str
    created_at: datetime
    sent_at: Optional[datetime]

    client: Optional[ClientResponse] = None
    template: Optional[TemplateResponse] = None

    class Config:
        orm_mode = True
