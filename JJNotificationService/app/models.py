from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, \
  Enum, Date, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
import enum
from datetime import datetime, date

Base = declarative_base()


# ------------------------------
# 🚀 Network state enum
# ------------------------------
class ConnectionState(str, enum.Enum):
    UP = "UP"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"  # default state


# ------------------------------
# 🚀 Billing status enum
# ------------------------------
class BillingStatus(str, enum.Enum):
    PAID = "PAID"
    UNPAID = "UNPAID"
    LIMITED = "LIMITED"
    CUTOFF = "CUTOFF"


# ===============================
# 🚀 Clients
# ===============================
class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    messenger_id = Column(String, unique=True, nullable=False)
    group_name = Column(String, nullable=True)
    connection_name = Column(String, nullable=True)  # 🔑 link to MikroTik comment

    # Network state
    state = Column(Enum(ConnectionState), default=ConnectionState.UNKNOWN, nullable=False)

    # Billing fields
    status = Column(Enum(BillingStatus), default=BillingStatus.PAID, nullable=False)
    speed_limit = Column(String, default="unlimited")  # ✅ default client bandwidth is open/unli
    amt_monthly = Column(Float, nullable=False, default=1000.0)

    # 🔥 Single recurring billing date
    billing_date = Column(Date, nullable=True, default=date.today)  # replaced day+month+year


# ===============================
# 🚀 Templates
# ===============================
class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)


# ===============================
# 🚀 Message Logs
# ===============================
class MessageLog(Base):
    __tablename__ = "message_logs"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    template_id = Column(Integer, ForeignKey("templates.id"))
    status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # when row created
    sent_at = Column(DateTime(timezone=True), nullable=True)  # when actually sent

    client = relationship("Client")
    template = relationship("Template")
