import React, { useState } from "react";
import { Globe, Loader2, Download, AlertCircle, ExternalLink, Ruler, HelpCircle, Lightbulb } from "lucide-react";

const ENGINE_BASE = import.meta.env.VITE_CAD_ENGINE_URL || "/py-api";

interface PageDimensions {
  width_cm?: number;
  height_cm?: number;
  depth_cm?: number;
  length_cm?: number;
  sizes?: Array<{ width: number; length: number; height: number }>;
}

interface HallucinationVerdict {
  verdict: string;
  confidence: number;
}

interface CrawlResult {
  status: string;
  page_url?: string;
  image_url?: string;
  dxf_file?: string;
  download_url?: string;
  preview_svg?: string;
  page_dimensions?: PageDimensions;
  detected_dimensions?: Record<string, number>;
  hallucination_check?: {
    overall_score: number;
    verdicts: Record<string, HallucinationVerdict>;
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
      const res = await fetch(`${ENGINE_BASE}/api/crawl-to-dxf`, {
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
    </div>

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
                {result.dxf_file && (
                  <a
                    href={`${ENGINE_BASE}${result.download_url}`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 text-blue-700 text-sm rounded-lg hover:bg-blue-100 mb-1"
                  >
                    <Download size={14} />
                    Download DXF
                  </a>
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
                    {(result.page_dimensions as any).overall_height_cm && (
                      <p>Height: {(result.page_dimensions as any).overall_height_cm}cm</p>
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

          {/* Hallucination check */}
          {result.hallucination_check && (
            <div className="p-2 bg-gray-50 rounded-lg text-xs">
              <p className="font-medium text-gray-700 mb-1">Detection Quality</p>
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${
                  (result.hallucination_check.overall_score || 0) >= 0.7
                    ? "bg-green-500" : (result.hallucination_check.overall_score || 0) >= 0.4
                    ? "bg-yellow-500" : "bg-red-500"
                }`} />
                <span className="text-gray-600">
                  Score: {(result.hallucination_check.overall_score * 100).toFixed(0)}%
                </span>
              </div>
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
