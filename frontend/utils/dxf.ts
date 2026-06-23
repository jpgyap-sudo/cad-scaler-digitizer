import { CadPrimitive, CadDocument } from '../types';

function dxfHeader(): string {
  return '  0\nSECTION\n  2\nHEADER\n  9\n$ACADVER\n  1\nAC1009\n  0\nENDSEC\n';
}

function dxfTables(): string {
  return `  0
SECTION
  2
TABLES
  0
TABLE
  2
LTYPE
 70
1
  0
LTYPE
  2
CENTER
 70
0
  3
Center __ _ __ _ __ _ __ _ __ _
 72
65
 73
4
 40
3.175
 49
1.905
 49
0.635
 49
0.635
 49
0.635
  0
ENDTAB
  0
TABLE
  2
LAYER
 70
1
  0
LAYER
  2
0
 70
0
 62
7
  6
CONTINUOUS
  0
ENDTAB
  0
ENDSEC
`;
}

function exportCircle(prim: any, layer: string): string {
  return `  0
CIRCLE
  8
${layer}
 10
${prim.center.x.toFixed(4)}
 20
${prim.center.y.toFixed(4)}
 30
0.0
 40
${prim.radius.toFixed(4)}
`;
}

function exportArc(prim: any, layer: string): string {
  return `  0
ARC
  8
${layer}
 10
${prim.center.x.toFixed(4)}
 20
${prim.center.y.toFixed(4)}
 30
0.0
 40
${prim.radius.toFixed(4)}
 50
${prim.startAngle.toFixed(4)}
 51
${prim.endAngle.toFixed(4)}
`;
}

function exportLine(p1: any, p2: any, layer: string): string {
  return `  0
LINE
  8
${layer}
 10
${p1.x.toFixed(4)}
 20
${p1.y.toFixed(4)}
 30
0.0
 11
${p2.x.toFixed(4)}
 21
${p2.y.toFixed(4)}
 31
0.0
`;
}

function exportPolyline(prim: any, layer: string): string {
  const flags = prim.closed ? 1 : 0;
  let dxf = `  0
LWPOLYLINE
  8
${layer}
 90
${prim.points.length}
 70
${flags}
`;
  prim.points.forEach((p: any) => {
    dxf += ` 10
${p.x.toFixed(4)}
 20
${p.y.toFixed(4)}
`;
  });
  return dxf;
}

function exportText(prim: any, layer: string): string {
  return `  0
TEXT
  8
${layer}
 10
${prim.position.x.toFixed(4)}
 20
${prim.position.y.toFixed(4)}
 30
0.0
 40
${prim.height || 2.5}
  1
${prim.content}
`;
}

export function generateDXF(doc: CadDocument): string {
  let dxf = '';
  dxf += dxfHeader();
  dxf += dxfTables();
  dxf += '  0\nSECTION\n  2\nENTITIES\n';

  const ppu = doc.calibration.pixelsPerUnit || 1;

  for (const view of doc.views) {
    for (const prim of view.primitives) {
      const layer = 'layer' in prim ? prim.layer || '0' : '0';

      // Scale to real units
      const scalePrim = scalePrimitive(prim, 1 / ppu);

      switch (scalePrim.type) {
        case 'circle':
          dxf += exportCircle(scalePrim, layer);
          break;
        case 'arc':
          dxf += exportArc(scalePrim, layer);
          break;
        case 'rectangle':
          dxf += exportLine(scalePrim.p1, { x: scalePrim.p2.x, y: scalePrim.p1.y }, layer);
          dxf += exportLine({ x: scalePrim.p2.x, y: scalePrim.p1.y }, scalePrim.p2, layer);
          dxf += exportLine(scalePrim.p2, { x: scalePrim.p1.x, y: scalePrim.p2.y }, layer);
          dxf += exportLine({ x: scalePrim.p1.x, y: scalePrim.p2.y }, scalePrim.p1, layer);
          break;
        case 'polyline':
          dxf += exportPolyline(scalePrim, layer);
          break;
        case 'line':
        case 'centerline':
          dxf += exportLine(scalePrim.p1, scalePrim.p2, layer);
          break;
        case 'dimension':
          // Export dimension line + text
          dxf += exportLine(scalePrim.p1, scalePrim.p2, 'dimension');
          dxf += exportText({
            position: { x: (scalePrim.p1.x + scalePrim.p2.x) / 2, y: (scalePrim.p1.y + scalePrim.p2.y) / 2 + 5 },
            content: `${scalePrim.value}${scalePrim.unit}`,
            height: 2.5,
          }, 'dimension');
          break;
        case 'text':
          dxf += exportText(scalePrim, layer);
          break;
      }
    }
  }

  dxf += '  0\nENDSEC\n  0\nEOF\n';
  return dxf;
}

function scalePrimitive(prim: CadPrimitive, factor: number): any {
  const scalePoint = (p: { x: number; y: number }) => ({
    x: p.x * factor,
    y: p.y * factor,
  });

  switch (prim.type) {
    case 'circle':
      return { ...prim, center: scalePoint(prim.center), radius: prim.radius * factor };
    case 'arc':
      return { ...prim, center: scalePoint(prim.center), radius: prim.radius * factor };
    case 'rectangle':
      return { ...prim, p1: scalePoint(prim.p1), p2: scalePoint(prim.p2) };
    case 'polyline':
      return { ...prim, points: prim.points.map(scalePoint) };
    case 'line':
    case 'centerline':
    case 'dimension':
      return { ...prim, p1: scalePoint(prim.p1), p2: scalePoint(prim.p2) };
    case 'text':
      return { ...prim, position: scalePoint(prim.position) };
    default:
      return prim;
  }
}
