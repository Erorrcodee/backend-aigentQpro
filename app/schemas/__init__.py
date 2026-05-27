# app/schemas/__init__.py

from .common_schema import BaseResponse, TokenResponse, ErrorResponse
from .llm_structured import VisionExtractionResult, ExtractedItem, CrossSellResult, RecommendedProduct
from .b2b_schema import B2BProjectResponse, ChatMessageRequest, ChatMessageResponse, ProjectItemDetail
from .admin_schema import ConfigUpdateRequest, AdminApprovalRequest, ROIAnalyticsResponse
from .user_schema import UserCreate, UserResponse
from .product_schema import ProductCreate, ProductResponse
from .rab_schema import RABItem, RABExtractionResult

# Mencegah warning unused imports
__all__ = [
    "BaseResponse", 
    "TokenResponse", 
    "ErrorResponse",
    "VisionExtractionResult", 
    "ExtractedItem", 
    "CrossSellResult", 
    "RecommendedProduct",
    "B2BProjectResponse", 
    "ChatMessageRequest", 
    "ChatMessageResponse", 
    "ProjectItemDetail",
    "ConfigUpdateRequest", 
    "AdminApprovalRequest", 
    "ROIAnalyticsResponse",
    "UserCreate",
    "UserResponse"
    "ProductCreate",
    "ProductResponse"
    "RABItem",
    "RABExtractionResult",
]