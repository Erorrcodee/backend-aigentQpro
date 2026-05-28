<div align="center">
  <h1>🏢 QHome AI B2B Negotiation System 🤖</h1>
  <p><i>Sistem Kecerdasan Buatan Otonom untuk Negosiasi Harga Material Konstruksi Skala Enterprise</i></p>

  ![Python Version](https://img.shields.io/badge/Python-3.13-blue.svg)
  ![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg?logo=fastapi)
  ![LangGraph](https://img.shields.io/badge/LangGraph-AI_Agents-orange)
  ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Asyncpg-336791.svg?logo=postgresql)
  ![Machine Learning](https://img.shields.io/badge/Machine_Learning-FP_Growth-FF6F00)
</div>

<br>

**QHome AI Backend** adalah solusi kecerdasan buatan kelas *enterprise* yang dirancang untuk merevolusi cara perusahaan QHome melakukan transaksi B2B (Business-to-Business) dengan pihak kontraktor. 

Kami menghilangkan hambatan birokrasi penawaran harga manual dengan menghadirkan **Agen Negosiator AI Otonom**. Sistem ini tidak sekadar menjawab obrolan, melainkan mampu melakukan tawar-menawar harga, menganalisis risiko margin, membaca Rencana Anggaran Biaya (RAB) fisik, hingga menerbitkan *invoice* secara *real-time*.

---

## 💎 Keunggulan Kompetitif (Value Proposition)

Mengapa sistem QHome AI lebih dari sekadar *chatbot* biasa?

| Fitur Unggulan | Chatbot Konvensional | QHome AI B2B System | Dampak Bisnis |
| :--- | :--- | :--- | :--- |
| **Kalkulasi Harga** | Diskon tetap (*Flat rate*) atau manual. | **MAUT Engine:** Diskon dihitung dinamis berdasarkan loyalitas klien, volume belanja, dan batas HPP. | Mencegah kerugian margin; memastikan harga adil bagi klien VIP. |
| **Pembacaan Dokumen** | Tidak bisa membaca fail PDF/Gambar. | **Vision Extraction:** Mampu membedah PDF/Gambar RAB kontraktor langsung menjadi JSON terstruktur. | Memangkas waktu entri data dari jam menjadi detik. |
| **Peningkatan Penjualan** | Menunggu pesanan (Pasif). | **Hybrid RAG-MBA:** AI menambang data transaksi menggunakan *FP-Growth* untuk menawarkan silang-jual (*cross-sell*) yang logis secara statistik. | Meningkatkan *Average Order Value* (AOV) tanpa tenaga staf *sales*. |
| **Penyelesaian Transaksi** | Hanya memberi informasi. | **Auto-Invoicing:** AI mengunci harga kesepakatan dan langsung mengunggah fail *Invoice* PDF ke klien via WebSocket. | Menutup penjualan (*closing deal*) secara instan 24/7. |

---

## 🏗️ Arsitektur Sistem (The Engine)

Sistem ini dibangun menggunakan arsitektur *Domain-Driven Design* (DDD) asinkron penuh untuk memastikan skalabilitas tinggi.

### 1. Alur Kerja Agen Negosiasi (LangGraph)
Otak utama percakapan diatur menggunakan Graf Kondisional (LangGraph) untuk mencegah halusinasi AI.

| Node (Simpul) | Peran & Tanggung Jawab |
| :--- | :--- |
| `gateway_node` | Penjaga gerbang. Menilai apakah obrolan masuk konteks B2B atau memblokir pertanyaan di luar topik (misal: resep masakan). |
| `vision_node` | Membaca dokumen RAB biner dan mengekstraknya ke dalam variabel *state* LangGraph. |
| `pricing_node` | Memanggil algoritma MAUT lokal untuk menghitung batas diskon maksimal sebelum AI membalas tawaran. |
| `negotiator_node` | Model LLM (Llama-3/Qwen) yang dilatih dengan *prompt* psikologi penjualan (Teori Cialdini) untuk tawar-menawar dengan batas diskon dari node harga. |
| `invoice_node` | Mencetak dokumen kesepakatan akhir, mengunci *database*, dan mengirim tautan unduhan. |

### 2. Pekerja Penambang Data (MBA Miner)
Berjalan di latar belakang setiap tengah malam (via `APScheduler`).
1. **Ekstrak:** Membaca ribuan transaksi B2B yang sukses.
2. **Transformasi & Analisis:** Menggunakan `mlxtend` (Algoritma FP-Growth) untuk mencari pola belanja tersembunyi (Misal: *Jika beli Bata Ringan, 80% kemungkinan butuh Semen Perekat*).
3. **Pemuatan:** Menyimpan aturan asosiasi (*Association Rules*) ke *database* untuk digunakan AI Negosiator esok harinya.

---

## 🚀 Prasyarat Instalasi

Pastikan sistem/server Anda telah memasang:
- **Python** (Versi >= 3.13)
- **PostgreSQL** (Dengan ekstensi `pgvector` aktif)
- **Redis Server** (Untuk *Rate Limiting*)
- Kunci API Aktif: **Groq**, **Google Gemini**, dan **Cloudinary**.

---

## ⚙️ Panduan Instalasi Lokal

**1. Klon Repositori & Masuk Direktori**
```bash
git clone git@github.com:bngden/qhome-ai-backend.git
cd qhome-ai-backend

