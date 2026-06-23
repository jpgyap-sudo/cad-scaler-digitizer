import { Point, CadPrimitive, CadView, CadDocument } from '../types';

type DrawStyle = {
  strokeStyle: string;
  lineWidth: number;
  lineDash: number[];
};

function getStyle(primitive: CadPrimitive): DrawStyle {
  const style = 'style' in primitive ? primitive.style : undefined;
  switch (style) {
    case 'hidden': return { strokeStyle: '#94a3b8', lineWidth: 1.5, lineDash: [4, 4] };
    case 'center': return { strokeStyle: '#3b82f6', lineWidth: 1, lineDash: [12, 4, 2, 4] };
    case 'dimension': return { strokeStyle: '#ef4444', lineWidth: 1, lineDash: [] };
    default: return { strokeStyle: '#1e293b', lineWidth: 2, lineDash: [] };
  }
}

function toPoint(p: any): Point | null {
  if (!p || typeof p.x !== 'number' || typeof p.y !== 'number') return null;
  return { x: p.x, y: p.y };
}

function drawArrow(ctx: CanvasRenderingContext2D, from: Point, to: Point, size = 8) {
  const angle = Math.atan2(to.y - from.y, to.x - from.x);
  ctx.save();
  ctx.translate(to.x, to.y);
  ctx.rotate(angle);
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.lineTo(-size, -size / 2);
  ctx.lineTo(-size, size / 2);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

export function renderCadView(
  ctx: CanvasRenderingContext2D,
  view: CadView,
  pixelsPerUnit: number,
  offsetX: number,
  offsetY: number
) {
  const toPixel = (p: Point): Point => ({
    x: p.x * pixelsPerUnit + offsetX,
    y: p.y * pixelsPerUnit + offsetY,
  });

  for (const prim of view.primitives) {
    try {
      const style = getStyle(prim);
      ctx.save();
      ctx.strokeStyle = style.strokeStyle;
      ctx.lineWidth = style.lineWidth;
      ctx.setLineDash(style.lineDash);

      switch (prim.type) {
        case 'circle': {
          const center = toPoint((prim as any).center);
          const radius = (prim as any).radius;
          if (!center || typeof radius !== 'number') break;
          const c = toPixel(center);
          ctx.beginPath();
          ctx.arc(c.x, c.y, radius * pixelsPerUnit, 0, Math.PI * 2);
          ctx.stroke();
          break;
        }
        case 'arc': {
          const center = toPoint((prim as any).center);
          const radius = (prim as any).radius;
          const startAngle = (prim as any).startAngle;
          const endAngle = (prim as any).endAngle;
          if (!center || typeof radius !== 'number') break;
          const c = toPixel(center);
          const start = ((startAngle || 0) * Math.PI) / 180;
          const end = ((endAngle || 360) * Math.PI) / 180;
          ctx.beginPath();
          ctx.arc(c.x, c.y, radius * pixelsPerUnit, start, end);
          ctx.stroke();
          break;
        }
        case 'rectangle': {
          const p1 = toPoint((prim as any).p1);
          const p2 = toPoint((prim as any).p2);
          if (!p1 || !p2) break;
          const r1 = toPixel(p1);
          const r2 = toPixel(p2);
          ctx.strokeRect(r1.x, r1.y, r2.x - r1.x, r2.y - r1.y);
          break;
        }
        case 'polyline': {
          const pts: Point[] = ((prim as any).points || []).map((p: any) => toPixel(p)).filter(Boolean);
          if (pts.length < 2) break;
          ctx.beginPath();
          pts.forEach((p, i) => {
            if (i === 0) ctx.moveTo(p.x, p.y);
            else ctx.lineTo(p.x, p.y);
          });
          if ((prim as any).closed) ctx.closePath();
          ctx.stroke();
          break;
        }
        case 'line':
        case 'centerline': {
          const p1 = toPoint((prim as any).p1);
          const p2 = toPoint((prim as any).p2);
          if (!p1 || !p2) break;
          const lp1 = toPixel(p1);
          const lp2 = toPixel(p2);
          ctx.beginPath();
          ctx.moveTo(lp1.x, lp1.y);
          ctx.lineTo(lp2.x, lp2.y);
          ctx.stroke();
          break;
        }
        case 'dimension': {
          const dp1 = toPoint((prim as any).p1);
          const dp2 = toPoint((prim as any).p2);
          const value = (prim as any).value;
          const unit = (prim as any).unit || '';
          if (!dp1 || !dp2) break;
          const d1 = toPixel(dp1);
          const d2 = toPixel(dp2);
          ctx.beginPath();
          ctx.moveTo(d1.x, d1.y);
          ctx.lineTo(d2.x, d2.y);
          ctx.stroke();
          const ext = 15;
          ctx.setLineDash([2, 2]);
          ctx.beginPath();
          ctx.moveTo(d1.x, d1.y - ext);
          ctx.lineTo(d1.x, d1.y + ext);
          ctx.moveTo(d2.x, d2.y - ext);
          ctx.lineTo(d2.x, d2.y + ext);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.fillStyle = '#ef4444';
          drawArrow(ctx, d1, d2);
          drawArrow(ctx, d2, d1);
          const midX = (d1.x + d2.x) / 2;
          const midY = (d1.y + d2.y) / 2 - 12;
          ctx.fillStyle = '#ef4444';
          ctx.font = 'bold 12px sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'bottom';
          ctx.fillText(value != null ? `${value}${unit}` : '', midX, midY);
          break;
        }
        case 'text': {
          const pos = toPoint((prim as any).position);
          if (!pos) break;
          const pt = toPixel(pos);
          ctx.fillStyle = '#1e293b';
          ctx.font = `${((prim as any).height || 2) * pixelsPerUnit}px sans-serif`;
          ctx.textAlign = 'left';
          ctx.textBaseline = 'top';
          ctx.fillText(String((prim as any).content || ''), pt.x, pt.y);
          break;
        }
      }
      ctx.restore();
    } catch (err) {
      console.warn('[CadRenderer] Skipped bad primitive:', prim.type, err);
      ctx.restore();
    }
  }
}

export function renderCadDocument(
  ctx: CanvasRenderingContext2D,
  doc: CadDocument,
  canvasWidth: number,
  canvasHeight: number
) {
  ctx.clearRect(0, 0, canvasWidth, canvasHeight);
  const ppu = doc.calibration?.pixelsPerUnit || 1;
  let yOffset = 30;
  const padding = 40;
  const labelHeight = 25;

  for (const view of (doc.views || [])) {
    ctx.fillStyle = '#475569';
    ctx.font = 'bold 14px sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(`📐 ${view.name || 'View'}  (1:${view.scale || '?'})`, 10, yOffset);
    yOffset += labelHeight;

    const bounds = getViewBounds(view, ppu);
    if (bounds) {
      ctx.strokeStyle = '#cbd5e1';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.strokeRect(bounds.x + 5, yOffset - 5, bounds.width + 10, bounds.height + 10);
      ctx.setLineDash([]);
      renderCadView(ctx, view, ppu, bounds.x + 10, yOffset);
      yOffset += bounds.height + padding;
    } else {
      yOffset += 100;
    }
  }
}

function getViewBounds(view: CadView, ppu: number) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

  const expand = (p: any) => {
    const pt = toPoint(p);
    if (!pt) return;
    const px = pt.x * ppu;
    const py = pt.y * ppu;
    if (px < minX) minX = px;
    if (py < minY) minY = py;
    if (px > maxX) maxX = px;
    if (py > maxY) maxY = py;
  };

  for (const prim of (view.primitives || [])) {
    try {
      const p = prim as any;
      switch (prim.type) {
        case 'circle': expand(p.center); break;
        case 'arc': expand(p.center); break;
        case 'rectangle': expand(p.p1); expand(p.p2); break;
        case 'polyline': (p.points || []).forEach(expand); break;
        case 'line': case 'centerline': case 'dimension': expand(p.p1); expand(p.p2); break;
        case 'text': expand(p.position); break;
      }
    } catch {}
  }

  if (minX === Infinity) return null;
  return {
    x: minX, y: minY,
    width: Math.max(maxX - minX, 100),
    height: Math.max(maxY - minY, 50),
  };
}
