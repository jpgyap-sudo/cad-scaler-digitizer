import React from "react";
import { Lightbulb, Bug, Target, Zap, Shield, RefreshCw, TrendingUp, Ruler, Image, Globe, Database, BookOpen, Cpu, Layers, AlertTriangle, CheckCircle2, ArrowRight } from "lucide-react";

const CATEGORIES = [
  {
    icon: <Image size={16} />,
    title: "Better Edge Detection",
    description: "OpenCV Canny thresholds auto-adjust via calibration (currently adjusting). Add AI-based segmentation (SAM) to isolate product from background before edge detection.",
    impact: "High",
    effort: "5-10 days",
    items: [
      "Integrate Meta's Segment Anything Model (SAM) for foreground/background separation",
      "Add adaptive thresholding based on image brightness histogram",
      "Implement multi-scale edge detection and merge results",
      "Add contour validation — filter out short/open contours from detection results"
    ]
  },
  {
    icon: <Ruler size={16} />,
    title: "Dimension Extraction Reliability",
    description: "Currently only ~70% of products have extractable dimensions. Improve variant option parsing and add PDF spec sheet dimension extraction.",
    impact: "High",
    effort: "3-5 days",
    items: [
      "Add Playwright-based full-page render for JS-loaded dimensions (currently HTTP-only)",
      "Parse more variant option formats (fractional inches, ranges like 140-200cm)",
      "Extract dimensions from spec sheet PDFs using OCR (PyMuPDF + pytesseract)",
      "Add Shopify metafield API support for custom dimension fields"
    ]
  },
  {
    icon: <Globe size={16} />,
    title: "Broader Website Support",
    description: "Currently optimized for Shopify stores (HomeU). Add support for non-Shopify e-commerce sites.",
    impact: "Medium",
    effort: "3-5 days",
    items: [
      "Add Playwright fallback for JS-heavy sites (currently HTTP-only page fetch)",
      "Create site-specific parsers: IKEA, Wayfair, Amazon, Crate & Barrel",
      "Add HTML meta tag dimension extraction (og:product:width, etc.)",
      "Implement robots.txt compliance with configurable override"
    ]
  },
  {
    icon: <Database size={16} />,
    title: "Training Data Pipeline",
    description: "Comparison results are logged but not directly used for ML training. Build an export pipeline to feed validated pairs into a model fine-tuning loop.",
    impact: "High",
    effort: "5-7 days",
    items: [
      "Export validated photo-DXF pairs as JSONL training records",
      "Build automated regression test suite (digitize known products, check score)",
      "Add active learning: flag low-confidence results for human review",
      "Create fine-tuning dataset from high-scoring comparisons (>90%)"
    ]
  },
  {
    icon: <Layers size={16} />,
    title: "More Templates",
    description: "18 templates exist but we need more: bed frames, wardrobes, outdoor furniture, office chairs.",
    impact: "Medium",
    effort: "3-5 days",
    items: [
      "Add outdoor furniture templates (lounger, dining set, umbrella base)",
      "Add office chair template (5-star base, gas lift, seat/backrest)",
      "Add sectional sofa template (modular corner units)",
      "Add bed frame template (with slats, rails, footboard)"
    ]
  },
  {
    icon: <Cpu size={16} />,
    title: "Real-time Processing",
    description: "Currently ~60s per product. Optimize the pipeline for faster processing: parallel OCR + OpenCV, cached image downloads.",
    impact: "Low",
    effort: "2-3 days",
    items: [
      "Add Redis result caching for repeated product URLs",
      "Run OCR and OpenCV edge detection in parallel threads",
      "Pre-warm Playwright browser pool for crawl operations",
      "Add HTTP/2 keep-alive for Spaces CDN downloads"
    ]
  },
  {
    icon: <Target size={16} />,
    title: "Validation Score Accuracy",
    description: "Current scoring weights page dims at 80%. Improve with multi-source validation and semantic checking.",
    impact: "Medium",
    effort: "3-5 days",
    items: [
      "Add cross-validation between OCR, JSON-LD, and meta tag dimensions",
      "Use AI-based image similarity to compare DXF preview vs product photo",
      "Add per-dimension confidence scoring based on source reliability",
      "Implement human-in-the-loop review for low-scoring results"
    ]
  },
  {
    icon: <Shield size={16} />,
    title: "Error Recovery & Retry",
    description: "Crawl failures (403, timeout) don't retry. Add exponential backoff and alternative extraction strategies.",
    impact: "Medium",
    effort: "2-3 days",
    items: [
      "Add automatic retry with exponential backoff on 403/timeout",
      "Fall back to Playwright when HTTP fetch fails or returns empty",
      "Store crawl error reasons for diagnostic dashboard",
      "Add dead-letter queue for permanently failed jobs"
    ]
  },
];

const BUGS: { title: string; description: string; severity: string; status: string }[] = [
  { title: "Elara dimension 2000x750cm instead of 200x100cm", description: "Variant option '2000 x 1000mm' not converted correctly — mm→cm works but the height uses a different pattern.", severity: "Major", status: "Fixed" },
  { title: "Stratos '140-200cm' range parsing", description: "Range '140-200' now handled via _parse_val (takes max). Width=90cm extracted. Height/length may be missing if not in variant options.", severity: "Major", status: "Fixed" },
  { title: "Sofa height shows 2cm on 4-seater", description: "HomeU data says '20(H) mm' for 4-seater sofa — 20mm=2cm is correct but unrealistic. Source data error on HomeU's side.", severity: "Medium", status: "Noted" },
  { title: "Tangerie table duplicate sizes in response", description: "Sizes array now deduplicated by unique (width, length, height) tuples before returning.", severity: "Minor", status: "Fixed" },
  { title: "Jardan product pages 403 on HTTP fetch", description: "Added dual User-Agent retry with Accept-Language header. Shopify JSON API fallback for dimension data still works.", severity: "Major", status: "Fixed" },
  { title: "npx prisma issue on fresh node_modules", description: "Prisma generate fails with empty node_modules due to cached layers.", severity: "Minor", status: "Fixed" },
  { title: "Comparison results no retention policy", description: "POST /api/calibration/cleanup?days=90 endpoint added. Deletes old comparisons and validation results.", severity: "Medium", status: "Fixed" },
  { title: "Redis queue jobs lost on container restart", description: "Failed crawl jobs now pushed to crawler:dead-letter queue in Redis for retry/review.", severity: "Major", status: "Fixed" },
];

export default function ImprovementsPage() {
  return (
    <div className="max-w-4xl mx-auto py-6 px-4 space-y-6">
      <div>
        <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
          <Lightbulb size={18} className="text-amber-500" />
          Improvements & Accuracy Guide
        </h2>
        <p className="text-xs text-gray-500">Recommended improvements ranked by impact, current known bugs, and how to make the digitizer more accurate.</p>
      </div>

      {/* Know Bugs */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="bg-red-50 px-4 py-2 border-b border-red-100 flex items-center gap-2">
          <Bug size={14} className="text-red-600" />
          <span className="text-xs font-semibold text-red-700">Known Bugs ({BUGS.filter(b => b.status !== "Fixed").length} open)</span>
        </div>
        <div className="divide-y divide-gray-100">
          {BUGS.map((bug, i) => (
            <div key={i} className="px-4 py-2 flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-gray-800">{bug.title}</p>
                <p className="text-[10px] text-gray-500 mt-0.5">{bug.description}</p>
              </div>
              <div className="flex items-center gap-2 ml-2 shrink-0">
                <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${
                  bug.severity === "Major" ? "bg-red-50 text-red-600" :
                  bug.severity === "Medium" ? "bg-yellow-50 text-yellow-600" :
                  "bg-gray-50 text-gray-500"
                }`}>{bug.severity}</span>
                <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${
                  bug.status === "Fixed" ? "bg-green-50 text-green-600" :
                  bug.status === "Queued" ? "bg-blue-50 text-blue-600" :
                  bug.status === "Planned" ? "bg-amber-50 text-amber-600" :
                  "bg-gray-50 text-gray-500"
                }`}>{bug.status}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Improvements by Category */}
      <div className="space-y-3">
        {CATEGORIES.map((cat, i) => (
          <details key={i} className="bg-white border border-gray-200 rounded-lg overflow-hidden group">
            <summary className="px-4 py-2.5 flex items-center justify-between cursor-pointer hover:bg-gray-50">
              <div className="flex items-center gap-2">
                <span className="text-indigo-500">{cat.icon}</span>
                <span className="text-sm font-semibold text-gray-800">{cat.title}</span>
              </div>
              <div className="flex items-center gap-2 text-[10px]">
                <span className={`px-1.5 py-0.5 rounded font-medium ${
                  cat.impact === "High" ? "bg-green-50 text-green-600" :
                  cat.impact === "Medium" ? "bg-yellow-50 text-yellow-600" :
                  "bg-gray-50 text-gray-500"
                }`}>Impact: {cat.impact}</span>
                <span className="text-gray-400">{cat.effort}</span>
              </div>
            </summary>
            <div className="px-4 pb-3 pt-1 border-t border-gray-100">
              <p className="text-xs text-gray-500 mb-2 mt-1">{cat.description}</p>
              <ul className="space-y-1">
                {cat.items.map((item, j) => (
                  <li key={j} className="flex items-start gap-1.5 text-[11px] text-gray-600">
                    <ArrowRight size={10} className="shrink-0 mt-0.5 text-indigo-400" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}
