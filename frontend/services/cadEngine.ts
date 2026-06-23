/**
 * CAD Engine API Client
 * Connects frontend to Python FastAPI backend (OpenCV + OCR + ezdxf).
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
 * Upload a file to the Node.js proxy (which forwards to Python engine).
 * Returns detected features and DXF download link.
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

  const base = import.meta.env.VITE_NODE_API_URL || import.meta.env.VITE_BRAIN_API_URL || 'http://localhost:5001';
  const res = await fetch(`${base}/api/upload`, { method: 'POST', body: form });

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
  const base = import.meta.env.VITE_NODE_API_URL || import.meta.env.VITE_BRAIN_API_URL || 'http://localhost:5001';
  return `${base}${result.download}`;
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
    const base = import.meta.env.VITE_NODE_API_URL || import.meta.env.VITE_BRAIN_API_URL || 'http://localhost:5001';
    const res = await fetch(`${base}/api/cad-engine/health`);
    if (!res.ok) return false;
    const data = await res.json();
    return data.status === 'ok';
  } catch {
    return false;
  }
}
