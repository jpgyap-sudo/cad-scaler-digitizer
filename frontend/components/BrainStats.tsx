import React, { useEffect, useState } from 'react';
import { Brain, TrendingUp, Package, Wrench, BarChart3 } from 'lucide-react';

interface BrainReport {
  corrections_by_type: { type: string; count: number; avg_ratio: number }[];
  top_materials: { component: string; material: string; count: number }[];
  confident_proportions: { type: string; component: string; samples: number; confidence: number }[];
  recent_drawings: { type: string; file: string; quality: number; time: string }[];
}

interface ProportionEntry {
  furniture_type: string; param: string; ratio: number; sample_count: number;
}

const BrainStats: React.FC<{ className?: string }> = ({ className = '' }) => {
  const [report, setReport] = useState<BrainReport | null>(null);
  const [proportions, setProportions] = useState<ProportionEntry[]>([]);
  const [materials, setMaterials] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    const base = import.meta.env.VITE_CAD_ENGINE_URL || '';
    const apiUrl = (path: string) =>
      (base.startsWith('http') ? `${base}/api/brain/${path}` : `${window.location.origin}/py-api/brain/${path}`);

    Promise.all([
      fetch(apiUrl('report')).then(r => r.json()).catch(() => null),
      fetch(apiUrl('proportions')).then(r => r.json()).catch(() => ({ proportions: [] })),
      fetch(apiUrl('materials')).then(r => r.json()).catch(() => ({})),
    ]).then(([rep, prop, mat]) => {
      if (rep) setReport(rep);
      if (prop?.proportions) setProportions(prop.proportions);
      if (mat) setMaterials(mat);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return null;

  const totalCorrections = (report?.corrections_by_type || []).reduce((s, c) => s + c.count, 0);
  const totalDrawings = (report?.recent_drawings || []).length;
  const topMaterial = report?.top_materials?.[0];
  const hasData = totalCorrections > 0 || totalDrawings > 0 || proportions.length > 0;

  return (
    <div className={className}>
      <div className="flex items-center space-x-2 mb-2">
        <Brain size={14} className="text-purple-500" />
        <span className="text-xs font-bold text-slate-600 uppercase tracking-wide">Central Brain</span>
      </div>

      {!hasData ? (
        <p className="text-[10px] text-slate-400 leading-relaxed">
          The brain is empty — upload drawings and chat corrections to feed it. It learns across all users.
        </p>
      ) : (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-purple-50 rounded-lg p-2 text-center">
              <div className="text-lg font-bold text-purple-700">{totalDrawings}</div>
              <div className="text-[9px] text-purple-500">Drawings</div>
            </div>
            <div className="bg-emerald-50 rounded-lg p-2 text-center">
              <div className="text-lg font-bold text-emerald-700">{totalCorrections}</div>
              <div className="text-[9px] text-emerald-500">Corrections</div>
            </div>
          </div>

          {topMaterial && (
            <div className="text-[10px] text-slate-500 leading-relaxed bg-slate-50 rounded-lg p-2">
              <TrendingUp size={12} className="inline text-amber-500 mr-1" />
              Top material: <strong>{topMaterial.material}</strong>
              <span className="text-slate-400"> ({topMaterial.count}x on {topMaterial.component})</span>
            </div>
          )}

          <button onClick={() => setShowDetails(!showDetails)}
            className="w-full flex items-center justify-center gap-1 py-1 text-[9px] text-slate-400 hover:text-slate-600 bg-slate-50 rounded">
            <BarChart3 size={10} />
            {showDetails ? 'Hide' : 'Show'} learned data ({proportions.length} proportions, {Object.keys(materials).length} materials)
          </button>

          {showDetails && proportions.length > 0 && (
            <div className="text-[9px] text-slate-500 space-y-1 bg-slate-50 rounded p-2">
              <p className="font-semibold text-slate-600 mb-1">Learned Proportions</p>
              {proportions.slice(0, 10).map((p, i) => (
                <div key={i} className="flex justify-between">
                  <span>{p.furniture_type} / {p.param}</span>
                  <span className="text-slate-400">{p.ratio.toFixed(3)} ({p.sample_count} samples)</span>
                </div>
              ))}
            </div>
          )}

          {showDetails && Object.keys(materials).length > 0 && (
            <div className="text-[9px] text-slate-500 space-y-1 bg-slate-50 rounded p-2">
              <p className="font-semibold text-slate-600 mb-1">Learned Materials</p>
              {Object.entries(materials).slice(0, 8).map(([key, val]: [string, any]) => (
                <div key={key} className="flex justify-between">
                  <span>{key}</span>
                  <span className="text-slate-400">{val.count || val}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default BrainStats;
