# AutoCAD Scaler & Digitizer — Gemini API Edition

Upload architectural drawings, automatically detect scale using Gemini AI, calibrate dimensions, draw polylines, and export to DXF format. **Pure frontend app — no backend server needed.**

## How It Works

1. **Upload a drawing image** (PNG, JPG, WEBP)
2. **Gemini AI processing** via Google's Gemini 2.5 Flash API:
   - Detects scale bars and dimension lines
   - Extracts text via OCR
   - Traces structural polylines
3. **Quality verification** — a Verifier Agent checks the extraction
4. **Manual corrections** — browse polylines, snap-draw missing edges, recalibrate
5. **Export to DXF** — downloads a standard AC1009 DXF file

## Prerequisites

- **Node.js 18+** and npm
- **Gemini API key** — get one free at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

## Quick Start

```bash
# 1. Add your API key
echo "VITE_GEMINI_API_KEY=your_key_here" > frontend/.env

# 2. Install and start
npm install
npm run dev
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| AI | Gemini API (gemini-2.5-flash) via @google/genai SDK |
| DXF Export | Custom TypeScript generator (no dependencies) |
| Local Detection | Browser Canvas API |

## What Changed (vs Vertex AI version)

- **Removed the entire Node.js backend** — Gemini SDK calls the API directly from the browser
- **No Google Cloud project needed** — just a Gemini API key
- **No Vertex AI proxy** — direct client-side calls to Gemini API
- **No Ollama** — uses cloud Gemini instead of local models
- **67 dependencies** (down from 181 in the original)
