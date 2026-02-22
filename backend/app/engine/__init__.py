"""M&A Financial Modeling Engine — core computation package."""
from .financial_engine import run_deal
from .models import DealInput, DealOutput

__all__ = ["run_deal", "DealInput", "DealOutput"]
