from typing import Annotated, TypedDict, List, Dict, Any
# pyrefly: ignore [missing-import]
from langchain_core.messages import BaseMessage
# Import add_messages khusus dari LangGraph
# pyrefly: ignore [missing-import]
from langgraph.graph.message import add_messages

class B2BNegotiationState(TypedDict):
    # REVISI UTAMA: Gunakan add_messages, bukan operator.add
    messages: Annotated[list[BaseMessage], add_messages]
    
    # Data input dari User/Frontend
    requested_discount: float
    project_metrics: Dict[str, float]
    rab_items: List[Dict[str, Any]]
    
    # Data output dari Node Guardrail
    is_off_topic: bool
    
    # Data output dari Node Pricing (MAUT & MBA)
    maut_allowed_discount: float
    mba_cross_sell_opportunities: List[Dict[str, Any]]

    # Data pendukung untuk Vision Node (Ekstraksi RAB)
    uploaded_file_bytes: bytes | None
    uploaded_file_mime_type: str | None

    # Schema Pengunci Deal dari Clien ya
    is_deal_reached: bool
    final_agreed_discount: float
    invoice_data: Dict[str, Any] | None