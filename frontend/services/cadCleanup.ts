import { CadPrimitive } from '../types';

/**
 * Shape Reconstruction Pipeline:
 * Cleans up raw CAD primitives into production-ready output.
 */
export function cleanupCadPrimitives(primitives: CadPrimitive[]): CadPrimitive[] {
  let cleaned = [...primitives];
  cleaned = deduplicatePrimitives(cleaned);
  cleaned = snapEndpoints(cleaned, 5);
  cleaned = mergeCollinearLines(cleaned);
  cleaned = straightenNearHV(cleaned);
  cleaned = removeShortPrimitives(cleaned, 3);
  return cleaned;
}

/** Remove duplicate primitives within tolerance */
function deduplicatePrimitives(prims: CadPrimitive[], tolerance = 8): CadPrimitive[] {
  const kept: CadPrimitive[] = [];
  for (const prim of prims) {
    let dup = false;
    for (const k of kept) {
      if (prim.type !== k.type) continue;
      if (primitivesEqual(prim, k, tolerance)) { dup = true; break; }
    }
    if (!dup) kept.push(prim);
  }
  return kept;
}

function primitivesEqual(a: CadPrimitive, b: CadPrimitive, tol: number): boolean {
  if (a.type === 'circle' && b.type === 'circle') {
    return dist(a.center, b.center) < tol && Math.abs(a.radius - b.radius) < tol;
  }
  if (a.type === 'line' && b.type === 'line') {
    return (dist(a.p1, b.p1) < tol && dist(a.p2, b.p2) < tol) ||
           (dist(a.p1, b.p2) < tol && dist(a.p2, b.p1) < tol);
  }
  return false;
}

/** Snap endpoints that are close together */
function snapEndpoints(prims: CadPrimitive[], snapDist: number): CadPrimitive[] {
  // Collect all endpoints
  const points: { x: number; y: number }[] = [];
  for (const prim of prims) {
    if (prim.type === 'line' || prim.type === 'centerline' || prim.type === 'dimension') {
      points.push(prim.p1, prim.p2);
    } else if (prim.type === 'polyline') {
      prim.points.forEach(p => points.push(p));
    }
  }
  if (points.length < 2) return prims;

  // Find clusters
  const clusters: { x: number; y: number }[][] = [];
  for (const p of points) {
    let added = false;
    for (const cluster of clusters) {
      if (dist(p, cluster[0]) < snapDist) {
        cluster.push(p);
        added = true;
        break;
      }
    }
    if (!added) clusters.push([p]);
  }

  // Compute cluster centers
  const centers = clusters.map(cluster => ({
    x: cluster.reduce((s, p) => s + p.x, 0) / cluster.length,
    y: cluster.reduce((s, p) => s + p.y, 0) / cluster.length,
  }));

  // Snap points to nearest center
  return prims.map(prim => {
    if (prim.type === 'line' || prim.type === 'centerline' || prim.type === 'dimension') {
      return { ...prim, p1: snapToNearest(prim.p1, centers, snapDist), p2: snapToNearest(prim.p2, centers, snapDist) };
    }
    if (prim.type === 'polyline') {
      return { ...prim, points: prim.points.map(p => snapToNearest(p, centers, snapDist)) };
    }
    return prim;
  });
}

function snapToNearest(p: { x: number; y: number }, targets: { x: number; y: number }[], maxDist: number) {
  let best = p;
  let bestDist = maxDist;
  for (const t of targets) {
    const d = dist(p, t);
    if (d < bestDist) { bestDist = d; best = t; }
  }
  return best;
}

/** Merge collinear line segments into longer lines */
function mergeCollinearLines(prims: CadPrimitive[]): CadPrimitive[] {
  const lines = prims.filter(p => p.type === 'line' || p.type === 'centerline') as any[];
  const others = prims.filter(p => p.type !== 'line' && p.type !== 'centerline');
  const merged: typeof lines = [];
  const used = new Set<number>();

  for (let i = 0; i < lines.length; i++) {
    if (used.has(i)) continue;
    let best = { ...lines[i] };
    used.add(i);

    for (let j = i + 1; j < lines.length; j++) {
      if (used.has(j)) continue;
      const mergedLine = tryMerge(best, lines[j], 3);
      if (mergedLine) {
        best = mergedLine;
        used.add(j);
      }
    }
    merged.push(best);
  }

  return [...merged, ...others];
}

function tryMerge(a: { p1: { x: number; y: number }; p2: { x: number; y: number } }, b: { p1: { x: number; y: number }; p2: { x: number; y: number } }, angleTol: number) {
  const angleDiff = (a1: number, a2: number) => {
    let d = Math.abs(a1 - a2);
    return Math.min(d, Math.PI - d);
  };

  const angleA = Math.atan2(a.p2.y - a.p1.y, a.p2.x - a.p1.x);
  const angleB = Math.atan2(b.p2.y - b.p1.y, b.p2.x - b.p1.x);

  if (angleDiff(angleA, angleB) * (180 / Math.PI) > angleTol) return null;

  // Check if endpoints connect
  if (dist(a.p2, b.p1) < 10) return { p1: a.p1, p2: b.p2 };
  if (dist(a.p1, b.p2) < 10) return { p1: b.p1, p2: a.p2 };
  if (dist(a.p1, b.p1) < 10) return { p1: a.p2, p2: b.p2 };
  if (dist(a.p2, b.p2) < 10) return { p1: a.p1, p2: b.p1 };

  return null;
}

/** Straighten lines that are almost horizontal or vertical */
function straightenNearHV(prims: CadPrimitive[], angleTol = 3): CadPrimitive[] {
  return prims.map(prim => {
    if (prim.type !== 'line' && prim.type !== 'centerline') return prim;
    const dx = prim.p2.x - prim.p1.x;
    const dy = prim.p2.y - prim.p1.y;
    const angle = Math.abs(Math.atan2(dy, dx)) * (180 / Math.PI);

    if (angle < angleTol || Math.abs(angle - 180) < angleTol) {
      // Nearly horizontal
      return { ...prim, p2: { x: prim.p2.x, y: prim.p1.y } };
    }
    if (Math.abs(angle - 90) < angleTol) {
      // Nearly vertical
      return { ...prim, p2: { x: prim.p1.x, y: prim.p2.y } };
    }
    return prim;
  });
}

/** Remove primitives shorter than threshold */
function removeShortPrimitives(prims: CadPrimitive[], minLength: number): CadPrimitive[] {
  return prims.filter(prim => {
    if (prim.type === 'line' || prim.type === 'centerline') {
      return dist(prim.p1, prim.p2) >= minLength;
    }
    if (prim.type === 'circle') {
      return prim.radius * 2 >= minLength;
    }
    return true;
  });
}

function dist(a: { x: number; y: number }, b: { x: number; y: number }) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}
