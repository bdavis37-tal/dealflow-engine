"""M&A Financial Modeling Engine — core computation package."""
from .financial_engine import run_deal
from .models import DealInput, DealOutput


def round_financial_output(obj, decimals=6):
    """
    Recursively round all float values in a Pydantic model or dict to
    eliminate IEEE 754 floating-point precision noise at the output boundary.

    Uses 6 significant decimal places by default — enough for financial
    accuracy while eliminating 10+ decimal place artifacts like
    0.12300000000000001 → 0.123.
    """
    if isinstance(obj, float):
        return round(obj, decimals)
    if isinstance(obj, dict):
        return {k: round_financial_output(v, decimals) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_financial_output(item, decimals) for item in obj]
    if hasattr(obj, "model_dump"):
        return round_financial_output(obj.model_dump(), decimals)
    return obj


__all__ = ["run_deal", "DealInput", "DealOutput", "round_financial_output"]
