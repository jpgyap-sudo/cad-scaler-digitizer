import React, { useEffect, useState } from 'react';
import { Brain, TrendingUp, Package, Wrench } from 'lucide-react';

interface BrainReport {
  corrections_by_type: { type: string; count: number; avg_ratio: number }[];
  top_materials: { component: string; material: string; count: number }[];
  confident_proportions: { type: string; component: string; samples: number; confidence: number }[];
  recent_drawings: { type: string; file: string; quality: number; time: string }[];
}

const BrainStats: React.FC<{ className?: string }> = ({ className = '' }) => {
  const [report, setReport] = useState<BrainReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const base = import.meta.env.VITE_CAD_ENGINE_URL || '';
    const apiUrl = base.startsWith('http')
      ? `${base}/api/brain/report`
      : `${window.location.origin}/py-api/brain/report`;
    fetch(apiUrl)
      .then(r => r.json())
      .then(setReport)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return null;

  const totalCorrections = (report?.corrections_by_type || []).reduce((s, c) => s + c.count, 0);
  const totalDrawings = (report?.recent_drawings || []).length;
  const topMaterial = report?.top_materials?.[0];
  const hasData = totalCorrections > 0 || totalDrawings > 0;

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

          {report?.confident_proportions?.length > 0 && (
            <div className="text-[10px] text-slate-400">
              <Wrench size={12} className="inline mr-1" />
              {report.confident_proportions.length} proportion(s) learned
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default BrainStats;
