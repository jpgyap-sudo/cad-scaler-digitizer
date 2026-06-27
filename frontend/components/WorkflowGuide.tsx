import React from "react";
import { Globe, Image, FileDown, CheckCircle2, BarChart3, BookOpen, ArrowRight, Zap } from "lucide-react";

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

      {/* Summary */}
      <div className="bg-gradient-to-r from-indigo-50 to-blue-50 border border-indigo-100 rounded-lg p-4 mt-6">
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
