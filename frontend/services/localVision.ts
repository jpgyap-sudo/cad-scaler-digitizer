import { Point, Polyline } from '../types';

export interface LocalDetectionResult {
  polylines: Polyline[];
  message: string;
}

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

function dedupeSegments(lines: Polyline[], tolerance = 5): Polyline[] {
  const kept: Polyline[] = [];
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
  const lines: Polyline[] = [];

  // Horizontal scanline extraction.
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
      lines.push({ id: `auto-h-${y}-${x1}-${Date.now()}`, points: [{ x: x1, y }, { x: x2, y }] });
    }
  }

  // Vertical scanline extraction.
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
      lines.push({ id: `auto-v-${x}-${y1}-${Date.now()}`, points: [{ x, y: y1 }, { x, y: y2 }] });
    }
  }

  const cleaned = dedupeSegments(lines)
    .filter(l => {
      const [a, b] = l.points;
      return Math.hypot(a.x - b.x, a.y - b.y) >= minLen;
    })
    .slice(0, 400);

  return {
    polylines: cleaned,
    message: `Detected ${cleaned.length} straight line segments. Use manual snap drawing for curves, circles and missing edges.`
  };
}
