import React from "react";
import { Globe, Image, FileDown, CheckCircle2, BarChart3, BookOpen, ArrowRight, Zap, Cpu, Bot, Layers, Play, Crosshair } from "lucide-react";

const STEPS = [
  {
    icon: <Globe size={20} />,
    title: "Crawl Product URL",
    description: "Paste any product page URL. The system crawls the page, finds the hero product image, and extracts dimensions from Shopify variant options, tags, and descriptions.",
    endpoint: "POST /api/crawl-to-dxf",
    color: "bg-blue-500",
  },
  {
    icon: <Image size={20} />,
    title: "Digitize the Photo",
    description: "OpenCV detects edges and extracts dimensions. The template graph system matches the product type (table, sofa, chair) and scales the DXF to real-world dimensions from the product page.",
    endpoint: "POST /api/digitize",
    color: "bg-indigo-500",
  },
  {
    icon: <BookOpen size={20} />,
    title: "Match Against Templates",
    description: "18 engineering templates (rectangular table, standard sofa, dining chair, etc.) are matched against detected dimensions. Missing dimensions are filled from reference ratios.",
    endpoint: "GET /api/templates/suggest",
    color: "bg-violet-500",
  },
  {
    icon: <FileDown size={20} />,
    title: "Generate DXF Drawing",
    description: "A complete 4-view engineering DXF is generated: Top view, Front view, Side view, and Isometric projection — with real dimensions, notes, and title block.",
    endpoint: "Download: /api/download/{file}.dxf",
    color: "bg-purple-500",
  },
  {
    icon: <CheckCircle2 size={20} />,
    title: "Validate & Score",
    description: "The comparison agent runs edge-overlay analysis, dimension deviation check, and entity count match. A 0-1 validation score is produced.",
    endpoint: "POST /api/compare",
    color: "bg-green-500",
  },
  {
    icon: <BarChart3 size={20} />,
    title: "Training Feedback Loop",
    description: "Comparison errors (edge mismatches, wrong dimensions) are logged to Postgres. The calibration system aggregates errors and auto-adjusts digitizer parameters (Canny thresholds, scale factors) for continuous improvement.",
    endpoint: "GET /api/calibration/report",
    color: "bg-amber-500",
  },
];

export default function WorkflowGuide() {
  return (
    <div className="max-w-3xl mx-auto py-6 px-4">
      <div className="text-center mb-8">
        <h2 className="text-lg font-bold text-gray-800">How It Works</h2>
        <p className="text-sm text-gray-500 mt-1">End-to-end pipeline: from product URL to validated DXF</p>
      </div>

      <div className="relative">
        {/* Vertical connector line */}
        <div className="absolute left-[19px] top-0 bottom-0 w-0.5 bg-gray-200" />

        {STEPS.map((step, i) => (
          <div key={i} className="relative flex gap-4 mb-6">
            {/* Circle */}
            <div className={`shrink-0 w-10 h-10 rounded-full ${step.color} flex items-center justify-center text-white relative z-10`}>
              {step.icon}
            </div>

            {/* Card */}
            <div className="flex-1 bg-white border border-gray-200 rounded-lg p-4 ml-1">
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-sm font-semibold text-gray-800">{step.title}</h3>
                <span className="text-[10px] text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded font-mono shrink-0">{step.endpoint}</span>
              </div>
              <p className="text-xs text-gray-500 mt-1.5 leading-relaxed">{step.description}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Engine Modes */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 mt-4">
        <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <Cpu size={16} className="text-indigo-500" />
          Digitizer Engine Modes
        </h3>
        <p className="text-xs text-gray-500 mb-3">
          The Upload tab offers four engine modes that control how the product photo is digitized:
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
            <div className="flex items-center gap-1.5 mb-1">
              <Cpu size={14} className="text-gray-600" />
              <span className="text-xs font-semibold text-gray-700">OpenCV</span>
            </div>
            <p className="text-[10px] text-gray-500 leading-relaxed">
              Pure edge detection pipeline. <strong>cv2.Canny</strong> detects edges using configurable thresholds (canny_low, canny_high).
              Lines are extracted via Hough Transform, circles via HoughCircles. OCR extracts written dimensions from the image using Tesseract.
              Fast but requires clear product photos with visible dimensions. Used as the baseline for all other modes.
            </p>
          </div>

          <div className="bg-indigo-50 rounded-lg p-3 border border-indigo-100">
            <div className="flex items-center gap-1.5 mb-1">
              <Crosshair size={14} className="text-indigo-600" />
              <span className="text-xs font-semibold text-indigo-700">Hybrid</span>
            </div>
            <p className="text-[10px] text-indigo-500 leading-relaxed">
              <strong>Default mode.</strong> Combines OpenCV edge detection with cloud-based AI vision (OpenAI GPT-4o / Google Vision).
              The AI classifies furniture type, detects major dimensions, and identifies measurement labels.
              OpenCV handles precise line/edge extraction. Results are merged: AI provides context + correction,
              OpenCV provides pixel-level accuracy. Falls back gracefully if cloud API is unavailable.
            </p>
          </div>

          <div className="bg-purple-50 rounded-lg p-3 border border-purple-100">
            <div className="flex items-center gap-1.5 mb-1">
              <Bot size={14} className="text-purple-600" />
              <span className="text-xs font-semibold text-purple-700">Smart AI</span>
            </div>
            <p className="text-[10px] text-purple-500 leading-relaxed">
              Cloud-first approach. Sends the full photo to OpenAI GPT-4o with computer vision.
              The AI analyzes the image end-to-end: identifies furniture type, detects all dimensions,
              estimates scale from reference objects, and returns a structured dimension JSON.
              OpenCV is used as a fallback for edge refinement only. Requires <code className="bg-purple-100 px-1 rounded">OPENAI_API_KEY</code>.
            </p>
          </div>

          <div className="bg-emerald-50 rounded-lg p-3 border border-emerald-100">
            <div className="flex items-center gap-1.5 mb-1">
              <Play size={14} className="text-emerald-600" />
              <span className="text-xs font-semibold text-emerald-700">Pipeline</span>
            </div>
            <p className="text-[10px] text-emerald-500 leading-relaxed">
              Full multi-stage orchestration pipeline. Runs Cloud Vision (AI) → CAD Kernel (OpenCV + annotation extraction)
              → Template matching → DXF/PDF export. Each stage is independently monitored and can be retried on failure.
              The pipeline result includes intermediate outputs (annotated image, primitives, scene graph) for debugging and transparency.
              Best quality but slowest (takes ~2-3 minutes per product).
            </p>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="bg-gradient-to-r from-indigo-50 to-blue-50 border border-indigo-100 rounded-lg p-4 mt-4">
        <div className="flex items-start gap-3">
          <Zap size={18} className="text-indigo-500 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-indigo-800">Full Automation</p>
            <p className="text-xs text-indigo-600 mt-1">
              Paste a URL → get a 4-view DXF + validation score + calibration feedback — all in ~60 seconds.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
