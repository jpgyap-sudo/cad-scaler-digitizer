/**
 * Local Vision — browser-side geometry detection with confidence tracking.
 *
 * Uses canvas pixel scanning for line detection.
 * Every detected segment includes source/confidence metadata.
 *
 * LIMITATIONS: Only scans horizontal and vertical dark pixel runs.
 * Does NOT detect: curves, circles, arcs, angled lines, arrowheads.
 * Use the Python backend (OpenCV + ezdxf) for production CAD.
 * This module is for PREVIEW / MANUAL ASSIST only.
 *
 * Source labels for UI display:
 *   measured: directly scanned from image pixels
 *   inferred: approximated from nearby features
 *   user_drawn: manually drawn by user
 *   template: from parametric template
 */

export interface LocalDetectionResult {
  polylines: PolylineWithMetadata[];
  message: string;
}

export interface PolylineWithMetadata {
  id: string;
  points: Array<{ x: number; y: number }>;
  /** Source of this geometry: 'measured' | 'inferred' | 'user_drawn' | 'template' */
  source: string;
  /** Confidence 0.0-1.0 */
  confidence: number;
  /** Evidence summary */
  evidence?: string;
}

// Import base types
import { Polyline } from '../types';

const isDark = (r: number, g: number, b: number) => (r + g + b) / 3 < 175;

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

function mergeIntervals(intervals: Array<[number, number]>, gap = 8): Array<[number, number]> {
  if (!intervals.length) return [];
  intervals.sort((a, b) => a[0] - b[0]);
  const out: Array<[number, number]> = [intervals[0]];
  for (const cur of intervals.slice(1)) {
    const last = out[out.length - 1];
    if (cur[0] <= last[1] + gap) last[1] = Math.max(last[1], cur[1]);
    else out.push(cur);
  }
  return out;
}

function dedupeSegments(lines: Array<PolylineWithMetadata>, tolerance = 5): Array<PolylineWithMetadata> {
  const kept: Array<PolylineWithMetadata> = [];
  for (const line of lines) {
    const [a, b] = line.points;
    const duplicate = kept.some(k => {
      const [ka, kb] = k.points;
      const sameH = Math.abs(a.y - b.y) < 2 && Math.abs(ka.y - kb.y) < 2 && Math.abs(a.y - ka.y) < tolerance;
      const sameV = Math.abs(a.x - b.x) < 2 && Math.abs(ka.x - kb.x) < 2 && Math.abs(a.x - ka.x) < tolerance;
      if (sameH) return Math.max(a.x, ka.x) <= Math.min(b.x, kb.x) + tolerance;
      if (sameV) return Math.max(a.y, ka.y) <= Math.min(b.y, kb.y) + tolerance;
      return false;
    });
    if (!duplicate) kept.push(line);
  }
  return kept;
}

/**
 * Detect straight horizontal and vertical lines from an image.
 * Returns segments with source="measured" and confidence based on
 * pixel darkness and line continuity.
 *
 * NOTE: This is a simplified browser-side scanner. It does NOT detect:
 * - Circles, arcs, curves
 * - Angled/diagonal lines
 * - Arrowheads, dimension ticks
 * - Dashed or centerline patterns
 * 
 * For full detection, use the Python backend pipeline.
 */
export async function detectLinesFromImage(imageSrc: string): Promise<LocalDetectionResult> {
  const img = await loadImage(imageSrc);
  const canvas = document.createElement('canvas');
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) throw new Error('Canvas is not available');
  ctx.drawImage(img, 0, 0);
  const { data, width, height } = ctx.getImageData(0, 0, canvas.width, canvas.height);

  const minLen = Math.max(24, Math.round(Math.min(width, height) * 0.05));
  const lines: Array<PolylineWithMetadata> = [];
  let totalDarkRunLength = 0;
  let runCount = 0;

  // Horizontal scanline extraction
  for (let y = 0; y < height; y += 2) {
    const intervals: Array<[number, number]> = [];
    let start = -1;
    for (let x = 0; x < width; x++) {
      const idx = (y * width + x) * 4;
      const dark = isDark(data[idx], data[idx + 1], data[idx + 2]) && data[idx + 3] > 10;
      if (dark && start < 0) start = x;
      if ((!dark || x === width - 1) && start >= 0) {
        const end = dark && x === width - 1 ? x : x - 1;
        if (end - start >= minLen) intervals.push([start, end]);
        start = -1;
      }
    }
    for (const [x1, x2] of mergeIntervals(intervals)) {
      const runLen = x2 - x1;
      totalDarkRunLength += runLen;
      runCount++;
      lines.push({
        id: `auto-h-${y}-${x1}`,
        points: [{ x: x1, y }, { x: x2, y }],
        source: 'measured',
        confidence: 0.6 + Math.min(runLen / 500, 0.35), // Longer runs = higher confidence
        evidence: `horizontal scan at y=${y}, length=${runLen}px`,
      });
    }
  }

  // Vertical scanline extraction
  for (let x = 0; x < width; x += 2) {
    const intervals: Array<[number, number]> = [];
    let start = -1;
    for (let y = 0; y < height; y++) {
      const idx = (y * width + x) * 4;
      const dark = isDark(data[idx], data[idx + 1], data[idx + 2]) && data[idx + 3] > 10;
      if (dark && start < 0) start = y;
      if ((!dark || y === height - 1) && start >= 0) {
        const end = dark && y === height - 1 ? y : y - 1;
        if (end - start >= minLen) intervals.push([start, end]);
        start = -1;
      }
    }
    for (const [y1, y2] of mergeIntervals(intervals)) {
      const runLen = y2 - y1;
      lines.push({
        id: `auto-v-${x}-${y1}`,
        points: [{ x, y: y1 }, { x, y: y2 }],
        source: 'measured',
        confidence: 0.6 + Math.min(runLen / 500, 0.35),
        evidence: `vertical scan at x=${x}, length=${runLen}px`,
      });
    }
  }

  // Clean up duplicates
  const cleaned = dedupeSegments(lines)
    .filter(l => {
      const [a, b] = l.points;
      return Math.hypot(a.x - b.x, a.y - b.y) >= minLen;
    })
    .slice(0, 400);

  // Compute average quality
  const avgConfidence = cleaned.length > 0
    ? cleaned.reduce((s, l) => s + l.confidence, 0) / cleaned.length
    : 0;

  return {
    polylines: cleaned,
    message:
      `Detected ${cleaned.length} straight line segments ` +
      `(avg confidence: ${(avgConfidence * 100).toFixed(0)}%). ` +
      `All marked as "measured" from pixel scan. ` +
      `Use manual snap drawing for curves, circles, angled leaders, and missing edges.`,
  };
}
