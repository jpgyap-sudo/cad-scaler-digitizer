import React from "react";

interface CadConfidenceSource {
  label: string;
  color: string;
  description: string;
}

const SOURCES: CadConfidenceSource[] = [
  { label: "pixel_detected", color: "#22c55e", description: "Detected from image pixels" },
  { label: "ocr_associated", color: "#3b82f6", description: "OCR dimension linked to geometry" },
  { label: "user_confirmed", color: "#8b5cf6", description: "Manually confirmed by user" },
  { label: "reference_estimated", color: "#f59e0b", description: "Estimated from reference proportions" },
  { label: "template_default", color: "#ef4444", description: "Template default — verify!" },
];

export function CadConfidenceLegend() {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs">
      <div className="font-semibold text-sm mb-2 text-slate-700">Confidence Sources</div>
      <div className="space-y-1.5">
        {SOURCES.map((s) => (
          <div key={s.label} className="flex items-center gap-2">
            <span
              className="inline-block w-3 h-3 rounded-full shrink-0"
              style={{ backgroundColor: s.color }}
            />
            <span className="font-medium text-slate-600 capitalize">
              {s.label.replace(/_/g, " ")}
            </span>
            <span className="text-slate-400">— {s.description}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
