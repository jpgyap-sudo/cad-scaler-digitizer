import React, { useState, useEffect } from 'react';
import { Sliders, Loader2 } from 'lucide-react';

interface DimSlider {
  key: string;
  label: string;
  min: number;
  max: number;
  step: number;
  unit: string;
}

interface SliderPanelProps {
  dxfFile: string;
  initialDims: Record<string, number>;
  onAdjusted: (dims: Record<string, number>, svgUrl: string) => void;
  className?: string;
}

const SLIDERS: DimSlider[] = [
  { key: 'top_diameter_cm', label: 'Top Diameter', min: 40, max: 160, step: 1, unit: 'cm' },
  { key: 'overall_height_cm', label: 'Overall Height', min: 30, max: 150, step: 1, unit: 'cm' },
  { key: 'base_diameter_cm', label: 'Base Diameter', min: 20, max: 100, step: 1, unit: 'cm' },
  { key: 'neck_diameter_cm', label: 'Neck Diameter', min: 10, max: 60, step: 0.5, unit: 'cm' },
  { key: 'top_thickness_cm', label: 'Top Thickness', min: 2, max: 12, step: 0.5, unit: 'cm' },
];

const SliderPanel: React.FC<SliderPanelProps> = ({ dxfFile, initialDims, onAdjusted, className = '' }) => {
  const [dims, setDims] = useState<Record<string, number>>(initialDims);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setDims(initialDims);
  }, [initialDims]);

  const handleSliderChange = (key: string, value: number) => {
    setDims(prev => ({ ...prev, [key]: value }));
  };

  const handleApply = async () => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('dxf_file', dxfFile);
      for (const s of SLIDERS) {
        if (dims[s.key] !== undefined) {
          formData.append(s.key, String(dims[s.key]));
        }
      }

      const base = import.meta.env.VITE_CAD_ENGINE_URL || '';
      const apiUrl = base.startsWith('http')
        ? `${base}/api/adjust`
        : `${window.location.origin}/py-api/adjust`;

      const resp = await fetch(apiUrl, { method: 'POST', body: formData });
      const data = await resp.json();
      if (data.preview_svg) {
        onAdjusted(data.dimensions, data.preview_svg);
      }
    } catch (e) {
      console.error('Adjust failed:', e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={className}>
      <div className="flex items-center space-x-2 mb-3">
        <Sliders size={14} className="text-indigo-500" />
        <span className="text-xs font-bold text-slate-600 uppercase tracking-wide">Adjust Dimensions</span>
      </div>

      <div className="space-y-3">
        {SLIDERS.map(s => (
          <div key={s.key} className="space-y-1">
            <div className="flex justify-between text-[10px] text-slate-500">
              <span>{s.label}</span>
              <span className="font-mono font-bold text-indigo-600">{dims[s.key] ?? '-'} {s.unit}</span>
            </div>
            <input
              type="range"
              min={s.min}
              max={s.max}
              step={s.step}
              value={dims[s.key] ?? (s.min + s.max) / 2}
              onChange={e => handleSliderChange(s.key, parseFloat(e.target.value))}
              className="w-full h-1.5 bg-slate-200 rounded-full appearance-none cursor-pointer accent-indigo-600"
            />
            <div className="flex justify-between text-[9px] text-slate-400">
              <span>{s.min}</span>
              <span>{s.max}</span>
            </div>
          </div>
        ))}
      </div>

      <button
        onClick={handleApply}
        disabled={loading}
        className="mt-3 w-full flex items-center justify-center space-x-2 px-3 py-2 bg-indigo-600 text-white rounded-lg text-xs font-bold hover:bg-indigo-700 disabled:opacity-50 transition-colors"
      >
        {loading ? <Loader2 size={14} className="animate-spin" /> : <Sliders size={14} />}
        <span>{loading ? 'Updating...' : 'Apply & Preview'}</span>
      </button>
    </div>
  );
};

export default SliderPanel;
