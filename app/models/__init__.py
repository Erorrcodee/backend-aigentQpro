# app/models/__init__.py

# Import Base terlebih dahulu
from .base import Base

# Import semua model agar terdaftar di metadata SQLAlchemy
from .users import User
from .product_catalog import Product
from .system_configs import SystemConfig
from .b2b_projects import B2BProject
from .agent_traces import AgentTrace
from .invoice import Invoice
from .maut_weight_config import MautWeightConfig
from .analytics import AssociationRule

# Baris ini memastikan tidak ada warning "unused import" di linter
__all__ = [
    "Base",
    "User",
    "Product",
    "SystemConfig",
    "B2BProject",
    "AgentTrace",
    "Invoice",
    "MautWeightConfig",
    "AssociationRule",
]