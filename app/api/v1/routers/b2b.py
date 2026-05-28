# app/api/v1/router/b2b.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from typing import List
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Import dependensi internal
from app.api.dependencies import get_current_b2b, get_db
from app.models.users import User
from app.models.product_catalog import Product
from app.schemas.common_schema import BaseResponse

# Import service AI
from app.services.vision_agent import extract_rab_from_file
from app.services.embedding_service import generate_product_vector

router = APIRouter()

# ==========================================
# 1. ENDPOINT UPLOAD & EKSTRAK RAB (VISION)
# ==========================================
@router.post("/upload-rab", response_model=BaseResponse, status_code=status.HTTP_200_OK)
async def upload_rab_document(
    file: UploadFile = File(...),
    current_b2b: User = Depends(get_current_b2b)
):
    """Membaca dokumen RAB (PDF/Gambar) menjadi format JSON"""
    allowed_mimes = ["image/jpeg", "image/png", "application/pdf"]
    if file.content_type not in allowed_mimes:
        raise HTTPException(status_code=400, detail="Format tidak didukung. Harap unggah PDF, JPG, atau PNG.")

    file_bytes = await file.read()
    
    try:
        extracted_data = await extract_rab_from_file(file_bytes, file.content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sistem AI gagal membedah dokumen: {str(e)}")

    return BaseResponse(
        status="success",
        message="Dokumen RAB berhasil diekstrak dan diaudit oleh AI",
        data=extracted_data
    )


# ==========================================
# 2. ENDPOINT MATCHMAKER (SEMANTIC SEARCH)
# ==========================================
class RABItemQuery(BaseModel):
    item_name: str
    quantity: float

class MatchmakerRequest(BaseModel):
    items: List[RABItemQuery]

@router.post("/match-rab", response_model=BaseResponse, status_code=status.HTTP_200_OK)
async def match_rab_to_catalog(
    request: MatchmakerRequest,
    db: AsyncSession = Depends(get_db),
    current_b2b: User = Depends(get_current_b2b)
):
    """
    Mencocokkan RAB dengan katalog QHome, lalu memisahkan
    barang yang tersedia dan yang tidak tersedia untuk kebutuhan UI Frontend.
    """
    found_items = []
    not_found_items = []
    estimated_total_qhome_price = 0.0
    
    for rab_item in request.items:
        try:
            # 1. Ubah nama barang RAB menjadi Vektor
            query_vector = await generate_product_vector(rab_item.item_name)
            
            # 2. Hitung jarak makna (Cosine Distance) di database
            distance_col = Product.embedding.cosine_distance(query_vector).label("distance")
            
            # 3. Cari top 3 barang terdekat
            stmt = (
                select(Product, distance_col)
                .filter(Product.is_active == True)
                .order_by(distance_col)
                .limit(3)
            )
            
            db_result = await db.execute(stmt)
            matches = db_result.all() 
            
            matched_products = []
            for product, dist in matches:
                similarity = (1 - dist) * 100 
                if similarity >= 70.0:  # Minimal 50% tingkat kemiripan
                    matched_products.append({
                        "id": str(product.id),
                        "sku": product.sku,
                        "name": product.name,
                        "brand": product.brand,
                        "price": product.price,
                        "similarity_percentage": round(similarity, 2)
                    })
            
            # 4. Pisahkan berdasarkan hasil pencarian
            if len(matched_products) > 0:
                best_match = matched_products[0]
                
                subtotal = best_match["price"] * rab_item.quantity
                estimated_total_qhome_price += subtotal
                
                found_items.append({
                    "rab_item_name": rab_item.item_name,
                    "requested_quantity": rab_item.quantity,
                    "best_match_qhome": best_match,
                    "other_alternatives": matched_products[1:], 
                    "subtotal_estimation": subtotal
                })
            else:
                not_found_items.append({
                    "rab_item_name": rab_item.item_name,
                    "requested_quantity": rab_item.quantity,
                    "reason": "Barang tidak ditemukan di katalog QHome atau kemiripan terlalu rendah."
                })
            
        except Exception:
            not_found_items.append({
                "rab_item_name": rab_item.item_name,
                "requested_quantity": rab_item.quantity,
                "reason": "Gagal diproses oleh sistem AI."
            })

    # 5. Format respons akhir
    return BaseResponse(
        status="success",
        message="AI berhasil memisahkan barang yang tersedia dan tidak tersedia",
        data={
            "summary": {
                "total_rab_items": len(request.items),
                "total_found": len(found_items),
                "total_not_found": len(not_found_items),
                "estimated_total_qhome_price": estimated_total_qhome_price
            },
            "found_items": found_items,
            "not_found_items": not_found_items
        }
    )