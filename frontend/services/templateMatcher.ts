/**
 * Parametric Template Matcher — fills template parameters from OCR data.
 *
 * Every filled parameter is labeled with its source:
 *   'measured_from_pixels'  — directly scanned from the image
 *   'ocr_confirmed'         — read from OCR dimension label text
 *   'user_confirmed'        — user typed or corrected value
 *   'ratio_estimated'       — estimated from standard furniture proportions
 *   'default_template'      — hardcoded template default (no confidence)
 *
 * The UI MUST clearly show each parameter's source so the user can
 * distinguish "read from drawing" vs. "guess from template defaults."
 */

import { ParametricTemplate, ParametricMatch, CadPrimitive } from '../types';

export const TEMPLATES: ParametricTemplate[] = [
  {
    name: 'Round Pedestal Table',
    type: 'round_pedestal_table',
    parameters: [
      { name: 'diameter', default: 80, unit: 'cm', description: 'Table top diameter' },
      { name: 'height', default: 70, unit: 'cm', description: 'Total height' },
      { name: 'thickness', default: 3, unit: 'cm', description: 'Table top thickness' },
      { name: 'base_diameter', default: 50, unit: 'cm', description: 'Pedestal base diameter' },
    ],
    views: [
      {
        view: 'top',
        primitives: [
          { type: 'circle', center: { x: 0, y: 0 }, radius: 'diameter/2' } as any,
          { type: 'centerline', p1: { x: '-diameter/2', y: 0 }, p2: { x: 'diameter/2', y: 0 } } as any,
          { type: 'centerline', p1: { x: 0, y: '-diameter/2' }, p2: { x: 0, y: 'diameter/2' } } as any,
        ],
      },
      {
        view: 'front',
        primitives: [
          { type: 'rectangle', p1: { x: '-diameter/2', y: 0 }, p2: { x: 'diameter/2', y: 'thickness' }, layer: 'tabletop' } as any,
          { type: 'rectangle', p1: { x: '-base_diameter/2', y: 'thickness' }, p2: { x: 'base_diameter/2', y: 'height' }, layer: 'pedestal' } as any,
          { type: 'dimension', p1: { x: '-diameter/2', y: 0 }, p2: { x: 'diameter/2', y: 0 }, value: 'diameter', unit: 'cm', orientation: 'horizontal' } as any,
          { type: 'dimension', p1: { x: 0, y: 0 }, p2: { x: 0, y: 'height' }, value: 'height', unit: 'cm', orientation: 'vertical' } as any,
        ],
      },
    ],
  },
  {
    name: 'Rectangular Table',
    type: 'rectangular_table',
    parameters: [
      { name: 'width', default: 120, unit: 'cm', description: 'Table width' },
      { name: 'depth', default: 80, unit: 'cm', description: 'Table depth' },
      { name: 'height', default: 70, unit: 'cm', description: 'Table height' },
      { name: 'leg_width', default: 5, unit: 'cm', description: 'Leg thickness' },
    ],
    views: [
      {
        view: 'top',
        primitives: [
          { type: 'rectangle', p1: { x: '-width/2', y: '-depth/2' }, p2: { x: 'width/2', y: 'depth/2' }, layer: 'tabletop' } as any,
        ],
      },
    ],
  },
  {
    name: 'Sofa',
    type: 'sofa',
    parameters: [
      { name: 'width', default: 200, unit: 'cm', description: 'Total width' },
      { name: 'depth', default: 80, unit: 'cm', description: 'Seat depth' },
      { name: 'height', default: 85, unit: 'cm', description: 'Total height' },
      { name: 'seat_height', default: 45, unit: 'cm', description: 'Seat height from floor' },
    ],
    views: [
      {
        view: 'front',
        primitives: [
          { type: 'rectangle', p1: { x: '-width/2', y: 0 }, p2: { x: 'width/2', y: 'height' }, layer: 'outline' } as any,
          { type: 'line', p1: { x: '-width/2', y: 'seat_height' }, p2: { x: 'width/2', y: 'seat_height' }, layer: 'seat' } as any,
        ],
      },
    ],
  },
  {
    name: 'Cabinet',
    type: 'cabinet',
    parameters: [
      { name: 'width', default: 100, unit: 'cm', description: 'Cabinet width' },
      { name: 'depth', default: 50, unit: 'cm', description: 'Cabinet depth' },
      { name: 'height', default: 180, unit: 'cm', description: 'Cabinet height' },
    ],
    views: [
      {
        view: 'front',
        primitives: [
          { type: 'rectangle', p1: { x: 0, y: 0 }, p2: { x: 'width', y: 'height' }, layer: 'outline' } as any,
          { type: 'line', p1: { x: 'width/2', y: 0 }, p2: { x: 'width/2', y: 'height' }, layer: 'door' } as any,
        ],
      },
    ],
  },
  {
    name: 'Bed Headboard',
    type: 'bed_headboard',
    parameters: [
      { name: 'width', default: 180, unit: 'cm', description: 'Headboard width' },
      { name: 'height', default: 60, unit: 'cm', description: 'Headboard height' },
      { name: 'thickness', default: 5, unit: 'cm', description: 'Headboard thickness' },
    ],
    views: [
      {
        view: 'front',
        primitives: [
          { type: 'rectangle', p1: { x: 0, y: 0 }, p2: { x: 'width', y: 'height' }, layer: 'headboard' } as any,
        ],
      },
    ],
  },
  {
    name: 'Chair',
    type: 'chair',
    parameters: [
      { name: 'seat_width', default: 45, unit: 'cm', description: 'Seat width' },
      { name: 'seat_depth', default: 45, unit: 'cm', description: 'Seat depth' },
      { name: 'seat_height', default: 45, unit: 'cm', description: 'Seat height' },
      { name: 'back_height', default: 45, unit: 'cm', description: 'Backrest height' },
    ],
    views: [
      {
        view: 'front',
        primitives: [
          { type: 'rectangle', p1: { x: '-seat_width/2', y: 'seat_height' }, p2: { x: 'seat_width/2', y: 0 }, layer: 'legs' } as any,
          { type: 'line', p1: { x: '-seat_width/2', y: 'seat_height' }, p2: { x: 'seat_width/2', y: 'seat_height' }, layer: 'seat' } as any,
          { type: 'rectangle', p1: { x: '-seat_width/2', y: 'seat_height' }, p2: { x: 'seat_width/2', y: 'seat_height + back_height' }, layer: 'backrest' } as any,
        ],
      },
    ],
  },
];

/**
 * Describe the source of a parameter value for display.
 */
export interface ParamSource {
  name: string;
  value: number;
  unit: string;
  /** One of: 'measured', 'ocr_confirmed', 'user_confirmed', 'ratio_estimated', 'default_template' */
  source: string;
  confidence: number;
  /** Human-readable explanation */
  note: string;
}

/**
 * Evaluate expression strings like "diameter/2" or "-width/2"
 * against a set of parameter values.
 */
function evalPrimitive(prim: CadPrimitive, params: Record<string, number>): any {
  const evalExpr = (expr: string | number): number => {
    if (typeof expr === 'number') return expr;
    let s = expr;
    for (const [key, val] of Object.entries(params)) {
      s = s.replace(new RegExp(key, 'g'), `(${val})`);
    }
    try {
      return Function(`"use strict"; return (${s})`)();
    } catch {
      return 0;
    }
  };

  const mapPoint = (p: any) => {
    if (typeof p.x === 'string' || typeof p.x === 'number') {
      return { x: evalExpr(p.x), y: evalExpr(p.y) };
    }
    return p;
  };

  switch (prim.type) {
    case 'circle':
      return { ...prim, center: mapPoint(prim.center), radius: evalExpr(prim.radius) };
    case 'arc':
      return { ...prim, center: mapPoint(prim.center), radius: evalExpr(prim.radius) };
    case 'rectangle':
      return { ...prim, p1: mapPoint(prim.p1), p2: mapPoint(prim.p2), width: evalExpr(prim.width), height: evalExpr(prim.height) };
    case 'polyline':
      return { ...prim, points: prim.points.map(mapPoint) };
    case 'line':
    case 'centerline':
      return { ...prim, p1: mapPoint(prim.p1), p2: mapPoint(prim.p2) };
    case 'dimension':
      return { ...prim, p1: mapPoint(prim.p1), p2: mapPoint(prim.p2), value: evalExpr(prim.value) };
    case 'text':
      return { ...prim, position: mapPoint(prim.position) };
    default:
      return prim;
  }
}

/**
 * Match a template by type name and fill parameters from OCR data.
 * Returns detailed source tracking for each parameter.
 */
export function matchTemplate(
  templateType: string,
  ocrParams: Record<string, number>,
  userParams?: Record<string, number>,
): { match: ParametricMatch | null; sources: ParamSource[] } {
  const template = TEMPLATES.find(t => t.type === templateType);
  if (!template) return { match: null, sources: [] };

  // Fill parameters with source tracking
  const filled: Record<string, number> = {};
  const sources: ParamSource[] = [];
  let matches = 0;

  for (const param of template.parameters) {
    let value: number;
    let source: string;
    let confidence: number;
    let note: string;

    // Priority 1: User-confirmed value
    if (userParams && userParams[param.name] !== undefined) {
      value = userParams[param.name];
      source = 'user_confirmed';
      confidence = 1.0;
      note = 'Manually entered by user';
    }
    // Priority 2: OCR-confirmed value
    else if (ocrParams[param.name] !== undefined) {
      value = ocrParams[param.name];
      source = 'ocr_confirmed';
      confidence = 0.85;
      note = 'Read from drawing dimension label';
      matches++;
    }
    // Priority 3: Default template value (no confidence)
    else {
      value = param.default;
      source = 'default_template';
      confidence = 0.15;
      note = 'Template default — verify against source drawing';
    }

    filled[param.name] = value;
    sources.push({
      name: param.name,
      value,
      unit: param.unit,
      source,
      confidence,
      note,
    });
  }

  // Overall confidence: how many params came from real data vs defaults
  const ocrMatchRatio = matches / template.parameters.length;
  const confidence = Math.min(0.3 + ocrMatchRatio * 0.7, 1);

  return {
    match: {
      templateName: template.name,
      type: template.type,
      parameters: filled,
      confidence,
    },
    sources,
  };
}

/**
 * Generate CAD primitives from a template match.
 */
export function generateFromTemplate(match: ParametricMatch): { view: string; primitives: CadPrimitive[] }[] {
  const template = TEMPLATES.find(t => t.type === match.type);
  if (!template) return [];

  return template.views.map(v => ({
    view: v.view,
    primitives: v.primitives.map(prim => evalPrimitive(prim, match.parameters)),
  }));
}

/**
 * Get a human-readable label for a parameter source.
 */
export function getSourceLabel(source: string): string {
  const labels: Record<string, string> = {
    measured: '📏 Measured from pixels',
    ocr_confirmed: '👁️ Read from drawing',
    user_confirmed: '✏️ User confirmed',
    ratio_estimated: '📐 Estimated from proportions',
    default_template: '⚠️ Template default — verify!',
  };
  return labels[source] || `❓ ${source}`;
}

/**
 * Get color for source display (CSS hex).
 */
export function getSourceColor(source: string): string {
  const colors: Record<string, string> = {
    measured: '#22c55e',       // Green
    ocr_confirmed: '#3b82f6',  // Blue
    user_confirmed: '#8b5cf6', // Purple
    ratio_estimated: '#f59e0b',// Amber
    default_template: '#ef4444',// Red
  };
  return colors[source] || '#6b7280';
}
