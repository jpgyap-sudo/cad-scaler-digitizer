import React, { useState, useEffect } from "react";
import { Globe, Loader2, Download, FileText, CheckCircle2, AlertCircle, Zap } from "lucide-react";

const ENGINE_BASE = import.meta.env.VITE_CAD_ENGINE_URL || "/py-api";

function categoryLabel(t: string): string {
  return t.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

export default function CrawlToSvg() {
  const [url, setUrl] = useState("");
  const [categories, setCategories] = useState<string[]>(["table", "sofa", "chair", "bed", "cabinet"]);
  const [category, setCategory] = useState("table");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [optimizing, setOptimizing] = useState(false);
  const [optimized, setOptimized] = useState<string | null>(null);

  // Load categories from templates endpoint
  useEffect(() => {
    fetch(`${ENGINE_BASE}/templates`)
      .then(r => r.json())
      .then(d => {
        const types = [...new Set((d.templates || []).map((t: any) => t.product_type).filter(Boolean))];
        if (types.length > 0) {
          setCategories(types.sort());
          if (!types.includes(category)) setCategory(types[0]);
        }
      })
      .catch(() => {});
  }, []);

  const handleCrawl = async () => {
    if (!url.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setOptimized(null);
    try {
      const r = await fetch(`${ENGINE_BASE}/crawl-to-dxf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim(), category }),
      });
      const data = await r.json();
      if (data.error) { setError(data.error); return; }
      setResult(data);
    } catch (e: any) {
      setError(e.message || "Crawl failed");
    } finally {
      setLoading(false);
    }
  };

  const handleOptimize = async () => {
    const svg = result?.skeleton_svg;
    if (!svg) return;
    setOptimizing(true);
    try {
      const fd = new FormData();
      fd.append("svg_text", svg);
      const r = await fetch(`${ENGINE_BASE}/optimize-svg`, { method: "POST", body: fd });
      const data = await r.json();
      if (data.svg) setOptimized(data.svg);
    } catch { /* ignore */ }
    setOptimizing(false);
  };

  const downloadSvg = (svg: string, label: string) => {
    const blob = new Blob([svg], { type: "image/svg+xml" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${(result?.dxf_file || "preview").replace(".dxf", "")}_${label}.svg`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const copySvg = async (svg: string) => {
    try { await navigator.clipboard.writeText(svg); } catch { /* ignore */ }
  };

  const displaySvg = optimized || result?.skeleton_svg || "";
  const source = result?.skeleton_source || (result?.hero_view_added ? "gemini" : "none");

  return (
    <div className="max-w-4xl mx-auto py-6 px-4">
      <div className="mb-4">
        <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
          <FileText size={18} className="text-emerald-500" />
          Crawl to SVG
        </h2>
        <p className="text-xs text-gray-500">Crawl a product URL and extract an optimized SVG silhouette.</p>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4">
        <div className="flex gap-2 mb-3">
          <input
            type="url" value={url} onChange={e => setUrl(e.target.value)}
            placeholder="https://homeu.ph/products/..."
            className="flex-1 px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none"
            onKeyDown={e => e.key === "Enter" && handleCrawl()}
          />
          <select
            value={category} onChange={e => setCategory(e.target.value)}
            className="px-2 py-2 text-xs border border-gray-300 rounded-lg bg-white outline-none max-w-[150px]"
          >
            {categories.map(c => (
              <option key={c} value={c}>{categoryLabel(c)}</option>
            ))}
          </select>
          <button onClick={handleCrawl} disabled={loading || !url.trim()}
            className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white text-xs rounded-lg hover:bg-emerald-700 disabled:opacity-50">
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Globe size={14} />}
            {loading ? "Crawling..." : "Crawl & Extract SVG"}
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
            <AlertCircle size={14} /> {error}
          </div>
        )}
      </div>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={20} className="animate-spin text-emerald-500" />
          <span className="ml-3 text-sm text-gray-500">Crawling product page and generating SVG...</span>
        </div>
      )}

      {result && !loading && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-gray-700">SVG Preview</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  source === "gemini" ? "bg-purple-100 text-purple-700" : "bg-gray-100 text-gray-600"
                }`}>
                  {source === "gemini" ? "Gemini-traced" : "Geometric"}
                </span>
              </div>
              <div className="flex gap-1">
                <button onClick={handleOptimize} disabled={optimizing}
                  className="flex items-center gap-1 px-2 py-1 text-[10px] bg-amber-50 text-amber-600 rounded hover:bg-amber-100 disabled:opacity-50">
                  <Zap size={10} /> {optimizing ? "..." : "Optimize"}
                </button>
                <button onClick={() => downloadSvg(displaySvg, source)}
                  className="flex items-center gap-1 px-2 py-1 text-[10px] bg-blue-50 text-blue-600 rounded hover:bg-blue-100">
                  <Download size={10} /> SVG
                </button>
              </div>
            </div>
            {displaySvg ? (
              <div className="border border-gray-100 rounded overflow-hidden bg-white">
                <div className="w-full h-[300px] overflow-auto flex items-center justify-center bg-gray-50">
                  <div className="max-w-full max-h-full" dangerouslySetInnerHTML={{ __html: displaySvg }} />
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-xs text-gray-400">No SVG available</div>
            )}
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
            <h3 className="text-xs font-semibold text-gray-700">Details</h3>
            <div className="space-y-2 text-[11px]">
              <div className="flex justify-between"><span className="text-gray-500">Source</span><span className="font-mono">{source}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">SVG size</span><span className="font-mono">{displaySvg.length.toLocaleString()} chars</span></div>
              {result.dxf_file && (
                <div className="flex justify-between"><span className="text-gray-500">DXF file</span><span className="font-mono text-[9px] truncate max-w-[140px]">{result.dxf_file}</span></div>
              )}
              {result.hero_view_added && (
                <div className="flex items-center gap-1 text-emerald-600"><CheckCircle2 size={10} /> Hero view in DXF</div>
              )}
              {optimized && (
                <div className="flex items-center gap-1 text-emerald-600"><CheckCircle2 size={10} /> SVG optimized</div>
              )}
            </div>
            <div className="flex flex-col gap-1.5 pt-2 border-t border-gray-100">
              <button onClick={() => copySvg(displaySvg)}
                className="w-full py-1.5 text-[10px] bg-gray-50 text-gray-600 rounded hover:bg-gray-100">Copy SVG to clipboard</button>
              <button onClick={() => window.open(`${ENGINE_BASE}/preview/svg/${result.dxf_file?.replace('.dxf', '')}`, '_blank')}
                className="w-full py-1.5 text-[10px] bg-gray-50 text-gray-600 rounded hover:bg-gray-100">Open raw SVG</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
