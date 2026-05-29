import logging
# pyrefly: ignore [missing-import]
from langgraph.graph import StateGraph, START, END
from app.agents.state import B2BNegotiationState

# Import fungsionalitas dari masing-masing node
from app.agents.nodes.gateway_node import execute_gateway_node
from app.agents.nodes.vision_node import execute_vision_node
from app.agents.nodes.pricing_node import execute_pricing_node
from app.agents.nodes.negotiator_node import execute_negotiator_node
from app.agents.nodes.invoice_node import execute_invoice_node
# pyrefly: ignore [missing-import]
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

# 1. Inisialisasi Graph dengan State
graph_builder = StateGraph(B2BNegotiationState)

# 2. Daftarkan Semua Node
graph_builder.add_node("gateway_node", execute_gateway_node)
graph_builder.add_node("vision_node", execute_vision_node)
graph_builder.add_node("pricing_node", execute_pricing_node)
graph_builder.add_node("negotiator_node", execute_negotiator_node)
graph_builder.add_node("invoice_node", execute_invoice_node)

# 3. Fungsi Logika Persimpangan (Conditional Routing)
def route_from_gateway(state: B2BNegotiationState):
    """Menentukan arah aliran setelah melalui penjagaan Gateway."""
    logger.info("🚦 [ROUTER - GATEWAY] Mengevaluasi persimpangan rute...")
    
    if state.get("is_off_topic", False):
        logger.warning("   ⛔ Topik melenceng! Rute diputus dan obrolan dihentikan (END).")
        return END 
    
    # PERCABANGAN CERDAS
    if state.get("uploaded_file_bytes") is not None:
        logger.info("   📄 Ada file RAB yang menunggu dibaca. Mengarahkan rute ke ➔ Vision Node.")
        return "vision_node"
        
    logger.info("   💬 Tidak ada file RAB. Potong kompas, mengarahkan rute ke ➔ Pricing Node.")
    return "pricing_node"

# 4. Rajut Alurnya
logger.info("🕸️ [GRAPH BUILDER] Merajut alur StateGraph B2B QHome...")
graph_builder.add_edge(START, "gateway_node")

graph_builder.add_conditional_edges(
    "gateway_node",
    route_from_gateway,
    {
        "vision_node": "vision_node",
        "pricing_node": "pricing_node", 
        END: END 
    }
)

graph_builder.add_edge("vision_node", "pricing_node")
graph_builder.add_edge("pricing_node", "negotiator_node")

# 5. Fungsi Router dari Negotiator
def route_from_negotiator(state: B2BNegotiationState):
    """Menentukan apakah transaksi perlu dikunci atau negosiasi masih berlanjut."""
    logger.info("🚦 [ROUTER - NEGOTIATOR] Mengevaluasi hasil negosiasi akhir...")
    
    if state.get("is_deal_reached", False):
        logger.info("   🎉 DEAL TERCAPAI! Meneruskan alur ke ➔ Invoice Node untuk penguncian data.")
        return "invoice_node"
        
    logger.info("   ⏳ Negosiasi berlanjut (Belum Deal). Menghentikan siklus graph sementara (END).")
    return END

graph_builder.add_conditional_edges(
    "negotiator_node",
    route_from_negotiator,
    {
        "invoice_node": "invoice_node",
        END: END,
    }
)

graph_builder.add_edge("invoice_node", END)

# 6. Kompilasi Graf
memory = MemorySaver()
app_graph = graph_builder.compile(checkpointer=memory)
logger.info("✅ [GRAPH BUILDER] Arsitektur LangGraph berhasil dikompilasi dengan MemorySaver.")