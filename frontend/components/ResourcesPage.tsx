import React, { useState, useEffect } from "react";
import { Database, Package, Layers, BarChart3, Globe, HardDrive, Triangle, Ruler, CheckCircle2, AlertTriangle, Loader2 } from "lucide-react";

const ENGINE_BASE = import.meta.env.VITE_CAD_ENGINE_URL || "/py-api";

export default function ResourcesPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Note: Qdrant has no public-facing route (it's only reachable on the
    // docker network / an internal port, not exposed through nginx) - a
    // direct browser fetch to its REST API can never work for real visitors,
    // so that card is left at its default (0) rather than attempting one.
    Promise.all([
      fetch("/api/product-references", { signal: AbortSignal.timeout(8000) }).then(r => r.json()).catch(() => []),
      fetch(`${ENGINE_BASE}/calibration/report`, { signal: AbortSignal.timeout(8000) }).then(r => r.json()).catch(() => null),
      fetch(`${ENGINE_BASE}/templates`, { signal: AbortSignal.timeout(8000) }).then(r => r.json()).catch(() => null),
    ]).then(([products, cal, templates]) => {
      setData({ products, cal, templates, qdrant: null });
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="flex items-center justify-center py-16"><Loader2 size={20} className="animate-spin text-gray-400" /><span className="ml-2 text-sm text-gray-500">Loading resources...</span></div>;

  const { products, cal, templates, qdrant } = data || {};
  const prodList = Array.isArray(products) ? products : [];

  // Group by manufacturer
  const byBrand: Record<string, any[]> = {};
  for (const p of prodList) {
    const m = p.manufacturer || "unknown";
    if (!byBrand[m]) byBrand[m] = [];
    byBrand[m].push(p);
  }

  const totalCadAssets = prodList.filter((p: any) => p.assets?.some((a: any) => a.assetType === "DXF" || a.assetType === "DWG")).length;
  const totalPdfAssets = prodList.filter((p: any) => p.assets?.some((a: any) => a.assetType === "PDF")).length;
  const totalImages = prodList.reduce((sum: number, p: any) => sum + (p.assets?.filter((a: any) => a.assetType === "IMAGE")?.length || 0), 0);
  const totalComparisons = cal?.comparison_stats?.total || 0;
  const avgScore = cal?.comparison_stats?.avg_score || 0;
  const qdrantPoints = qdrant?.result?.points_count || 0;
  const templateCount = templates?.count || 0;
  const errorCounts = cal?.comparison_stats?.error_counts || {};

  return (
    <div className="max-w-4xl mx-auto py-6 px-4 space-y-4">
      <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
        <Database size={18} className="text-indigo-500" />
        Resource Inventory & Validation Layer
      </h2>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <SummaryCard icon={<Package size={16} />} label="Product References" value={prodList.length} color="bg-blue-50 text-blue-700" />
        <SummaryCard icon={<HardDrive size={16} />} label="CAD Files (DXF/DWG)" value={totalCadAssets} color="bg-purple-50 text-purple-700" />
        <SummaryCard icon={<FileTextIcon />} label="PDF Spec Sheets" value={totalPdfAssets} color="bg-amber-50 text-amber-700" />
        <SummaryCard icon={<Triangle size={16} />} label="Qdrant Geometries" value={qdrantPoints} color="bg-green-50 text-green-700" />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <SummaryCard icon={<Layers size={16} />} label="Engineering Templates" value={templateCount} color="bg-violet-50 text-violet-700" />
        <SummaryCard icon={<BarChart3 size={16} />} label="Validation Runs" value={totalComparisons} color="bg-cyan-50 text-cyan-700" />
        <SummaryCard icon={<CheckCircle2 size={16} />} label="Avg Validation Score" value={`${(avgScore * 100).toFixed(0)}%`} color="bg-emerald-50 text-emerald-700" />
        <SummaryCard icon={<Globe size={16} />} label="Brands" value={Object.keys(byBrand).filter(k => k !== "e2e" && k !== "e2e-test" && k !== "test" && k !== "final" && k !== "demo").length} color="bg-indigo-50 text-indigo-700" />
      </div>

      {/* Error Distribution */}
      {Object.keys(errorCounts).length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-1"><AlertTriangle size={12} /> Validation Error Distribution</p>
          <div className="space-y-1.5">
            {Object.entries(errorCounts).map(([type, count]: [string, any]) => {
              const total = Object.values(errorCounts).reduce((s: number, c: any) => s + c, 0);
              return (
                <div key={type} className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 w-28 shrink-0">{type.replace(/_/g, " ")}</span>
                  <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${(count / total) * 100}%`, backgroundColor: type.includes("edge") ? "#f87171" : "#fbbf24" }} />
                  </div>
                  <span className="text-xs text-gray-500 w-16 text-right">{count} ({(count / total * 100).toFixed(0)}%)</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* By Brand */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <p className="text-xs font-semibold text-gray-700 mb-3">Products by Brand</p>
        <div className="space-y-2">
          {Object.entries(byBrand).filter(([k]) => !["e2e", "e2e-test", "test", "final", "demo"].includes(k)).sort().map(([brand, items]: [string, any]) => {
            const cadCount = items.filter((p: any) => p.assets?.some((a: any) => a.assetType === "DXF" || a.assetType === "DWG")).length;
            const pdfCount = items.filter((p: any) => p.assets?.some((a: any) => a.assetType === "PDF")).length;
            const imageCount = items.reduce((s: number, p: any) => s + (p.assets?.filter((a: any) => a.assetType === "IMAGE")?.length || 0), 0);
            const cats = [...new Set(items.map((p: any) => p.category).filter(Boolean))];
            const productNames = items.map((p: any) => p.productName || p.id.replace(brand + "-", "")).join(", ");

            return (
              <details key={brand} className="group">
                <summary className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-gray-700 capitalize">{brand}</span>
                    <span className="text-gray-400">({items.length} products)</span>
                  </div>
                  <div className="flex items-center gap-3 text-gray-400">
                    {cadCount > 0 && <span title="CAD files">{cadCount} CAD</span>}
                    {pdfCount > 0 && <span title="PDF specs">{pdfCount} PDF</span>}
                    {imageCount > 0 && <span title="Images">{imageCount} img</span>}
                  </div>
                </summary>
                <div className="mt-1.5 px-4 py-2 text-xs text-gray-500 space-y-1">
                  <p><span className="text-gray-400">Categories:</span> {cats.join(", ") || "—"}</p>
                  <p><span className="text-gray-400">Products:</span> {productNames}</p>
                  {items.filter((p: any) => p.assets?.length > 0).slice(0, 3).map((p: any) => (
                    <div key={p.id} className="flex items-center gap-2 text-[10px] text-gray-400">
                      <span className="w-6 h-6 rounded bg-gray-100 flex items-center justify-center text-[9px] font-bold">{p.category?.[0]?.toUpperCase() || "?"}</span>
                      <span className="truncate">{p.productName || p.id}</span>
                      {p.assets?.filter((a: any) => a.assetType === "DXF").slice(0, 2).map((a: any, i: number) => (
                        <span key={i} className="px-1 py-0.5 bg-purple-50 text-purple-600 rounded text-[9px]">DXF</span>
                      ))}
                      {p.assets?.filter((a: any) => a.assetType === "PDF").slice(0, 2).map((a: any, i: number) => (
                        <span key={i} className="px-1 py-0.5 bg-amber-50 text-amber-600 rounded text-[9px]">PDF</span>
                      ))}
                    </div>
                  ))}
                </div>
              </details>
            );
          })}
        </div>
      </div>

      {/* Comparison / Validation Stats */}
      {totalComparisons > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs font-semibold text-gray-700 mb-2">Recent Validation Activity</p>
          <p className="text-xs text-gray-500">{totalComparisons} comparisons run, avg score {(avgScore * 100).toFixed(0)}%</p>
        </div>
      )}
    </div>
  );
}

function SummaryCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: string | number; color: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3">
      <div className={`inline-flex items-center justify-center w-7 h-7 rounded-lg mb-1.5 ${color}`}>{icon}</div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-lg font-bold text-gray-800">{value}</p>
    </div>
  );
}

function FileTextIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="9" y1="15" x2="15" y2="15" />
    </svg>
  );
}
