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
 * Evaluate expression strings like "diameter/2" or "-width/2" 
 * against a set of parameter values.
 */
function evalPrimitive(prim: CadPrimitive, params: Record<string, number>): any {
  const evalExpr = (expr: string | number): number => {
    if (typeof expr === 'number') return expr;
    // Replace parameter names with values
    let s = expr;
    for (const [key, val] of Object.entries(params)) {
      s = s.replace(new RegExp(key, 'g'), `(${val})`);
    }
    try {
      // Safe evaluation: only basic arithmetic
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
 */
export function matchTemplate(
  templateType: string,
  ocrParams: Record<string, number>
): ParametricMatch | null {
  const template = TEMPLATES.find(t => t.type === templateType);
  if (!template) return null;

  // Fill parameters, using OCR values where available, defaults otherwise
  const filled: Record<string, number> = {};
  let matches = 0;
  for (const param of template.parameters) {
    if (ocrParams[param.name] !== undefined) {
      filled[param.name] = ocrParams[param.name];
      matches++;
    } else {
      filled[param.name] = param.default;
    }
  }

  const confidence = Math.min(0.5 + (matches / template.parameters.length) * 0.5, 1);

  return {
    templateName: template.name,
    type: template.type,
    parameters: filled,
    confidence,
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
