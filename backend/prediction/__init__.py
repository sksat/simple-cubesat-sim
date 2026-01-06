"""Contact prediction module."""

from backend.prediction.models import ContactWindow
from backend.prediction.contact_predictor import ContactPredictor

__all__ = ["ContactWindow", "ContactPredictor"]
