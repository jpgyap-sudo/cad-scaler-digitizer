import React, { useState, useEffect } from "react";
import { BarChart3, TrendingUp, AlertTriangle, CheckCircle2, Clock, Cpu, Layers, Loader2, ArrowUp, ArrowDown, Minus } from "lucide-react";

const ENGINE_BASE = import.meta.env.VITE_CAD_ENGINE_URL || "/py-api";
const NODE_API = "http://localhost:4000";

export default function AnalyticsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch(`${ENGINE_BASE}/calibration/report`, { signal: AbortSignal.timeout(8000) }).then(r => r.json()).catch(() => null),
      fetch(`${ENGINE_BASE}/compare/results`, { signal: AbortSignal.timeout(8000) }).then(r => r.json()).catch(() => []),
      fetch(`${ENGINE_BASE}/calibration/parameters`, { signal: AbortSignal.timeout(5000) }).then(r => r.json()).catch(() => ({})),
    ]).then(([cal, results, params]) => {
      setData({ cal, results, params });
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="flex items-center justify-center py-16"><Loader2 size={20} className="animate-spin text-gray-400" /></div>;

  const { cal, results, params } = data || {};
  const stats = cal?.comparison_stats || {};
  const errorCounts = stats.error_counts || {};
  const totalErrors = Object.values(errorCounts).reduce((s: number, c: any) => s + c, 0);
  const totalComparisons = stats.total || 0;
  const avgScore = stats.avg_score || 0;
  const biases = cal?.systematic_biases || [];

  // Group results by score tiers
  const highScore = (results || []).filter((r: any) => r.overall_score >= 0.8).length;
  const medScore = (results || []).filter((r: any) => r.overall_score >= 0.5 && r.overall_score < 0.8).length;
  const lowScore = (results || []).filter((r: any) => r.overall_score < 0.5).length;
  const total = highScore + medScore + lowScore;

  return (
    <div className="max-w-4xl mx-auto py-6 px-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
            <BarChart3 size={18} className="text-indigo-500" />
            Analytics & Accuracy
          </h2>
          <p className="text-xs text-gray-500">Daily accuracy metrics, error trends, and digitizer performance tracking.</p>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard icon={<BarChart3 size={16} />} label="Comparisons" value={totalComparisons} color="bg-blue-50 text-blue-700" />
        <StatCard icon={<TrendingUp size={16} />} label="Avg Score" value={`${(avgScore * 100).toFixed(0)}%`} color="bg-green-50 text-green-700" />
        <StatCard icon={<AlertTriangle size={16} />} label="Total Errors" value={totalErrors} color="bg-red-50 text-red-700" />
        <StatCard icon={<Cpu size={16} />} label="Parameters" value={Object.keys(params || {}).length} color="bg-purple-50 text-purple-700" />
      </div>

      {/* Score distribution */}
      {total > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs font-semibold text-gray-700 mb-2">Score Distribution</p>
          <div className="flex h-6 rounded-lg overflow-hidden">
            <div className="bg-green-500" style={{ width: `${(highScore / total) * 100}%` }} title={`High (≥80%): ${highScore}`} />
            <div className="bg-yellow-500" style={{ width: `${(medScore / total) * 100}%` }} title={`Medium (50-79%): ${medScore}`} />
            <div className="bg-red-500" style={{ width: `${(lowScore / total) * 100}%` }} title={`Low (<50%): ${lowScore}`} />
          </div>
          <div className="flex gap-4 mt-1.5 text-[10px] text-gray-500">
            <span>🟢 High: {highScore} ({(highScore / total * 100).toFixed(0)}%)</span>
            <span>🟡 Medium: {medScore} ({(medScore / total * 100).toFixed(0)}%)</span>
            <span>🔴 Low: {lowScore} ({(lowScore / total * 100).toFixed(0)}%)</span>
          </div>
        </div>
      )}

      {/* Error breakdown */}
      {Object.keys(errorCounts).length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-1"><AlertTriangle size={12} /> Error Breakdown</p>
          <div className="space-y-1.5">
            {Object.entries(errorCounts).sort(([, a]: any, [, b]: any) => b - a).map(([type, count]: [string, any]) => {
              const pct = (count / totalErrors) * 100;
              return (
                <div key={type}>
                  <div className="flex justify-between text-[10px] text-gray-500 mb-0.5">
                    <span className="capitalize">{type.replace(/_/g, " ")}</span>
                    <span>{count} ({pct.toFixed(0)}%)</span>
                  </div>
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: type.includes("edge") ? "#f87171" : "#fbbf24" }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Systematic biases */}
      {biases.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs font-semibold text-gray-700 mb-2">Systematic Biases Detected</p>
          {biases.map((b: any, i: number) => (
            <div key={i} className="flex items-center justify-between py-1 border-b border-gray-50 last:border-0 text-xs">
              <span className="text-gray-600">{b.dimension}: <strong>{b.direction}</strong> by {b.avg_deviation_pct}%</span>
              <span className="text-gray-400">{(b.confidence * 100).toFixed(0)}% confidence, {b.sample_count} samples</span>
            </div>
          ))}
        </div>
      )}

      {/* Recent comparisons */}
      {Array.isArray(results) && results.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs font-semibold text-gray-700 mb-2">Recent Comparisons</p>
          <div className="space-y-1">
            {results.slice(0, 10).map((r: any, i: number) => (
              <div key={i} className="flex items-center justify-between py-1 border-b border-gray-50 last:border-0 text-xs">
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${r.overall_score >= 0.8 ? "bg-green-500" : r.overall_score >= 0.5 ? "bg-yellow-500" : "bg-red-500"}`} />
                  <span className="text-gray-600 truncate max-w-[120px]">{r.product_id || r.job_id}</span>
                </div>
                <div className="flex items-center gap-3 text-gray-400">
                  <span>Score: {(r.overall_score * 100).toFixed(0)}%</span>
                  <span>Edge: {(r.edge_overlap * 100).toFixed(0)}%</span>
                  <span>Errors: {r.error_count}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Current parameters */}
      {params && Object.keys(params).length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-1"><Cpu size={12} /> Digitizer Parameters</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {Object.entries(params).filter(([, v]) => typeof v === "number").map(([key, val]) => (
              <div key={key} className="text-[10px] text-gray-500">
                <span className="block text-gray-400">{key.replace(/_/g, " ")}</span>
                <span className="font-semibold">{typeof val === "number" ? (key.includes("canny") ? val.toFixed(0) : val.toFixed(3)) : val}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {totalComparisons === 0 && (
        <div className="text-center py-12 text-sm text-gray-400">
          <BarChart3 size={32} className="mx-auto mb-2 text-gray-300" />
          No comparison data yet. Run some digitizations to populate analytics.
        </div>
      )}
    </div>
  );
}

function StatCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: string | number; color: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3">
      <div className={`inline-flex items-center justify-center w-7 h-7 rounded-lg mb-1.5 ${color}`}>{icon}</div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-lg font-bold text-gray-800">{value}</p>
    </div>
  );
}
