import React from "react";

export function CadConfidenceLegend() {
  return (
    <div className="rounded-lg border p-3 text-sm">
      <div className="font-semibold mb-2">CAD Confidence</div>
      <div>High: OCR or user-confirmed geometry</div>
      <div>Medium: pixel-detected geometry</div>
      <div>Low: estimated, template, or unknown geometry</div>
    </div>
  );
}
