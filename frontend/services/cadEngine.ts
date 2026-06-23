/**
 * CAD Engine API Client
 * Connects frontend to Python FastAPI backend (OpenCV + OCR + ezdxf).
 * Uses Vite dev proxy (/py-api/) to bypass Windows system proxy on localhost.
 */

export type DigitizeResult = {
  job_id: string;
  download: string;
  dxf_file: string;
  furniture: {
    type: string;
    confidence: number;
    required_dimensions?: string[];
    missing_dimensions?: string[];
    recommended_template?: string;
  };
  detected: {
    lines: number;
    circles: number;
    rectangles: number;
    dimensions: Array<{ value_cm: number; tag: string; raw: string }>;
    ocr_lines: string[];
  };
  warnings: string[];
};

export type FurnitureType =
  | 'round_pedestal_table'
  | 'rectangular_table'
  | 'sofa'
  | 'cabinet'
  | 'bed_headboard'
  | 'chair'
  | 'generic_2d_furniture'
  | '';

const FURNITURE_LABELS: Record<string, string> = {
  round_pedestal_table: 'Round Pedestal Table',
  rectangular_table: 'Rectangular Table',
  sofa: 'Sofa / Couch',
  cabinet: 'Cabinet / Wardrobe',
  bed_headboard: 'Bed / Headboard',
  chair: 'Chair',
  generic_2d_furniture: 'Generic Furniture',
};

export function getFurnitureLabel(type: string): string {
  return FURNITURE_LABELS[type] || type.replace(/_/g, ' ');
}

export function getFurnitureConfidenceLabel(confidence: number): string {
  if (confidence >= 0.8) return 'High';
  if (confidence >= 0.5) return 'Medium';
  return 'Low';
}

/**
 * Get the base URL for Python CAD engine.
 * Uses Vite dev proxy (/py-api/) by default — this bypasses Windows proxy.
 */
function getEngineBase(): string {
  return import.meta.env.VITE_CAD_ENGINE_URL || '/py-api';
}

/**
 * Upload a file directly to the Python CAD engine.
 * The browser sends FormData directly — no Node proxy involved.
 */
export async function digitizeWithBackend(
  file: File,
  opts?: {
    realWidthCm?: number;
    realHeightCm?: number;
    furnitureType?: string;
  }
): Promise<DigitizeResult> {
  const form = new FormData();
  form.append('file', file);
  if (opts?.realWidthCm) form.append('real_width_cm', String(opts.realWidthCm));
  if (opts?.realHeightCm) form.append('real_height_cm', String(opts.realHeightCm));
  if (opts?.furnitureType) form.append('furniture_type', String(opts.furnitureType));

  const base = getEngineBase();
  const url = `${base}/digitize`;
  const res = await fetch(url, { method: 'POST', body: form });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`CAD engine failed (${res.status}): ${err}`);
  }

  return res.json();
}

/**
 * Get the DXF download URL for a result.
 */
export function getDownloadUrl(result: DigitizeResult): string {
  const base = import.meta.env.VITE_CAD_ENGINE_URL || '';
  const dlPath = result.download.replace('/api/', '/py-api/');
  return base ? `${base}${result.download}` : `${window.location.origin}${dlPath}`;
}

/**
 * Download DXF file directly in browser.
 */
export function downloadDxf(result: DigitizeResult): void {
  const url = getDownloadUrl(result);
  const a = document.createElement('a');
  a.href = url;
  a.download = result.dxf_file || 'drawing.dxf';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/**
 * Check if Python CAD engine is available.
 */
export async function checkEngineHealth(): Promise<boolean> {
  try {
    const res = await fetch('/py-api/health');
    if (!res.ok) return false;
    const data = await res.json();
    return data.ok === true;
  } catch {
    return false;
  }
}
