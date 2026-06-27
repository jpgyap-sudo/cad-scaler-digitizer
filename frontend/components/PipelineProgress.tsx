import React from 'react';
import { CheckCircle2, Loader2, XCircle, Clock } from 'lucide-react';
import type { PipelineJobResult } from './PipelineUpload';

interface PipelineProgressProps {
  result: PipelineJobResult;
  className?: string;
}

const STEP_LABELS: Record<string, string> = {
  cloud_vision: 'Cloud Vision',
  param_pack: 'Parameter Pack',
  production: 'Production Planning',
  manufacturing: 'Manufacturing',
  fusion: 'Decision Fusion',
  template_graph: 'Template Graph',
  cad_kernel: 'CAD Kernel',
  quality: 'Quality Check',
  closed_loop: 'Learning Record',
};

const StepIcon: React.FC<{ status: string }> = ({ status }) => {
  switch (status) {
    case 'completed': return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
    case 'running': return <Loader2 className="w-4 h-4 text-indigo-500 animate-spin" />;
    case 'failed': return <XCircle className="w-4 h-4 text-red-500" />;
    default: return <Clock className="w-4 h-4 text-slate-300" />;
  }
};

const PipelineProgress: React.FC<PipelineProgressProps> = ({ result, className = '' }) => {
  const stepOrder = [
    'cloud_vision', 'param_pack', 'production', 'manufacturing',
    'fusion', 'template_graph', 'cad_kernel', 'quality', 'closed_loop'
  ];

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Pipeline Progress</h3>
        <span className="text-xs font-semibold text-slate-600">{result.status}</span>
      </div>

      <div className="space-y-1">
        {stepOrder.map((stepKey) => {
          const step = result.steps.find(s => s.step === stepKey);
          const label = STEP_LABELS[stepKey] || stepKey;
          return (
            <div key={stepKey} className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs transition-colors ${
              step?.status === 'completed' ? 'bg-emerald-50 text-emerald-700' :
              step?.status === 'running' ? 'bg-indigo-50 text-indigo-700' :
              step?.status === 'failed' ? 'bg-red-50 text-red-700' :
              'text-slate-400'
            }`}>
              <StepIcon status={step?.status || 'pending'} />
              <span className="font-medium">{label}</span>
              {step?.detail && step.status === 'completed' && (
                <span className="ml-auto text-[10px] opacity-75 truncate max-w-[120px]">{step.detail}</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Overall score */}
      {result.outputs?.quality_score && (
        <div className="mt-4 pt-3 border-t border-slate-100">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-600">Quality Score</span>
            <span className="text-sm font-bold text-indigo-600">{parseFloat(result.outputs.quality_score).toFixed(2)}</span>
          </div>
        </div>
      )}

      {/* Errors */}
      {result.errors && result.errors.length > 0 && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-xl">
          <p className="text-xs font-bold text-red-700 mb-1">Errors</p>
          {result.errors.map((e, i) => (
            <p key={i} className="text-[11px] text-red-600 font-mono">{e.slice(0, 200)}</p>
          ))}
        </div>
      )}
    </div>
  );
};

export default PipelineProgress;
