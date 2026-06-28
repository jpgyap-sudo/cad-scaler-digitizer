import React, { useState } from "react";
import { Globe, Loader2, Download, AlertCircle, ExternalLink, Ruler, HelpCircle, Lightbulb, Maximize2 } from "lucide-react";

const ENGINE_BASE = import.meta.env.VITE_CAD_ENGINE_URL || "/py-api";

interface PageDimensions {
  width_cm?: number;
  height_cm?: number;
  overall_height_cm?: number;
  depth_cm?: number;
  length_cm?: number;
  sizes?: Array<{ width: number; length: number; height: number }>;
}

interface CrawlResult {
  status: string;
  page_url?: string;
  image_url?: string;
  dxf_file?: string;
  download_url?: string;
  preview_svg?: string;
  skeleton_svg?: string;
  page_dimensions?: PageDimensions;
  detected_dimensions?: Record<string, number>;
  comparison?: {
    overall_score: number;
    edge_overlap_score: number;
    entity_match_score: number;
    error_count: number;
  };
  error?: string;
}

export default function CrawlInput() {
  const [url, setUrl] = useState("");
  const [category, setCategory] = useState("table");
  const [result, setResult] = useState<CrawlResult | null>(null);
  const [loading, setLoading] = useState(false);

  const categories = [
    "table", "sofa", "chair", "bed", "cabinet", "lighting", "rug", "furniture",
  ];

  const handleCrawl = async () => {
    if (!url.trim()) return;
    setLoading(true);
    setResult(null);

    try {
      const res = await fetch(`${ENGINE_BASE}/crawl-to-dxf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim(), category }),
      });
      const data: CrawlResult = await res.json();
      setResult(data);
    } catch (err) {
      setResult({ status: "failed", error: (err as Error).message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 mb-4">
      <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
        <Globe size={16} className="text-blue-500" />
        Crawl Product URL → Auto-Digitize
      </h3>

      <div className="flex gap-2">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://homeu.ph/products/tangerie-dining-table"
          className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
          onKeyDown={(e) => e.key === "Enter" && handleCrawl()}
        />
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="px-2 py-2 text-sm border border-gray-300 rounded-lg bg-white"
        >
          {categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <button
          onClick={handleCrawl}
          disabled={loading || !url.trim()}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 whitespace-nowrap"
        >
          {loading ? (
            <><Loader2 size={14} className="animate-spin" /> Crawling...</>
          ) : (
            <><Globe size={14} /> Crawl & Digitize</>
          )}
        </button>
      </div>

      {/* Examples / help */}
      <details className="mt-2">
        <summary className="text-xs text-gray-400 hover:text-gray-600 cursor-pointer flex items-center gap-1">
          <Lightbulb size={12} /> Try with example URLs
        </summary>
        <div className="mt-1.5 space-y-1">
          <button onClick={() => setUrl("https://homeu.ph/products/tangerie-dining-table")}
            className="block w-full text-left text-xs text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-2 py-1 rounded">
            HomeU — Tangerie Dining Table
          </button>
          <button onClick={() => setUrl("https://homeu.ph/products/glenn-modern-sofa")}
            className="block w-full text-left text-xs text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-2 py-1 rounded">
            HomeU — Glenn Modern Sofa
          </button>
          <button onClick={() => setUrl("https://homeu.ph/products/evon-modern-bed")}
            className="block w-full text-left text-xs text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-2 py-1 rounded">
            HomeU — Evon Modern Bed
          </button>
        </div>
      </details>

      {/* Error */}
      {result?.status === "failed" && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
          <AlertCircle size={16} className="text-red-500 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-medium text-red-700">Failed</p>
            <p className="text-xs text-red-600 mt-0.5">{result.error}</p>
          </div>
        </div>
      )}

      {/* Success Result */}
      {result?.status === "completed" && (
        <div className="mt-3 space-y-3">
          {/* Image preview */}
          {result.image_url && (
            <div className="flex gap-3">
              <img
                src={result.image_url}
                alt="Product"
                className="w-20 h-20 object-cover rounded-lg border border-gray-200"
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
              />
              <div className="flex-1 min-w-0">
                {/* DXF Download */}
                {result.dxf_file && result.download_url && (
                  <a
                    href={result.download_url.startsWith("/") ? result.download_url : `${ENGINE_BASE}${result.download_url}`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 text-blue-700 text-sm rounded-lg hover:bg-blue-100 mb-1"
                  >
                    <Download size={14} />
                    Download DXF
                  </a>
                )}
                {/* Phase 3: SVG Skeleton Preview (before DXF download) */}
                {result.skeleton_svg && (
                  <div className="mt-2">
                    <p className="text-[10px] font-semibold text-gray-500 mb-1 flex items-center gap-1">
                      <Ruler size={10} /> Quick Skeleton Preview (before DXF)
                    </p>
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-1 overflow-hidden" style={{ maxHeight: "120px" }}>
                      <img
                        src={"data:image/svg+xml;charset=utf-8," + encodeURIComponent(result.skeleton_svg)}
                        alt="Skeleton Preview"
                        className="w-full"
                        style={{ objectFit: "contain", maxHeight: "110px" }}
                      />
                    </div>
                  </div>
                )}
                {/* Page dimensions */}
                {result.page_dimensions && (
                  <div className="text-xs text-gray-600 mt-1 space-y-0.5">
                    <p className="font-medium text-gray-700 flex items-center gap-1">
                      <Ruler size={12} /> Dimensions from page:
                    </p>
                    {result.page_dimensions.width_cm && (
                      <p>Width: {result.page_dimensions.width_cm}cm</p>
                    )}
                    {result.page_dimensions.overall_height_cm && (
                      <p>Height: {result.page_dimensions.overall_height_cm}cm</p>
                    )}
                    {result.page_dimensions.depth_cm && (
                      <p>Depth: {result.page_dimensions.depth_cm}cm</p>
                    )}
                    {result.page_dimensions.length_cm && (
                      <p>Length: {result.page_dimensions.length_cm}cm</p>
                    )}
                    {result.page_dimensions.sizes && result.page_dimensions.sizes.length > 0 && (
                      <details className="mt-1">
                        <summary className="cursor-pointer text-gray-500 hover:text-gray-700">
                          {result.page_dimensions.sizes.length} sizes available
                        </summary>
                        <div className="mt-1 space-y-0.5">
                          {result.page_dimensions.sizes.map((s, i) => (
                            <p key={i} className="text-gray-500">
                              {s.width} × {s.length} × {s.height}cm
                            </p>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Comparison score */}
          {result.comparison && (
            <div className="p-2 bg-gray-50 rounded-lg text-xs">
              <p className="font-medium text-gray-700 mb-1">Validation Score</p>
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${
                  (result.comparison.overall_score || 0) >= 0.9
                    ? "bg-green-500" : (result.comparison.overall_score || 0) >= 0.7
                    ? "bg-yellow-500" : "bg-red-500"
                }`} />
                <span className="text-gray-600">
                  Score: {(result.comparison.overall_score * 100).toFixed(0)}%
                </span>
              </div>
              {result.comparison.error_count > 0 && (
                <p className="text-gray-400 mt-0.5">{result.comparison.error_count} issues detected</p>
              )}
            </div>
          )}

          {/* SVG Preview */}
          {result.preview_svg && (
            <div className="bg-white border border-gray-200 rounded-lg p-2">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs font-semibold text-gray-700">CAD Preview</p>
                <a
                  href={result.preview_svg.startsWith("/") ? result.preview_svg : ENGINE_BASE + result.preview_svg}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-[10px] text-indigo-500 hover:text-indigo-700"
                >
                  <Maximize2 size={10} /> Open full size
                </a>
              </div>
              <a
                href={result.preview_svg.startsWith("/") ? result.preview_svg : ENGINE_BASE + result.preview_svg}
                target="_blank"
                rel="noopener noreferrer"
              >
                <img
                  src={result.preview_svg.startsWith("/") ? result.preview_svg : ENGINE_BASE + result.preview_svg}
                  alt="CAD Preview"
                  className="w-full border border-gray-100 rounded bg-white"
                  style={{ maxHeight: "350px", objectFit: "contain", cursor: "zoom-in" } as React.CSSProperties}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              </a>
            </div>
          )}

          <a
            href={result.page_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
          >
            <ExternalLink size={12} /> View product page
          </a>
        </div>
      )}
    </div>
  );
}
