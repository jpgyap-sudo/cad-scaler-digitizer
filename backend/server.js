import express from 'express';
import pg from 'pg';

const app = express();
app.use(express.json({ limit: '10mb' }));

const PORT = process.env.API_BACKEND_PORT || 5001;
const HOST = process.env.API_BACKEND_HOST || '127.0.0.1';

// PostgreSQL connection from env or defaults
const pool = new pg.Pool({
  host: process.env.PG_HOST || 'localhost',
  port: parseInt(process.env.PG_PORT || '5432'),
  database: process.env.PG_DATABASE || 'cad_digitizer',
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
    const { session_id, loop_number, calibration, polylines, ocr_text, verification_score, verification_approved, verification_feedback, raw_dxf } = req.body;
    const result = await pool.query(
      `INSERT INTO digitizer_results (session_id, loop_number, calibration, polylines, ocr_text, verification_score, verification_approved, verification_feedback, raw_dxf)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
       RETURNING *`,
      [session_id, loop_number, JSON.stringify(calibration), JSON.stringify(polylines), JSON.stringify(ocr_text), verification_score, verification_approved, JSON.stringify(verification_feedback), raw_dxf]
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
  console.log(`[Brain] PostgreSQL backend at http://${HOST}:${PORT}`);
});
