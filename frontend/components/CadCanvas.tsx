import { CadView } from '../types';
import { renderCadView } from '../services/cadRenderer';

function safePoint(p: any): { x: number; y: number } | null {
  if (!p || typeof p.x !== 'number' || typeof p.y !== 'number') return null;
  return p;
}

/**
 * Renders CAD document to canvas with multi-view layout.
 */
export function renderCadToCanvas(
  ctx: CanvasRenderingContext2D,
  views: CadView[],
  pixelsPerUnit: number,
  width: number,
  height: number
) {
  ctx.clearRect(0, 0, width, height);

  if (!views || views.length === 0) {
    ctx.fillStyle = '#94a3b8';
    ctx.font = '16px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('No views to display', width / 2, height / 2);
    return;
  }

  let yOffset = 30;
  const padding = 40;

  for (const view of views) {
    // View label
    ctx.fillStyle = '#475569';
    ctx.font = 'bold 14px sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(`📐 ${view.name || 'Unnamed View'}`, 10, yOffset);
    yOffset += 25;

    // Compute bounds safely
    const bounds = computeBoundsSafe(view);
    if (!bounds) {
      yOffset += 50;
      continue;
    }

    const scale = Math.min(width * 0.8 / Math.max(bounds.width, 1), 300 / Math.max(bounds.height, 1));
    const effectivePpu = (pixelsPerUnit || 1) * Math.max(scale, 0.1);

    // Render with null-safe renderer
    try {
      renderCadView(ctx, view, effectivePpu, 20, yOffset);
    } catch (e) {
      console.warn('[CadCanvas] renderCadView error:', e);
    }

    yOffset += Math.max(bounds.height * effectivePpu + padding, 100);
  }
}

function computeBoundsSafe(view: CadView) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

  const expand = (p: any) => {
    const pt = safePoint(p);
    if (!pt) return;
    if (pt.x < minX) minX = pt.x;
    if (pt.y < minY) minY = pt.y;
    if (pt.x > maxX) maxX = pt.x;
    if (pt.y > maxY) maxY = pt.y;
  };

  if (!view.primitives || view.primitives.length === 0) return null;

  for (const prim of view.primitives) {
    try {
      const p = prim as any;
      switch (p.type) {
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
    x: minX,
    y: minY,
    width: Math.max(maxX - minX, 10),
    height: Math.max(maxY - minY, 10),
  };
}
