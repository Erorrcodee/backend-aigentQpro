import json
import logging
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
# pyrefly: ignore [missing-import]
from langchain_core.messages import HumanMessage

# Import graph yang sudah Anda rakit sebelumnya
from app.agents.graph_builder import app_graph

logger = logging.getLogger(__name__)
ws_router = APIRouter()

@ws_router.websocket("/ws/negotiation")
async def websocket_negotiation_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Klien B2B terhubung ke WebSocket Negosiasi.")

    # Buat ID sesi unik untuk setiap klien yang terhubung
    session_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    try:
        while True:
            # 1. Terima input dari user
            data_str = await websocket.receive_text()
            request_data = json.loads(data_str)
            
            # Kita HANYA mengirimkan pesan baru dan pembaruan metrik ke dalam graf.
            # LangGraph akan secara otomatis menggabungkannya dengan riwayat sebelumnya.
            user_input = {
                "messages": [HumanMessage(content=request_data.get("message", ""))],
                "requested_discount": request_data.get("requested_discount", 0.0),
                "project_metrics": request_data.get("project_metrics", {}),
            }

            # Masukkan rab_items hanya jika klien mengirimkannya (mencegah penimpaan data RAB yang sudah ada di memori)
            if request_data.get("rab_items"):
                user_input["rab_items"] = request_data["rab_items"]

            await websocket.send_text(json.dumps({"type": "status", "content": "Agen sedang memproses..."}))

            # 2. Eksekusi LangGraph dengan version="v2" dan menyertakan config (thread_id)
            async for event in app_graph.astream_events(user_input, config=config, version="v2"):
                kind = event["event"]
                
                # Streaming teks dengan pengecekan atribut yang aman
                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    
                    # Mengambil konten dengan aman (menangani objek pesan atau chunk)
                    content = ""
                    if hasattr(chunk, "content"):
                        content = chunk.content
                    elif isinstance(chunk, dict) and "content" in chunk:
                        content = chunk["content"]
                    
                    if content:
                        await websocket.send_text(json.dumps({
                            "type": "stream_chunk", 
                            "content": content
                        }))
                
                # Log status node yang sedang berjalan
                elif kind == "on_chain_start":
                    node_name = event["name"]
                    if node_name in ["gateway_node", "vision_node", "pricing_node", "negotiator_node"]:
                        await websocket.send_text(json.dumps({
                            "type": "agent_status",
                            "content": f"Menjalankan {node_name}..."
                        }))

            await websocket.send_text(json.dumps({"type": "stream_done"}))

    except WebSocketDisconnect:
        logger.info(f"Klien B2B terputus. Sesi {session_id} diakhiri.")
    except Exception as e:
        logger.error(f"Error pada sistem LangGraph: {str(e)}")
        await websocket.send_text(json.dumps({
            "type": "error", 
            "content": "Terjadi kesalahan internal pada agen negosiasi."
        }))