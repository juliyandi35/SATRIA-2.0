"""Core services for the SATRIA 2.0 local intelligence environment."""

from .data_service import DataRepository, DataValidationError

__all__ = ["DataRepository", "DataValidationError"]
