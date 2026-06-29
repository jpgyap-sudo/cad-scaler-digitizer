import React, { useEffect, useState } from "react";
import { History, Loader2, Download, ExternalLink, RefreshCw } from "lucide-react";

const ENGINE_BASE = import.meta.env.VITE_CAD_ENGINE_URL || "/py-api";

interface HistoryItem {
  job_id: string;
  furniture_type: string;
  dxf_file: string;
  quality_score: number | null;
  dimensions: Record<string, number>;
  preview_urls: { svg?: string; dxf?: string };
  created_at: string;
}

function skeletonUrl(item: HistoryItem): string {
  const d = item.dimensions || {};
  const w = d.width_cm ?? d.length_cm ?? d.top_diameter_cm ?? 100;
  const depth = d.depth_cm;
  const h = d.overall_height_cm ?? d.height_cm;
  const params = new URLSearchParams({ width_cm: String(w) });
  if (depth) params.set("depth_cm", String(depth));
  if (h) params.set("height_cm", String(h));
  return `${ENGINE_BASE}/skeleton/${item.furniture_type}?${params.toString()}`;
}

export default function HistoryPage() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    fetch(`${ENGINE_BASE}/history?limit=30`, { signal: AbortSignal.timeout(10000) })
      .then((r) => r.json())
      .then((data) => {
        if (data.error) {
          setError(data.error);
          setItems([]);
        } else {
          setItems(data.items || []);
        }
      })
      .catch(() => setError("Could not load history"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="max-w-4xl mx-auto py-6 px-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
          <History size={18} className="text-indigo-500" />
          Generation History
        </h2>
        <button onClick={load} className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600">
          <RefreshCw size={12} /> Refresh
        </button>
      </div>
      <p className="text-xs text-gray-500 mb-4">
        Past DXF generations. Drawings persisted to CDN storage show a live skeleton
        preview and the actual generated drawing side by side; older or unpersisted
        jobs show the skeleton only.
      </p>

      {loading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 size={20} className="animate-spin text-gray-400" />
        </div>
      )}

      {!loading && error && (
        <p className="text-sm text-red-500 text-center py-8">{error}</p>
      )}

      {!loading && !error && items.length === 0 && (
        <p className="text-sm text-gray-400 text-center py-8">
          No generations yet — digitize a furniture photo to see it here.
        </p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {items.map((item) => (
          <div key={item.job_id} className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <div className="grid grid-cols-2 divide-x divide-gray-100 bg-gray-50">
              <div className="p-1.5">
                <p className="text-[9px] text-gray-400 text-center mb-1">Skeleton</p>
                <img
                  src={skeletonUrl(item)}
                  alt="Skeleton preview"
                  className="w-full h-28 object-contain bg-white rounded"
                  onError={(e) => { (e.target as HTMLImageElement).style.opacity = "0.2"; }}
                />
              </div>
              <div className="p-1.5">
                <p className="text-[9px] text-gray-400 text-center mb-1">Generated DXF</p>
                {item.preview_urls?.svg ? (
                  <img
                    src={item.preview_urls.svg}
                    alt="DXF preview"
                    className="w-full h-28 object-contain bg-white rounded"
                  />
                ) : (
                  <div className="w-full h-28 flex items-center justify-center text-[10px] text-gray-300 bg-white rounded">
                    Not persisted
                  </div>
                )}
              </div>
            </div>
            <div className="p-2.5 flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-gray-700">
                  {item.furniture_type.replace(/_/g, " ")}
                </p>
                <p className="text-[10px] text-gray-400">
                  {new Date(item.created_at).toLocaleString()}
                  {item.quality_score != null && ` · score ${(item.quality_score * 100).toFixed(0)}%`}
                </p>
              </div>
              {item.preview_urls?.dxf ? (
                <a
                  href={item.preview_urls.dxf}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-[10px] text-indigo-600 hover:text-indigo-800 bg-indigo-50 px-2 py-1 rounded"
                >
                  <Download size={11} /> DXF
                </a>
              ) : (
                <span className="flex items-center gap-1 text-[10px] text-gray-300 px-2 py-1">
                  <ExternalLink size={11} /> n/a
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
