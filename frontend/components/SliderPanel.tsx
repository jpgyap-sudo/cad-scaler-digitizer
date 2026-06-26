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
  furnitureType?: string;
  onAdjusted: (dims: Record<string, number>, svgUrl: string) => void;
  className?: string;
}

const ROUND_SLIDERS: DimSlider[] = [
  { key: 'top_diameter_cm', label: 'Top Diameter', min: 40, max: 160, step: 1, unit: 'cm' },
  { key: 'overall_height_cm', label: 'Overall Height', min: 30, max: 150, step: 1, unit: 'cm' },
  { key: 'base_diameter_cm', label: 'Base Diameter', min: 20, max: 100, step: 1, unit: 'cm' },
  { key: 'neck_diameter_cm', label: 'Neck Diameter', min: 10, max: 60, step: 0.5, unit: 'cm' },
  { key: 'top_thickness_cm', label: 'Top Thickness', min: 2, max: 12, step: 0.5, unit: 'cm' },
];

const RECT_SLIDERS: DimSlider[] = [
  { key: 'width_cm', label: 'Width', min: 60, max: 300, step: 1, unit: 'cm' },
  { key: 'depth_cm', label: 'Depth', min: 40, max: 150, step: 1, unit: 'cm' },
  { key: 'overall_height_cm', label: 'Height', min: 30, max: 150, step: 1, unit: 'cm' },
  { key: 'leg_thickness_cm', label: 'Leg Thickness', min: 3, max: 15, step: 0.5, unit: 'cm' },
];

type BaseShape = 'cylinder' | 'tapered' | 'flared';

// One-click starting ratios (relative to top diameter) for each base profile.
// Tapered = narrows toward the floor (the classic cone). Flared = widens
// toward the floor (a stable foot). Cylinder = same width top-to-bottom.
// These are just sensible defaults -- the diameter sliders below remain
// fully adjustable afterward.
const BASE_SHAPE_RATIOS: Record<BaseShape, { neck: number; base: number }> = {
  cylinder: { neck: 0.40, base: 0.40 },
  tapered: { neck: 0.55, base: 0.28 },
  flared: { neck: 0.28, base: 0.55 },
};

const SliderPanel: React.FC<SliderPanelProps> = ({ dxfFile, initialDims, furnitureType, onAdjusted, className = '' }) => {
  const isRound = !furnitureType?.includes('rectangular');
  const sliders = isRound ? ROUND_SLIDERS : RECT_SLIDERS;
  const [dims, setDims] = useState<Record<string, number>>(initialDims);
  const [loading, setLoading] = useState(false);
  const [baseShape, setBaseShape] = useState<BaseShape | null>(null);

  useEffect(() => {
    setDims(initialDims);
    setBaseShape(null);
  }, [initialDims]);

  const handleSliderChange = (key: string, value: number) => {
    setDims(prev => ({ ...prev, [key]: value }));
  };

  const applyDims = async (overrideDims?: Record<string, number>) => {
    const payload = overrideDims ?? dims;
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('dxf_file', dxfFile);
      for (const s of sliders) {
        if (payload[s.key] !== undefined) {
          formData.append(s.key, String(payload[s.key]));
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

  const handleApply = () => applyDims();

  const handleBaseShape = (shape: BaseShape) => {
    setBaseShape(shape);
    const topDia = dims['top_diameter_cm'] ?? 80;
    const ratios = BASE_SHAPE_RATIOS[shape];
    const next = {
      ...dims,
      base_diameter_cm: Math.round(topDia * ratios.base * 10) / 10,
      neck_diameter_cm: Math.round(topDia * ratios.neck * 10) / 10,
    };
    setDims(next);
    applyDims(next);
  };

  return (
    <div className={className}>
      <div className="flex items-center space-x-2 mb-3">
        <Sliders size={14} className="text-indigo-500" />
        <span className="text-xs font-bold text-slate-600 uppercase tracking-wide">Adjust Dimensions</span>
      </div>

      {isRound && (
        <div className="mb-3">
          <div className="text-[10px] text-slate-500 mb-1">
            Base Shape
            <span className="text-slate-400 normal-case"> -- AI guessed this from the photo; override if wrong</span>
          </div>
          <div className="grid grid-cols-3 gap-1">
            {(['cylinder', 'tapered', 'flared'] as BaseShape[]).map(shape => (
              <button
                key={shape}
                onClick={() => handleBaseShape(shape)}
                disabled={loading}
                className={`px-2 py-1.5 rounded-lg text-[10px] font-bold capitalize transition-colors disabled:opacity-50 ${
                  baseShape === shape
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {shape}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-3">
        {sliders.map(s => (
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
              onInput={e => handleSliderChange(s.key, parseFloat((e.target as HTMLInputElement).value))}
              className="w-full h-1.5 bg-slate-200 rounded-full appearance-none cursor-pointer accent-indigo-600
                [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-indigo-600
                [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:shadow
                [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:rounded-full
                [&::-moz-range-thumb]:bg-indigo-600 [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer"
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
