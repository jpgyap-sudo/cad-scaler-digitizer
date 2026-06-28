import React, { useState, useRef } from 'react';
import { UploadCloud, Play, X, CheckCircle2, Image, Loader2, AlertCircle } from 'lucide-react';
import type { DigitizeResult, ConstraintResult } from '../services/cadEngine';

export interface PipelineJobResult {
  job_id: string;
  status: string;
  steps: { step: string; status: string; detail: string }[];
  errors: string[];
  outputs: {
    dxf_url?: string;
    quality_score?: string;
    scene_graph?: string;
  };
}

interface PipelineUploadProps {
  onPipelineComplete?: (result: PipelineJobResult) => void;
  disabled?: boolean;
  className?: string;
  /** Optional digitize result to show template_graph info panel */
  digitizeResult?: DigitizeResult;
  /** Optional constraints from template resolution */
  constraints?: ConstraintResult[];
  /** Optional furniture type label */
  furnitureLabel?: string;
}

const FURNITURE_TYPES = [
  { value: '', label: 'Auto-detect' },
  { value: 'dining_table', label: 'Dining Table' },
  { value: 'sofa', label: 'Sofa' },
  { value: 'cabinet', label: 'Cabinet' },
  { value: 'bed', label: 'Bed' },
  { value: 'sideboard', label: 'Sideboard' },
  { value: 'desk', label: 'Office Desk' },
  { value: 'nightstand', label: 'Nightstand' },
  { value: 'coffee_table', label: 'Coffee Table' },
];

const PipelineUpload: React.FC<PipelineUploadProps> = ({
  onPipelineComplete,
  disabled,
  className = '',
  digitizeResult,
  constraints,
  furnitureLabel,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [furnitureType, setFurnitureType] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target?.files?.[0];
    if (!f) return;
    setFile(f);
    setError(null);
    const reader = new FileReader();
    reader.onload = (ev) => setImagePreview(ev.target?.result as string);
    reader.readAsDataURL(f);
  };

  const handleSubmit = async () => {
    if (!file) return;
    setIsUploading(true);
    setStatus('Uploading to pipeline...');
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      if (furnitureType) formData.append('furniture_type', furnitureType);

      const base = import.meta.env.VITE_CAD_ENGINE_URL || '';
      const url = base ? `${base}/pipeline/run` : '/py-api/pipeline/run';

      const res = await fetch(url, { method: 'POST', body: formData });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }

      setStatus('Pipeline complete!');
      if (onPipelineComplete) onPipelineComplete(data as PipelineJobResult);
    } catch (err: any) {
      setError(err?.message || 'Pipeline failed');
    } finally {
      setIsUploading(false);
    }
  };

  const handleCancel = () => {
    setFile(null);
    setImagePreview(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const tg = digitizeResult?.template_graph;

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Upload area — hide when digitizeResult has template_graph */}
      {!file && !digitizeResult && (
        <div
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-indigo-300 rounded-2xl p-8 bg-white hover:border-indigo-500 hover:bg-indigo-50/30 transition-all cursor-pointer text-center"
        >
          <input type="file" ref={fileInputRef} onChange={handleFileSelect}
            accept="image/png,image/jpeg,image/jpg,image/webp" className="hidden" />
          <UploadCloud className="w-10 h-10 text-indigo-400 mx-auto mb-3" />
          <p className="text-sm font-semibold text-slate-700">Upload a furniture photo</p>
          <p className="text-xs text-slate-400 mt-1">PNG, JPEG — the pipeline will detect type, materials, and generate a DXF</p>
        </div>
      )}

      {/* Selected file preview */}
      {file && (
        <div className="space-y-3">
          {imagePreview && (
            <img src={imagePreview} alt="Preview" className="max-h-40 rounded-xl border border-slate-200 mx-auto object-contain" />
          )}
          <div className="flex items-center justify-between bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-2">
            <div className="flex items-center space-x-2 text-emerald-700 text-sm font-medium truncate">
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
              <span className="truncate">{file.name}</span>
            </div>
            <button onClick={handleCancel} className="text-slate-400 hover:text-red-500 transition-colors p-1">
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Furniture type selector */}
          <select value={furnitureType} onChange={e => setFurnitureType(e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white">
            {FURNITURE_TYPES.map(ft => (
              <option key={ft.value} value={ft.value}>{ft.label}</option>
            ))}
          </select>

          {/* Submit button */}
          <button onClick={handleSubmit} disabled={isUploading || disabled}
            className="w-full flex items-center justify-center space-x-2 px-6 py-3 bg-indigo-600 text-white rounded-xl text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 transition-all shadow-lg">
            {isUploading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Play className="w-5 h-5" />
            )}
            <span>{isUploading ? 'Running Pipeline...' : 'Run Pipeline'}</span>
          </button>

          {status && !error && (
            <div className="flex items-center space-x-2 text-indigo-700 bg-indigo-50 rounded-xl px-4 py-2 text-sm font-medium">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>{status}</span>
            </div>
          )}

          {error && (
            <div className="flex items-start space-x-2 text-red-700 bg-red-50 rounded-xl px-4 py-3 text-sm border border-red-200">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>
      )}

      {/* Template Graph Info Panel — shown when digitizeResult has template_graph */}
      {tg && (
        <div className="space-y-4 border-t border-slate-100 pt-4">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center">
            <Image className="w-3.5 h-3.5 mr-1.5" /> Template Graph
          </h3>

          {/* Template name + furniture type */}
          <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-3">
            {furnitureLabel && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500 font-medium">Furniture Type</span>
                <span className="text-sm font-bold text-purple-700">{furnitureLabel}</span>
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 font-medium">Template</span>
              <span className="text-sm font-semibold text-slate-700">{tg.template_name || tg.template_id}</span>
            </div>
            {tg.product_type && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500 font-medium">Product Type</span>
                <span className="text-sm font-semibold text-slate-700">{tg.product_type}</span>
              </div>
            )}
          </div>

          {/* Required Views */}
          {tg.required_views && tg.required_views.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <h4 className="text-xs font-semibold text-slate-500 mb-2">Required Views</h4>
              <div className="flex flex-wrap gap-1.5">
                {tg.required_views.map((v: string, i: number) => (
                  <span key={i} className="text-xs bg-indigo-50 text-indigo-700 px-2 py-1 rounded-lg font-medium border border-indigo-100">
                    {v}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Required Details */}
          {tg.required_details && tg.required_details.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <h4 className="text-xs font-semibold text-slate-500 mb-2">Required Details</h4>
              <ul className="text-xs text-slate-600 space-y-1">
                {tg.required_details.map((d: string, i: number) => (
                  <li key={i} className="flex items-start">
                    <span className="text-indigo-400 mr-1.5">•</span>
                    <span>{d}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Drawing Notes */}
          {tg.drawing_notes && tg.drawing_notes.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <h4 className="text-xs font-semibold text-slate-500 mb-2">Drawing Notes</h4>
              <ul className="text-xs text-slate-600 space-y-1">
                {tg.drawing_notes.map((n: string, i: number) => (
                  <li key={i} className="flex items-start">
                    <span className="text-amber-500 mr-1.5">📌</span>
                    <span>{n}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Constraint Status */}
          {constraints && constraints.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <h4 className="text-xs font-semibold text-slate-500 mb-2">Constraint Checks</h4>
              <div className="space-y-1.5">
                {constraints.map((c: ConstraintResult, i: number) => (
                  <div key={i} className="flex items-center justify-between text-xs bg-slate-50 rounded-lg px-3 py-2">
                    <div className="flex-1 min-w-0">
                      <span className="font-medium text-slate-700">{c.id || c.description}</span>
                      {c.description && c.id && (
                        <span className="text-slate-400 ml-1 truncate">— {c.description}</span>
                      )}
                    </div>
                    <span className={`ml-2 text-[10px] font-bold px-2 py-0.5 rounded-full flex-shrink-0 ${
                      c.passed
                        ? 'bg-emerald-100 text-emerald-700'
                        : 'bg-red-100 text-red-700'
                    }`}>
                      {c.passed ? '✓ PASS' : '✗ FAIL'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default PipelineUpload;
