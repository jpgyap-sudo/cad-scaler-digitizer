/**
 * CAD Engine API Client
 * Connects frontend to Python FastAPI backend (OpenCV + OCR + ezdxf).
 * Uses Vite dev proxy (/py-api/) to bypass Windows system proxy on localhost.
 */

export interface ComponentDim {
  key: string;
  label: string;
  min: number;
  max: number;
  step: number;
  unit: string;
}

export interface ComponentSchema {
  name: string;
  label: string;
  dims: ComponentDim[];
  material?: { key: string; default: string };
}

export interface AccuracyAssociation {
  text: string;
  value_cm: number;
  text_position: { x: number; y: number };
  dim_line?: { p1: [number, number]; p2: [number, number]; length_px: number } | null;
  associated_lines_count: number;
  associated_circle: [number, number, number] | null;
  confidence: number;
  is_diameter: boolean;
  evidence: string[];
  source?: string;
}

export interface AccuracyPipeline {
  layout?: Record<string, any>;
  line_roles?: Record<string, any>;
  associations?: {
    associations: AccuracyAssociation[];
    unassociated_labels: Array<{ text: string; x: number; y: number }>;
    unassociated_geometry_count: number;
    scale_px_per_cm?: number;
    summary: string;
  };
  scale?: Record<string, any> | null;
  reconstruction?: Record<string, any>;
}

export interface TemplateGraphView {
  template_id: string;
  template_name: string;
  product_type: string;
  family: string;
  resolved_parameters_mm: Record<string, number>;
  required_views: string[];
  required_details: string[];
  drawing_notes: string[];
}

export interface ConstraintResult {
  id: string;
  description: string;
  expression: string;
  severity: string;
  passed: boolean;
}

export interface ResolveResult {
  template_id: string;
  template_name: string;
  product_type: string;
  family: string;
  resolved_parameters_mm: Record<string, number>;
  parameters_schema: Array<{
    name: string;
    default: number;
    min_value: number;
    max_value: number;
    description: string;
  }>;
  required_views: string[];
  required_details: string[];
  drawing_notes: string[];
  constraints: ConstraintResult[];
  warnings: string[];
}

export interface Phase3Result {
  vision_features?: Record<string, any>;
  scene_graph?: Record<string, any>;
  template_graph?: TemplateGraphView;
  validation?: Record<string, any>;
  production?: Record<string, any>;
  warnings: string[];
  errors: string[];
}

export type DigitizeResult = {
  job_id: string;
  download: string;
  dxf_file: string;
  preview_svg?: string;
  resolved_dimensions?: Record<string, number>;
  component_schema?: ComponentSchema[] | null;
  template_graph?: TemplateGraphView;
  template_warnings?: string[];
  phase3?: Phase3Result | null;
  accuracy_pipeline?: AccuracyPipeline;
  furniture: {
    type: string;
    confidence: number;
    needs_confirmation?: boolean;
    required_dimensions?: string[];
    missing_dimensions?: string[];
    recommended_template?: string;
  };
  image_quality?: { blur_score: number; is_blurry: boolean; threshold: number };
  materials?: Record<string, { description: string; inferred: boolean } | string>;
  ai_analysis?: {
    visual_base_estimate?: {
      profile?: 'cylinder' | 'tapered' | 'flared' | 'unknown';
      neck_ratio?: number;
      base_ratio?: number;
      has_collar?: boolean;
      collar_ratio?: number;
    };
  };
  detected: {
    lines: number;
    circles: number;
    rectangles: number;
    dimensions: Array<{ value_cm: number; tag: string; raw: string; source?: string; confidence?: number }>;
    ocr_lines: string[];
  };
  warnings: string[];
};

export type FurnitureType =
  | 'round_pedestal_table'
  | 'rectangular_table'
  | 'oval_pedestal_table'
  | 'console_table'
  | 'coffee_table'
  | 'side_table'
  | 'sofa'
  | 'lounge_chair'
  | 'dining_chair'
  | 'chair'
  | 'cabinet'
  | 'sideboard'
  | 'tv_console'
  | 'nightstand'
  | 'wardrobe'
  | 'bed'
  | 'bed_headboard'
  | 'office_desk'
  | 'reception_counter'
  | 'asymmetric_pedestal_table'
  | 'generic_2d_furniture'
  | '';

const FURNITURE_LABELS: Record<string, string> = {
  round_pedestal_table: 'Round Pedestal Table',
  rectangular_table: 'Rectangular Table',
  oval_pedestal_table: 'Oval Pedestal Table',
  console_table: 'Console / Sofa Table',
  coffee_table: 'Coffee Table',
  side_table: 'Side / End Table',
  sofa: 'Sofa / Couch',
  lounge_chair: 'Lounge Chair',
  dining_chair: 'Dining Chair',
  chair: 'Chair',
  cabinet: 'Cabinet',
  sideboard: 'Sideboard / Buffet',
  tv_console: 'TV Console',
  nightstand: 'Nightstand',
  wardrobe: 'Wardrobe',
  bed: 'Platform Bed',
  bed_headboard: 'Bed Headboard',
  office_desk: 'Office Desk',
  reception_counter: 'Reception Counter',
  asymmetric_pedestal_table: 'Asymmetric Pedestal Table',
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
 * Upload to HYBRID pipeline: OpenCV geometry + OpenAI Vision cross-validation.
 * This gives maximum accuracy by using both engines together.
 */
export async function digitizeHybrid(
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
  const url = `${base}/digitize/hybrid`;
  const res = await fetch(url, { method: 'POST', body: form });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Hybrid engine failed (${res.status}): ${err}`);
  }

  return res.json();
}

/**
 * Get the DXF download URL for a result.
 * Always builds through the Vite proxy (/py-api/download/...) for localhost;
 * or prepends full base URL in production.
 */
export function getDownloadUrl(result: DigitizeResult): string {
  if (!result || !result.download) return '';
  // Rewrite /api/download → /py-api/download so Vite proxy routes it
  const dlPath = result.download.replace('/api/', '/py-api/');
  const base = import.meta.env.VITE_CAD_ENGINE_URL || '';
  if (base.startsWith('http')) {
    // Production: absolute base URL provided
    return `${base}${result.download}`;
  }
  // Dev: use relative path through Vite proxy
  return `${window.location.origin}${dlPath}`;
}

/**
 * Download DXF file directly in browser.
 */
export function downloadDxf(result: DigitizeResult): void {
  if (!result || !result.download) {
    console.error('[DXF Download] No download URL available in result:', result);
    return;
  }
  // Download via fetch + blob to avoid Vite proxy multipart issues with direct download
  const dlPath = result.download.replace('/api/', '/py-api/');
  const base = import.meta.env.VITE_CAD_ENGINE_URL || window.location.origin;
  const url = base.startsWith('http') ? `${base}${result.download}` : `${window.location.origin}${dlPath}`;

  // Use fetch to download and create blob (works through proxy)
  fetch(url)
    .then(res => res.blob())
    .then(blob => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = result.dxf_file || 'drawing.dxf';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
    })
    .catch(err => {
      console.error('[DXF Download] Error:', err);
      // Fallback: direct link
      const a = document.createElement('a');
      a.href = url;
      a.download = result.dxf_file || 'drawing.dxf';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    });
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

/**
 * Get preview PNG URL for a DXF file.
 */
export function getPreviewUrl(dxfFile: string): string {
  const base = import.meta.env.VITE_CAD_ENGINE_URL || '';
  if (base.startsWith('http')) return `${base}/api/preview/${dxfFile}`;
  return `${window.location.origin}/py-api/preview/${dxfFile}`;
}

/**
 * Get SVG preview URL (handles both /api/ and /py-api/ prefixes).
 */
export function getSvgPreviewUrl(path: string): string {
  if (!path) return '';
  const base = import.meta.env.VITE_CAD_ENGINE_URL || '';
  // Rewrite /api/ -> /py-api/ for Vite dev proxy
  const proxyPath = path.replace('/api/', '/py-api/');
  if (base.startsWith('http')) return `${base}${path}`;
  return `${window.location.origin}${proxyPath}`;
}

/**
 * Get PDF download URL for a DXF file.
 */
export function getPdfUrl(dxfFile: string): string {
  const base = import.meta.env.VITE_CAD_ENGINE_URL || '';
  if (base.startsWith('http')) return `${base}/api/preview/pdf/${dxfFile}`;
  return `${window.location.origin}/py-api/preview/pdf/${dxfFile}`;
}

/**
 * Pre-digitize resolve: get template graph + parameter schema + constraints
 * for a furniture type, WITHOUT uploading a photo.
 * Returns the full ResolveResult for showing sliders/notes BEFORE digitizing.
 */
export async function resolveTemplate(
  furnitureType: string,
  options?: {
    lengthCm?: number;
    depthCm?: number;
    heightCm?: number;
    widthCm?: number;
    topThicknessCm?: number;
    seatHeightCm?: number;
  }
): Promise<ResolveResult> {
  const form = new FormData();
  form.append('furniture_type', furnitureType);
  if (options?.lengthCm) form.append('length_cm', String(options.lengthCm));
  if (options?.depthCm) form.append('depth_cm', String(options.depthCm));
  if (options?.heightCm) form.append('height_cm', String(options.heightCm));
  if (options?.widthCm) form.append('width_cm', String(options.widthCm));
  if (options?.topThicknessCm) form.append('top_thickness_cm', String(options.topThicknessCm));
  if (options?.seatHeightCm) form.append('seat_height_cm', String(options.seatHeightCm));

  const base = getEngineBase();
  const url = `${base}/digitize/resolve`;
  const res = await fetch(url, { method: 'POST', body: form });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Resolve failed (${res.status}): ${err}`);
  }

  return res.json();
}

/**
 * UNIFIED endpoint — ONE call that blends AI Vision + OpenCV/OCR +
 * cad_intelligence + template graphs into a single confidence-weighted
 * result with per-field provenance tracking.
 *
 * This is the "genius" endpoint: it works for photos, CAD drawings,
 * and everything in between.
 */
export interface UnifiedDimSource {
  value: number;
  source: string;
  confidence: number;
  note: string;
}

export interface UnifiedResult {
  job_id: string;
  ai_enabled: boolean;
  product_type: UnifiedDimSource | null;
  top_shape: UnifiedDimSource | null;
  support_type: UnifiedDimSource | null;
  material_top: UnifiedDimSource | null;
  material_base: UnifiedDimSource | null;
  dimensions: Record<string, UnifiedDimSource>;
  entity_count: number;
  warnings: string[];
  errors: string[];
  template?: {
    template_id: string;
    template_name: string;
    resolved_parameters_mm: Record<string, number>;
    required_views: string[];
    required_details: string[];
    drawing_notes: string[];
  };
}

export async function digitizeUnified(
  file: File,
  opts?: {
    realWidthCm?: number;
    realHeightCm?: number;
    furnitureType?: string;
  }
): Promise<UnifiedResult> {
  const form = new FormData();
  form.append('file', file);
  if (opts?.realWidthCm) form.append('real_width_cm', String(opts.realWidthCm));
  if (opts?.realHeightCm) form.append('real_height_cm', String(opts.realHeightCm));
  if (opts?.furnitureType) form.append('furniture_type', String(opts.furnitureType));

  const base = getEngineBase();
  const url = `${base}/digitize/unified`;
  const res = await fetch(url, { method: 'POST', body: form });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Unified engine failed (${res.status}): ${err}`);
  }

  return res.json();
}

// ──── Smart Auto Workflow ────

export type SmartWorkflowMeta = {
  workflow: "smart_auto";
  internal_route: "opencv" | "hybrid" | "ai" | "pipeline";
  ai_used_or_recommended: boolean;
  route_reasons: string[];
  confidence: { furniture: number; dimensions: number; scale: number; };
  needs_confirmation: boolean;
  confirmation_questions: Array<{
    id: string; type: string; severity: string; title: string; message: string;
    options: Array<{ label: string; value: string }>;
    default_value?: string; required?: boolean; affects_dxf?: boolean;
  }>;
};

export async function digitizeSmartAuto(
  file: File,
  opts?: { realWidthCm?: number; realHeightCm?: number; furnitureType?: string; answers?: Record<string, string>; }
): Promise<DigitizeResult> {
  const form = new FormData();
  form.append("file", file);
  if (opts?.realWidthCm) form.append("real_width_cm", String(opts.realWidthCm));
  if (opts?.realHeightCm) form.append("real_height_cm", String(opts.realHeightCm));
  if (opts?.furnitureType) form.append("furniture_type", String(opts.furnitureType));
  if (opts?.answers) form.append("confirmation_answers", JSON.stringify(opts.answers));
  const base = getEngineBase();
  const res = await fetch(`${base}/digitize/smart`, { method: "POST", body: form });
  if (!res.ok) { const err = await res.text(); throw new Error(`Smart Auto failed (${res.status}): ${err}`); }
  return res.json();
}
