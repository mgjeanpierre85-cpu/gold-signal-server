from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

# Tabla para señales (GOLD y SILVER)
class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)  # XAUUSD o XAGUSD
    signal_type = Column(String)         # ML_LONG o ML_SHORT
    price = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Tabla para velas
class Candle(Base):
    __tablename__ = "candles"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    timeframe = Column(String)           # ej: "1m"
    timestamp = Column(DateTime, default=datetime.utcnow)

# Tabla para SL/TP dinámicos
class SLTP(Base):
    __tablename__ = "sltp"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    sl = Column(Float)
    tp = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Tabla para cierres de operaciones
class Close(Base):
    __tablename__ = "closes"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    result = Column(Float)               # ganancia o pérdida
    reason = Column(String)              # TP, SL, reverse, etc.
    timestamp = Column(DateTime, default=datetime.utcnow)
