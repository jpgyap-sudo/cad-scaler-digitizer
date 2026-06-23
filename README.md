# CAD Scaler Digitizer

Upload a furniture drawing (PNG, JPEG, or PDF) with written dimensions → get a **scaled, editable DXF** with proper polylines.

## 🎯 End Goal
```
Input:  Furniture drawing image with dimensions
        (PNG/JPEG/PDF)
           ↓
    OpenCV detects lines, circles, rectangles
    Tesseract OCR reads dimension labels
           ↓
    Classifies furniture type (table, sofa, cabinet, chair, bed)
           ↓
    Scales to real-world dimensions (cm)
           ↓
Output: Clean DXF with editable polylines
        (opens in AutoCAD, LibreCAD, FreeCAD)
```

## 🏗️ Architecture

```
┌──────────────┐     ┌───────────────────┐     ┌──────────────────┐
│  Frontend    │────▶│  Node.js Backend   │────▶│  Python Engine   │
│  React/TS    │     │  (Express + PG)    │     │  (FastAPI)       │
│  Vite        │◀────│  /api/upload       │◀────│  /api/digitize   │
│              │     │  proxies to Python │     │  OpenCV + OCR    │
│  - Upload UI │     │  /api/download     │     │  + ezdxf DXF     │
│  - Dimensions│     │  PostgreSQL        │     │  + Furniture     │
│  - Furniture │     │  sessions/results  │     │    Classifier    │
│    selector  │     └───────────────────┘     └──────────────────┘
│  - DXF export│
└──────────────┘
```

## 🚀 Quick Start

### 1. Python CAD Engine (Required)
```bash
cd backend-python
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
# For PDF support, install additional:
# pip install pdf2image PyPDF2
uvicorn app.main:app --reload --port 8000
```

> **Note:** OCR requires Tesseract. Install from https://github.com/UB-Mannheim/tesseract/wiki
> and ensure `tesseract` is in your PATH.

### 2. Node.js Backend (Optional - for PostgreSQL)
```bash
cd backend
npm install
node server.js              # Runs on port 5001
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev                 # Runs on port 5173
```

## 🔧 Configuration

### Frontend (`.env`)
```
VITE_BRAIN_API_URL=http://localhost:5001    # Node.js backend (proxy)
VITE_CAD_ENGINE_URL=http://localhost:8000   # Direct Python engine
```

### Backend (`.env`)
```
PYTHON_ENGINE_URL=http://localhost:8000     # Where Python engine runs
```

## 🧠 How It Works

| Step | Component | Description |
|------|-----------|-------------|
| 1 | **Upload** | User uploads PNG/JPEG/PDF with optional known dimensions |
| 2 | **Vision** | OpenCV detects lines (Hough), circles, rectangles (contour) |
| 3 | **OCR** | Tesseract reads dimension labels, extracts numeric values |
| 4 | **Classify** | Furniture type identified: table, sofa, cabinet, chair, bed |
| 5 | **Scale** | Real-world dimensions applied for accurate scaling |
| 6 | **DXF** | ezdxf generates clean R2010 DXF with layers |
| 7 | **Download** | User downloads scaled, editable DXF |

## 🪑 Supported Furniture Types

| Type | Auto-Detect | Template Reconstruction |
|------|:-----------:|:----------------------:|
| Round Pedestal Table | ✅ High | ✅ Top + Front views |
| Rectangular Table | ✅ Medium | ✅ Top + Front views |
| Sofa / Couch | ✅ Medium | ✅ Front view |
| Cabinet / Wardrobe | ✅ Medium | ✅ Front + Side views |
| Bed / Headboard | ✅ Medium | ✅ Front view |
| Chair | ✅ Medium | ✅ Front + Side views |
| Generic (raw tracing) | ✅ Low | ❌ Lines + circles only |

## 🧪 Tech Stack

- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons
- **Backend (Node):** Express 5, PostgreSQL, Multer
- **Engine (Python):** FastAPI, OpenCV, Tesseract OCR, ezdxf
- **AI (optional):** OpenAI GPT-4o / Gemini API for advanced detection

## 📁 Project Structure

```
├── backend/                    # Node.js Express + PostgreSQL
│   ├── server.js               # API server / Python proxy
│   └── package.json
├── backend-python/             # Python CAD engine
│   ├── app/
│   │   ├── main.py             # FastAPI endpoints
│   │   ├── engine/
│   │   │   ├── vision.py       # OpenCV line/circle/rect detection + OCR
│   │   │   ├── pipeline.py     # Full processing pipeline
│   │   │   ├── dxf_writer.py   # ezdxf DXF generation
│   │   │   └── furniture_classifier.py
│   │   └── agents/             # Agent documentation
│   └── requirements.txt
├── frontend/                   # React/TypeScript UI
│   ├── App.tsx                 # Main app component
│   ├── services/
│   │   ├── agent.ts            # OpenAI AI agent
│   │   ├── cadEngine.ts        # Python engine client
│   │   ├── cadRenderer.ts      # Canvas rendering
│   │   ├── cadCleanup.ts       # Primitive cleanup
│   │   └── templateMatcher.ts  # Parametric template matching
│   └── components/
├── resources/
│   └── furniture_templates/    # Parametric JSON templates
│       ├── round_pedestal_table.json
│       ├── rectangular_table.json
│       ├── sofa.json
│       ├── cabinet.json
│       ├── bed_headboard.json
│       └── chair.json
├── skills/                     # Operator documentation
├── plans/                      # Architecture plans
└── memory/                     # Bug tracking
```

## 📋 Roadmap

- [x] V1: Round pedestal table template (working)
- [x] V2: Rectangular table, cabinet, sofa, headboard, chair templates
- [x] V3: PDF support + OCR dimension association
- [x] V4: True DXF DIMENSION entities and layered output
- [ ] V5: FreeCAD workbench/plugin
- [ ] V6: DWG conversion (ODA File Converter)
- [ ] V7: WebAssembly OpenCV for browser-only mode
