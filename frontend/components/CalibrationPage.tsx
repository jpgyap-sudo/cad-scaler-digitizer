import React, { useState, useEffect } from "react";
import { BarChart3, TrendingUp, AlertTriangle, CheckCircle2, Settings, RefreshCw, Loader2, SlidersHorizontal } from "lucide-react";

const ENGINE_BASE = import.meta.env.VITE_CAD_ENGINE_URL || "/py-api";

interface CorrectionHint {
  type: string;
  parameter: string;
  current_value: number;
  suggested_value: number;
  reason: string;
  confidence: number;
}

interface CalibrationReport {
  current_parameters: Record<string, number>;
  comparison_stats: {
    total: number;
    avg_score: number;
    error_counts: Record<string, number>;
  };
  systematic_biases: Array<{
    dimension: string;
    avg_deviation_pct: number;
    direction: string;
    sample_count: number;
    correction_factor: number;
    confidence: number;
  }>;
  correction_hints: CorrectionHint[];
  correction_history: Array<{
    parameter: string;
    old_value: number;
    new_value: number;
    reason: string;
    applied_at: string;
  }>;
  recommended_action: string;
}

export default function CalibrationPage() {
  const [report, setReport] = useState<CalibrationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);

  const load = () => {
    setLoading(true);
      fetch(`${ENGINE_BASE}/calibration/report`)
      .then((r) => r.json())
      .then((data) => { setReport(data); setLoading(false); })
      .catch(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const applyCorrections = async () => {
    setApplying(true);
    try {
      const r = await fetch(`${ENGINE_BASE}/calibration/apply`, { method: "POST" });
      const data = await r.json();
      alert(`Applied ${data.hints_applied} corrections`);
      load();
    } catch { alert("Failed to apply corrections"); }
    setApplying(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 size={20} className="animate-spin text-gray-400" />
        <span className="ml-2 text-sm text-gray-500">Loading calibration report...</span>
      </div>
    );
  }

  if (!report) return <div className="p-4 text-sm text-red-500">Failed to load</div>;

  return (
    <div className="max-w-3xl mx-auto py-6 px-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
            <BarChart3 size={18} className="text-amber-500" />
            Calibration & Training Feedback
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Aggregates comparison errors to detect systematic biases and auto-adjust digitizer parameters.
          </p>
        </div>
        <button onClick={load} className="flex items-center gap-1 px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 border rounded-lg">
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white border border-gray-200 rounded-lg p-3">
          <p className="text-xs text-gray-500">Comparisons</p>
          <p className="text-2xl font-bold text-gray-800">{report.comparison_stats.total}</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-3">
          <p className="text-xs text-gray-500">Avg Score</p>
          <p className="text-2xl font-bold text-gray-800">{(report.comparison_stats.avg_score * 100).toFixed(0)}%</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-3">
          <p className="text-xs text-gray-500">Status</p>
          <p className="text-xs font-medium text-amber-600 mt-1 capitalize">{report.recommended_action.replace(/_/g, " ")}</p>
        </div>
      </div>

      {/* Parameter Sliders */}
      <details className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <summary className="px-4 py-2.5 flex items-center gap-2 cursor-pointer hover:bg-gray-50 text-xs font-semibold text-gray-700">
          <SlidersHorizontal size={14} /> Digitizer Parameters (manual override)
        </summary>
        <div className="px-4 pb-4 pt-2 space-y-3 border-t border-gray-100">
          <SliderControl label="Canny Low Threshold" paramKey="canny_low" min={10} max={150} step={5} svg={report.current_parameters} />
          <SliderControl label="Canny High Threshold" paramKey="canny_high" min={50} max={400} step={10} svg={report.current_parameters} />
          <SliderControl label="Min Contour Area" paramKey="min_contour_area" min={5} max={200} step={5} svg={report.current_parameters} />
          <SliderControl label="Edge Dilation Kernel" paramKey="edge_dilation_kernel" min={1} max={11} step={2} svg={report.current_parameters} />
          <SliderControl label="Scale Correction (Width)" paramKey="scale_correction_width_cm" min={0.5} max={1.5} step={0.05} svg={report.current_parameters} />
          <SliderControl label="Scale Correction (Height)" paramKey="scale_correction_overall_height_cm" min={0.5} max={1.5} step={0.05} svg={report.current_parameters} />
          <SliderControl label="OCR Confidence Threshold" paramKey="ocr_confidence_threshold" min={0.1} max={1.0} step={0.05} svg={report.current_parameters} />
        </div>
      </details>

      {/* Error counts */}
      {Object.keys(report.comparison_stats.error_counts).length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-3">
          <p className="text-xs font-semibold text-gray-700 mb-2">Error Distribution</p>
          {Object.entries(report.comparison_stats.error_counts).map(([type, count]) => (
            <div key={type} className="flex items-center gap-2 mb-1">
              <span className="text-xs text-gray-500 w-28">{type.replace(/_/g, " ")}</span>
              <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-red-400 rounded-full"
                  style={{ width: `${Math.min(100, (count / report.comparison_stats.total) * 100)}%` }}
                />
              </div>
              <span className="text-xs text-gray-500 w-8 text-right">{count}</span>
            </div>
          ))}
        </div>
      )}

      {/* Systematic biases */}
      {report.systematic_biases.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-3">
          <p className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-1">
            <TrendingUp size={12} /> Systematic Biases
          </p>
          {report.systematic_biases.map((b, i) => (
            <div key={i} className="flex items-center justify-between py-1 border-b border-gray-50 last:border-0">
              <div>
                <p className="text-xs text-gray-700">{b.dimension}: {b.direction} by {b.avg_deviation_pct}%</p>
                <p className="text-[10px] text-gray-400">{b.sample_count} samples, correction ×{b.correction_factor}</p>
              </div>
              <span className={`text-[10px] px-1.5 py-0.5 rounded ${b.confidence > 0.5 ? "bg-amber-100 text-amber-700" : "bg-gray-100 text-gray-500"}`}>
                {(b.confidence * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Correction hints */}
      {report.correction_hints.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-3">
          <p className="text-xs font-semibold text-gray-700 mb-2">Recommended Adjustments</p>
          {report.correction_hints.map((h, i) => (
            <div key={i} className="flex items-start gap-2 py-1.5 border-b border-gray-50 last:border-0">
              <Settings size={12} className="text-gray-400 mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-gray-700">
                  {h.parameter}: {h.current_value} → <span className="font-semibold text-indigo-600">{h.suggested_value}</span>
                </p>
                <p className="text-[10px] text-gray-400">{h.reason}</p>
              </div>
              <span className={`text-[10px] px-1.5 py-0.5 rounded shrink-0 ${h.confidence > 0.5 ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                {(h.confidence * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {report.correction_hints.length > 0 && (
        <button
          onClick={applyCorrections}
          disabled={applying}
          className="w-full py-2 bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium rounded-lg disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {applying ? <><Loader2 size={14} className="animate-spin" /> Applying...</> : <><CheckCircle2 size={14} /> Apply Corrections</>}
        </button>
      )}

      {report.correction_hints.length === 0 && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-center">
          <CheckCircle2 size={20} className="text-gray-300 mx-auto mb-1" />
          <p className="text-xs text-gray-500">No corrections needed. More comparisons will generate actionable hints.</p>
        </div>
      )}

      {/* Correction history */}
      {report.correction_history?.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-3">
          <p className="text-xs font-semibold text-gray-700 mb-2">Correction History</p>
          {report.correction_history.slice(-5).reverse().map((h, i) => (
            <div key={i} className="text-[10px] text-gray-500 py-0.5">
              {h.parameter}: {h.old_value} → {h.new_value} — {h.reason}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SliderControl({ label, paramKey, min, max, step, svg }: {
  label: string; paramKey: string; min: number; max: number; step: number; svg: Record<string, number>;
}) {
  const [value, setValue] = useState(svg[paramKey] ?? 50);
  const [saving, setSaving] = useState(false);

  useEffect(() => { setValue(svg[paramKey] ?? 50); }, [svg, paramKey]);

  const save = async () => {
    setSaving(true);
    try {
      await fetch(`${ENGINE_BASE}/calibration/parameters/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ param_key: paramKey, param_value: value }),
      });
    } catch {}
    setSaving(false);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-xs text-gray-600">{label}</label>
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-semibold text-indigo-600 w-12 text-right">{value}</span>
          <button onClick={save} disabled={saving} className="text-[9px] px-1.5 py-0.5 bg-indigo-50 text-indigo-600 rounded hover:bg-indigo-100 disabled:opacity-50">
            {saving ? "..." : "Set"}
          </button>
        </div>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => setValue(parseFloat(e.target.value))}
        className="w-full h-1.5 bg-gray-200 rounded-full appearance-none cursor-pointer accent-indigo-500"
      />
    </div>
  );
}
