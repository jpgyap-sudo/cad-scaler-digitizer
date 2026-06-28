import express from 'express';
import pg from 'pg';
import multer from 'multer';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import http from 'http';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const app = express();
app.use(express.json({ limit: '50mb' }));

const PORT = process.env.API_BACKEND_PORT || 5001;
const HOST = process.env.API_BACKEND_HOST || '127.0.0.1';
const PYTHON_ENGINE_URL = process.env.PYTHON_ENGINE_URL || 'http://localhost:8001';

// Multer for file uploads
const uploadDir = path.join(__dirname, '..', 'uploads');
if (!fs.existsSync(uploadDir)) fs.mkdirSync(uploadDir, { recursive: true });
const upload = multer({ dest: uploadDir, limits: { fileSize: 50 * 1024 * 1024 } });

// PostgreSQL connection from env or defaults
const pool = new pg.Pool({
  host: process.env.PG_HOST || 'localhost',
  port: parseInt(process.env.PG_PORT || '5432'),
  database: process.env.PG_DATABASE || 'cad_reference_library',
  user: process.env.PG_USER || 'postgres',
  password: process.env.PG_PASSWORD || 'postgres',
  max: 5,
});

// CORS middleware
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.sendStatus(204);
  next();
});

// ============ PYTHON ENGINE PROXY ============

/**
 * POST /api/upload
 * Accepts image/PDF file + optional parameters, forwards to Python CAD engine.
 * Uses form-data npm package to properly reconstruct multipart for Python.
 */
app.post('/api/upload', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded. Use multipart/form-data with field name "file".' });
    }

    const realWidthCm = req.body.real_width_cm || req.body.realWidthCm || null;
    const realHeightCm = req.body.real_height_cm || req.body.realHeightCm || null;
    const furnitureType = req.body.furniture_type || req.body.furnitureType || null;

    // Forward to Python engine using fetch + FormData
    const { default: FormData } = await import('form-data');
    const form = new FormData();
    form.append('file', fs.createReadStream(req.file.path), req.file.originalname || 'file.png');
    if (realWidthCm) form.append('real_width_cm', String(realWidthCm));
    if (realHeightCm) form.append('real_height_cm', String(realHeightCm));
    if (furnitureType) form.append('furniture_type', String(furnitureType));

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120000);

    const pythonRes = await fetch(`${PYTHON_ENGINE_URL}/api/digitize`, {
      method: 'POST',
      body: form,
      headers: form.getHeaders ? form.getHeaders() : undefined,
      signal: controller.signal,
      // Use keepalive to avoid proxy issues
    }).finally(() => clearTimeout(timeout));

    // Clean up uploaded file
    try { fs.unlinkSync(req.file.path); } catch {}

    if (!pythonRes.ok) {
      const errText = await pythonRes.text();
      return res.status(pythonRes.status).json({ error: `Python engine error: ${errText}` });
    }

    const result = await pythonRes.json();
    res.json(result);
  } catch (err) {
    // Clean up on error
    if (req.file) {
      try { fs.unlinkSync(req.file.path); } catch {}
    }
    console.error('[Upload] Error:', err.message);
    res.status(500).json({ error: err.message });
  }
});

/**
 * GET /api/download/:filename
 * Proxies DXF download from Python engine.
 */
app.get('/api/download/:filename', async (req, res) => {
  try {
    const pythonRes = await fetch(`${PYTHON_ENGINE_URL}/api/download/${req.params.filename}`);
    if (!pythonRes.ok) {
      return res.status(404).json({ error: 'File not found in Python engine' });
    }
    const buffer = await pythonRes.arrayBuffer();
    res.setHeader('Content-Type', 'application/dxf');
    res.setHeader('Content-Disposition', `attachment; filename="${req.params.filename}"`);
    res.send(Buffer.from(buffer));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ============ PYTHON ENGINE HEALTH CHECK ============

app.get('/api/cad-engine/health', async (_req, res) => {
  try {
    const pythonRes = await fetch(`${PYTHON_ENGINE_URL}/health`);
    if (pythonRes.ok) {
      const data = await pythonRes.json();
      res.json({ status: 'ok', engine: 'python', details: data });
    } else {
      res.json({ status: 'unavailable', engine: 'python' });
    }
  } catch {
    res.json({ status: 'unavailable', engine: 'python' });
  }
});

// ============ POSTGRESQL SESSIONS ============

// Health check
app.get('/api/brain/health', async (_req, res) => {
  try {
    await pool.query('SELECT 1');
    res.json({ status: 'ok', postgres: 'connected' });
  } catch {
    res.json({ status: 'degraded', postgres: 'disconnected' });
  }
});

// Initialize schema
app.get('/api/brain/init', async (_req, res) => {
  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS digitizer_sessions (
        id SERIAL PRIMARY KEY,
        session_id TEXT UNIQUE NOT NULL,
        file_name TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
      );
      CREATE TABLE IF NOT EXISTS digitizer_results (
        id SERIAL PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES digitizer_sessions(session_id) ON DELETE CASCADE,
        loop_number INT DEFAULT 0,
        calibration JSONB,
        polylines JSONB,
        ocr_text JSONB,
        verification_score INT,
        verification_approved BOOLEAN,
        verification_feedback JSONB,
        raw_dxf TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
      );
    `);
    res.json({ status: 'ok', message: 'Schema initialized' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Save a session
app.post('/api/brain/sessions', async (req, res) => {
  try {
    const { session_id, file_name } = req.body;
    const result = await pool.query(
      `INSERT INTO digitizer_sessions (session_id, file_name)
       VALUES ($1, $2)
       ON CONFLICT (session_id) DO UPDATE SET updated_at = NOW()
       RETURNING *`,
      [session_id, file_name]
    );
    res.json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Save a result for a session
app.post('/api/brain/results', async (req, res) => {
  try {
    const { session_id, loop_number, calibration, polylines, ocr_text,
            verification_score, verification_approved, verification_feedback, raw_dxf } = req.body;
    const result = await pool.query(
      `INSERT INTO digitizer_results
       (session_id, loop_number, calibration, polylines, ocr_text,
        verification_score, verification_approved, verification_feedback, raw_dxf)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
       RETURNING *`,
      [session_id, loop_number,
       JSON.stringify(calibration), JSON.stringify(polylines), JSON.stringify(ocr_text),
       verification_score, verification_approved, JSON.stringify(verification_feedback), raw_dxf]
    );
    res.json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get all results for a session
app.get('/api/brain/results/:session_id', async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT * FROM digitizer_results WHERE session_id = $1 ORDER BY loop_number ASC`,
      [req.params.session_id]
    );
    res.json(result.rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get all sessions
app.get('/api/brain/sessions', async (_req, res) => {
  try {
    const result = await pool.query(
      `SELECT s.*, COUNT(r.id) as result_count
       FROM digitizer_sessions s
       LEFT JOIN digitizer_results r ON r.session_id = s.session_id
       GROUP BY s.id
       ORDER BY s.updated_at DESC
       LIMIT 50`
    );
    res.json(result.rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Error handling
app.use((err, _req, res, _next) => {
  console.error('[Brain] Unhandled error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

app.listen(PORT, HOST, () => {
  console.log(`[Brain] Node.js backend at http://${HOST}:${PORT}`);
  console.log(`[Brain] Python CAD engine proxy: ${PYTHON_ENGINE_URL}`);
});
