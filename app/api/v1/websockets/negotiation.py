import json 
import logging
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage

# Import graph yang sudah Anda rakit sebelumnya
from app.agents.graph_builder import app_graph

logger = logging.getLogger(__name__)
ws_router = APIRouter()

# 1. PETA STATUS: Menerjemahkan nama node teknis ke bahasa yang ramah untuk UI Frontend
NODE_STATUS_MAP = {
    "gateway_node": "Menganalisis maksud pesan...",
    "pricing_node": "Mengecek ketersediaan dan kalkulasi harga...",
    "negotiator_node": "Menyusun balasan...",
    "invoice_node": "Menerbitkan dokumen kesepakatan..."
}

@ws_router.websocket("/ws/negotiation")
async def websocket_negotiation_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Klien B2B terhubung ke WebSocket Negosiasi.")

    # ID fallback jika FE tidak mengirimkan conversation_id
    fallback_connection_id = str(uuid.uuid4())

    try:
        while True:
            # 2. Terima input dari user
            data_str = await websocket.receive_text()
            request_data = json.loads(data_str)
            
            # 3. KELOLA MEMORI: Gunakan conversation_id dari FE untuk mempertahankan state LangGraph
            session_id = request_data.get("conversation_id", fallback_connection_id)
            config = {"configurable": {"thread_id": session_id}}

            message = request_data.get("message", "")
            analysis_context = request_data.get("analysis_context", {})

            # 4. RAKIT INPUT: Sesuaikan dengan struktur JSON yang disepakati dengan tim Frontend
            user_input = {
                "messages": [HumanMessage(content=message)],
            }

            # Ekstrak data dari hasil REST API (/match-rab) jika dikirimkan oleh FE
            if analysis_context:
                found_items = analysis_context.get("found_items", [])
                summary = analysis_context.get("summary", {})
                
                if found_items:
                    user_input["rab_items"] = found_items
                
                if summary:
                    user_input["project_metrics"] = {
                        "total_hpp_estimated": summary.get("estimated_total_qhome_price", 0.0),
                        "total_volume": summary.get("total_found", 0)
                    }

            await websocket.send_text(json.dumps({"type": "status", "content": "Agen mulai memproses..."}))

            # 5. EKSEKUSI LANGGRAPH: Streaming respons
            async for event in app_graph.astream_events(user_input, config=config, version="v2"):
                kind = event["event"]
                
                # Streaming teks balasan AI
                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    
                    content = ""
                    if hasattr(chunk, "content"):
                        content = chunk.content
                    elif isinstance(chunk, dict) and "content" in chunk:
                        content = chunk["content"]
                    
                    if content:
                        await websocket.send_text(json.dumps({
                            "type": "chunk",  # Diubah dari "stream_chunk" agar sesuai spesifikasi FE
                            "content": content
                        }))
                
                # Sembunyikan nama node teknis dari Frontend, gunakan peta status
                elif kind == "on_chain_start":
                    node_name = event["name"]
                    if node_name in NODE_STATUS_MAP:
                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "content": NODE_STATUS_MAP[node_name]
                        }))

            # 6. Sinyal Selesai
            await websocket.send_text(json.dumps({"type": "stream_done"}))

    except WebSocketDisconnect:
        logger.info(f"Klien B2B terputus.")
    except Exception as e:
        logger.error(f"Error pada sistem LangGraph: {str(e)}")
        await websocket.send_text(json.dumps({
            "type": "error", 
            "content": "Terjadi kesalahan internal pada agen negosiasi."
        }))