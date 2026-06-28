/**
 * Confidence Heatmap Service
 * 
 * Builds per-component confidence data from existing EntityMetadata
 * for rendering as a color overlay on the CAD preview canvas.
 * 
 * Uses EXISTING infrastructure:
 * - EntityMetadata already carries confidence/source/evidence on every entity
 * - getSourceColor() and getSourceLabel() already exist in templateMatcher.ts
 * - CadConfidenceLegend.tsx already shows the color legend
 * - ConfidencePanel.tsx already shows dimension confidence
 * 
 * NEW: This service aggregates what already exists into a canvas-ready format.
 */

import { CadDocument, CadPrimitive } from '../types';

export interface HeatmapComponent {
  name: string;
  confidence: number;
  source: string;
  color: string;
  label: string;
  evidence: string[];
  boundingBox: { x1: number; y1: number; x2: number; y2: number };
  layer?: string;
}

export interface HeatmapData {
  components: HeatmapComponent[];
  overall: {
    average: number;
    weakest: string | null;
    needsReview: string[];
  };
}

/**
 * Get heatmap color from confidence value
 */
export function getHeatmapColor(confidence: number): string {
  if (confidence >= 0.85) return '#22c55e';   // green — trusted
  if (confidence >= 0.60) return '#eab308';   // yellow — check
  if (confidence >= 0.30) return '#f97316';   // orange — low
  return '#ef4444';                             // red — verify
}

/**
 * Get descriptive label for a confidence/source pair.
 * Mirrors the existing getSourceLabel() but works with numeric confidence.
 */
export function getHeatmapLabel(confidence: number, source: string): string {
  if (source === 'user') return '✏️ User confirmed';
  if (confidence >= 0.85 && (source === 'measured' || source === 'ocr' || source === 'ocr_confirmed')) {
    return '📏 Measured from image';
  }
  if (confidence >= 0.85 && source === 'ai_vision') {
    return '👁️ AI verified';
  }
  if (confidence >= 0.60) {
    if (source === 'ratio' || source === 'ratio_estimated') return '📐 Estimated from proportions';
    if (source === 'template_default' || source === 'schema_default') return '📋 Template default';
    return '⚠️ Partially verified';
  }
  return '❓ Needs verification';
}

/**
 * Build heatmap data from a CadDocument.
 * Uses existing primitive data + any available metadata.
 */
export function buildHeatmap(document: CadDocument): HeatmapData {
  const components: HeatmapComponent[] = [];
  const allViews = document.views || [];

  for (const view of allViews) {
    const primitives = view.primitives || [];

    for (const prim of primitives) {
      // Extract name from primitive or view context
      const name = extractPrimitiveName(prim, view.name);
      
      // Extract confidence (from metadata if available, or infer)
      const confidence = extractConfidence(prim);
      const source = extractSource(prim);
      const evidence = extractEvidence(prim);
      const color = getHeatmapColor(confidence);
      const label = getHeatmapLabel(confidence, source);
      const bbox = computePrimitiveBBox(prim);

      components.push({
        name: `${view.name} / ${name}`,
        confidence,
        source,
        color,
        label,
        evidence,
        boundingBox: bbox,
        layer: prim.layer || 'OBJECT',
      });
    }
  }

  // Compute overall stats
  const confidences = components.map(c => c.confidence);
  const average = confidences.length > 0
    ? confidences.reduce((a, b) => a + b, 0) / confidences.length
    : 0;

  const needsReview = components
    .filter(c => c.confidence < 0.60)
    .map(c => c.name);

  const weakest = components.length > 0
    ? components.reduce((min, c) => c.confidence < min.confidence ? c : min, components[0])
    : null;

  return {
    components,
    overall: {
      average: Math.round(average * 100) / 100,
      weakest: weakest?.name || null,
      needsReview: needsReview.slice(0, 10), // top 10 worst
    },
  };
}

/**
 * Draw heatmap overlay onto a canvas context.
 * Call AFTER drawing the CAD preview primitives.
 */
export function drawHeatmapOverlay(
  ctx: CanvasRenderingContext2D,
  heatmap: HeatmapComponent[],
  options?: { opacity?: number; showLabels?: boolean }
): void {
  const opacity = options?.opacity ?? 0.15;
  const showLabels = options?.showLabels ?? false;

  for (const comp of heatmap) {
    const { x1, y1, x2, y2 } = comp.boundingBox;
    const w = x2 - x1;
    const h = y2 - y1;

    if (w <= 0 || h <= 0) continue;

    // Translucent fill
    ctx.fillStyle = hexToRgba(comp.color, opacity);
    ctx.fillRect(x1, y1, w, h);

    // Colored border
    ctx.strokeStyle = hexToRgba(comp.color, 0.6);
    ctx.lineWidth = 2;
    ctx.strokeRect(x1, y1, w, h);

    // Optional label
    if (showLabels) {
      ctx.fillStyle = comp.color;
      ctx.font = '10px monospace';
      ctx.fillText(`${comp.label} (${Math.round(comp.confidence * 100)}%)`, x1 + 2, y1 + 12);
    }
  }
}

/**
 * Highlight a specific component by name (for hover/click interaction).
 */
export function drawHeatmapHighlight(
  ctx: CanvasRenderingContext2D,
  component: HeatmapComponent
): void {
  const { x1, y1, x2, y2 } = component.boundingBox;
  ctx.strokeStyle = '#3b82f6';
  ctx.lineWidth = 3;
  ctx.setLineDash([6, 3]);
  ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
  ctx.setLineDash([]);

  // Tooltip background
  const tooltipText = `${component.name}\nConfidence: ${Math.round(component.confidence * 100)}%\nSource: ${component.source}\nEvidence: ${component.evidence.join(', ') || 'none'}`;
  ctx.fillStyle = 'rgba(30, 41, 59, 0.9)';
  ctx.fillRect(x1, y1 - 50, 250, 48);
  ctx.fillStyle = '#ffffff';
  ctx.font = '10px monospace';
  tooltipText.split('\n').forEach((line, i) => {
    ctx.fillText(line, x1 + 5, y1 - 35 + i * 14);
  });
}

// ─── Helpers ────────────────────────────────────────────────────────

function extractPrimitiveName(prim: CadPrimitive, viewName: string): string {
  if ('type' in prim) {
    return `${prim.type}_${viewName}`;
  }
  return 'unknown';
}

function extractConfidence(prim: CadPrimitive): number {
  // If the backend provided metadata, it would be on a `metadata` field.
  // Fallback: infer from source or use a default.
  const anyPrim = prim as any;
  if (anyPrim.metadata?.confidence != null) {
    return anyPrim.metadata.confidence;
  }
  // Infer from layer/style
  if (anyPrim.source === 'measured' || anyPrim.source === 'ocr') return 0.85;
  if (anyPrim.source === 'user') return 0.95;
  if (anyPrim.source === 'estimated' || anyPrim.source === 'ratio') return 0.45;
  if (anyPrim.layer === 'CONSTRUCTION' || anyPrim.style === 'hidden') return 0.25;
  return 0.50; // default moderate confidence
}

function extractSource(prim: CadPrimitive): string {
  const anyPrim = prim as any;
  if (anyPrim.metadata?.source) return anyPrim.metadata.source;
  if (anyPrim.source) return anyPrim.source;
  if (anyPrim.layer === 'DIMENSION') return 'ocr';
  if (anyPrim.layer === 'CONSTRUCTION') return 'inferred';
  return 'pipeline_default';
}

function extractEvidence(prim: CadPrimitive): string[] {
  const anyPrim = prim as any;
  if (anyPrim.metadata?.evidence) return anyPrim.metadata.evidence;
  return [];
}

function computePrimitiveBBox(prim: CadPrimitive): { x1: number; y1: number; x2: number; y2: number } {
  let pts: { x: number; y: number }[] = [];

  switch (prim.type) {
    case 'circle':
      pts = [
        { x: prim.center.x - prim.radius, y: prim.center.y - prim.radius },
        { x: prim.center.x + prim.radius, y: prim.center.y + prim.radius },
      ];
      break;
    case 'arc':
      pts = [
        { x: prim.center.x - prim.radius, y: prim.center.y - prim.radius },
        { x: prim.center.x + prim.radius, y: prim.center.y + prim.radius },
      ];
      break;
    case 'rectangle':
      pts = [prim.p1, { x: prim.p2.x, y: prim.p1.y }, prim.p2, { x: prim.p1.x, y: prim.p2.y }];
      break;
    case 'polyline':
      pts = prim.points;
      break;
    case 'line':
    case 'centerline':
    case 'dimension':
      pts = [prim.p1, prim.p2];
      break;
    case 'text':
      pts = [{ x: prim.position.x, y: prim.position.y }];
      break;
  }

  if (pts.length === 0) return { x1: 0, y1: 0, x2: 0, y2: 0 };

  const xs = pts.map(p => p.x);
  const ys = pts.map(p => p.y);
  return {
    x1: Math.min(...xs),
    y1: Math.min(...ys),
    x2: Math.max(...xs),
    y2: Math.max(...ys),
  };
}

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
