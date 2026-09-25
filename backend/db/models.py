"""
Database ORM Models
====================
SQLAlchemy models for User, RiskProfile, Portfolio, Holding, and Transaction.
"""

import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship

from backend.db.database import Base


class User(Base):
    """User account model."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    risk_profile = relationship("RiskProfile", back_populates="user", uselist=False)
    portfolios = relationship("Portfolio", back_populates="user")


class RiskProfile(Base):
    """
    Stores the user's risk assessment results.

    Fields:
        subjective_score: Score from the 10-question quiz (1–10).
        objective_score: Score from financial capacity analysis (1–10).
        composite_score: Blended final risk score (1–10).
        risk_band: Text label (e.g., "Balanced").
        quiz_answers: JSON blob of all individual answers for audit trail.
        objective_inputs: JSON blob of income, expenses, assets, employment type.
        time_horizon_years: Investment horizon in years.
        uses_isa: Whether the user plans to invest via an ISA.
    """
    __tablename__ = "risk_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    subjective_score = Column(Float, nullable=False)
    objective_score = Column(Float, nullable=False)
    composite_score = Column(Float, nullable=False)
    risk_band = Column(String, nullable=False)
    quiz_answers = Column(JSON, nullable=False)
    objective_inputs = Column(JSON, nullable=False)
    time_horizon_years = Column(Integer, nullable=False)
    uses_isa = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="risk_profile")


class Portfolio(Base):
    """
    A user's investment portfolio with target allocations and metadata.
    """
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, default="My Portfolio")
    risk_score = Column(Float, nullable=False)
    target_allocations = Column(JSON, nullable=False)  # {asset_class: weight}
    selected_asset_classes = Column(JSON, nullable=False)  # [asset_class, ...]
    investment_amount = Column(Float, nullable=False)
    monthly_contribution = Column(Float, default=0.0)
    uses_isa = Column(Boolean, default=False)
    expected_return = Column(Float, nullable=True)
    expected_volatility = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    alpha = Column(Float, nullable=True)  # Excess return over risk-free
    total_return_pct = Column(Float, default=0.0)  # Marked-to-market return on net contributions
    cash_gbp = Column(Float, default=0.0)  # Uninvested cash held in the portfolio
    net_contributions = Column(Float, default=0.0)  # Deposits minus withdrawals, GBP
    last_valued_at = Column(DateTime, nullable=True)  # When prices were last marked
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="portfolios")
    holdings = relationship("Holding", back_populates="portfolio")
    transactions = relationship("Transaction", back_populates="portfolio")


class Holding(Base):
    """
    A single ETF position within a portfolio.
    """
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    ticker = Column(String, nullable=False)
    asset_class = Column(String, nullable=False)
    quantity = Column(Float, nullable=False, default=0.0)  # Units held
    average_cost = Column(Float, nullable=False, default=0.0)  # GBP per unit (section 104 pool)
    target_weight = Column(Float, nullable=False)
    current_weight = Column(Float, nullable=True)
    current_price = Column(Float, nullable=True)  # Last GBP price per unit
    price_as_of = Column(DateTime, nullable=True)  # Market date of current_price
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)

    portfolio = relationship("Portfolio", back_populates="holdings")


class Transaction(Base):
    """
    Record of buy/sell/rebalance transactions.
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    ticker = Column(String, nullable=False)
    action = Column(String, nullable=False)  # "buy" | "sell" | "deposit" | "dividend"
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    value = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    cost = Column(Float, default=0.0)  # Trading cost in GBP
    realised_gain = Column(Float, default=0.0)  # GBP, average-cost basis (sells only)
    notes = Column(String, nullable=True)

    portfolio = relationship("Portfolio", back_populates="transactions")
