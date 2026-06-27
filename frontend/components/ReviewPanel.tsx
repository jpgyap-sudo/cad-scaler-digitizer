import React, { useState } from 'react';
import { CheckCircle2, XCircle, Edit3, MessageSquare, Send, Loader2, AlertTriangle, Eye, Layers } from 'lucide-react';
import type { PipelineJobResult } from './PipelineUpload';
import type { Phase3Result } from '../services/cadEngine';

interface ReviewPanelProps {
  result: PipelineJobResult;
  onReviewComplete?: (action: string) => void;
  className?: string;
  /** Optional Phase3 result to show vision/scene analysis */
  phase3Result?: Phase3Result | null;
}

const ReviewPanel: React.FC<ReviewPanelProps> = ({ result, onReviewComplete, className = '', phase3Result }) => {
  const [action, setAction] = useState<'accept' | 'reject' | null>(null);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (reviewAction: 'accept' | 'reject') => {
    setSubmitting(true);
    setAction(reviewAction);
    try {
      const base = import.meta.env.VITE_CAD_ENGINE_URL || '';
      const url = base
        ? `${base}/api/pipeline/review`
        : `/api/pipeline/review`;

      await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: result.job_id,
          action: reviewAction,
          comment,
        }),
      });

      setSubmitted(true);
      if (onReviewComplete) onReviewComplete(reviewAction);
    } catch (err) {
      console.error('Review submit failed:', err);
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className={`p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-center ${className}`}>
        <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
        <p className="text-sm font-semibold text-emerald-700">
          {action === 'accept' ? 'Drawing accepted!' : 'Drawing rejected.'}
        </p>
        <p className="text-xs text-emerald-600 mt-1">Feedback recorded for future improvements.</p>
      </div>
    );
  }

  const phase3 = phase3Result;

  return (
    <div className={`space-y-3 ${className}`}>
      <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center">
        <MessageSquare className="w-3.5 h-3.5 mr-1.5" /> Review Drawing
      </h3>

      {/* Quality score */}
      {result.outputs?.quality_score && (
        <div className="flex items-center justify-between bg-slate-50 px-3 py-2 rounded-lg border border-slate-200">
          <span className="text-xs text-slate-600 font-medium">Quality Score</span>
          <span className="text-sm font-bold text-indigo-600">
            {parseFloat(result.outputs.quality_score).toFixed(2)}
          </span>
        </div>
      )}

      {/* Phase3 Section */}
      {phase3 && (
        <div className="space-y-3 border-t border-slate-100 pt-3">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center">
            <Eye className="w-3.5 h-3.5 mr-1.5" /> Phase 3 — Vision & Scene
          </h3>

          {/* Vision Features */}
          {phase3.vision_features && Object.keys(phase3.vision_features).length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-2">
              <h4 className="text-xs font-semibold text-slate-500 mb-1">Vision Features</h4>
              {phase3.vision_features.product_type && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500">Product Type</span>
                  <span className="text-xs font-semibold text-slate-700">
                    {phase3.vision_features.product_type}
                  </span>
                </div>
              )}
              {phase3.vision_features.confidence !== undefined && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500">Confidence</span>
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                    phase3.vision_features.confidence >= 0.8
                      ? 'bg-emerald-100 text-emerald-700'
                      : phase3.vision_features.confidence >= 0.5
                      ? 'bg-amber-100 text-amber-700'
                      : 'bg-red-100 text-red-700'
                  }`}>
                    {Math.round(phase3.vision_features.confidence * 100)}%
                  </span>
                </div>
              )}
              {/* Other vision feature keys */}
              {Object.entries(phase3.vision_features)
                .filter(([k]) => k !== 'product_type' && k !== 'confidence')
                .map(([key, val]) => (
                  <div key={key} className="flex items-center justify-between">
                    <span className="text-xs text-slate-500 capitalize">{key.replace(/_/g, ' ')}</span>
                    <span className="text-xs font-semibold text-slate-700">{String(val)}</span>
                  </div>
                ))}
            </div>
          )}

          {/* Scene Graph */}
          {phase3.scene_graph && Object.keys(phase3.scene_graph).length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <h4 className="text-xs font-semibold text-slate-500 mb-2 flex items-center">
                <Layers className="w-3 h-3 mr-1 text-indigo-400" /> Scene Graph
              </h4>
              {phase3.scene_graph.component_count !== undefined && (
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-slate-500">Components</span>
                  <span className="text-sm font-bold text-indigo-600">
                    {phase3.scene_graph.component_count}
                  </span>
                </div>
              )}
              {Object.entries(phase3.scene_graph)
                .filter(([k]) => k !== 'component_count')
                .map(([key, val]) => (
                  <div key={key} className="flex items-center justify-between text-xs py-0.5">
                    <span className="text-slate-500 capitalize">{key.replace(/_/g, ' ')}</span>
                    <span className="font-medium text-slate-700">
                      {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                    </span>
                  </div>
                ))}
            </div>
          )}

          {/* Phase 3 Warnings */}
          {phase3.warnings && phase3.warnings.length > 0 && (
            <div className="bg-white border border-amber-200 rounded-xl p-4">
              <h4 className="text-xs font-semibold text-amber-600 mb-2 flex items-center">
                <AlertTriangle className="w-3 h-3 mr-1" /> Warnings
              </h4>
              <ul className="text-xs text-amber-700 space-y-1">
                {phase3.warnings.map((w: string, i: number) => (
                  <li key={i} className="flex items-start">
                    <span className="mr-1.5">⚠️</span>
                    <span>{w}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Phase 3 Errors */}
          {phase3.errors && phase3.errors.length > 0 && (
            <div className="bg-white border border-red-200 rounded-xl p-4">
              <h4 className="text-xs font-semibold text-red-600 mb-2 flex items-center">
                <AlertTriangle className="w-3 h-3 mr-1" /> Errors
              </h4>
              <ul className="text-xs text-red-700 space-y-1">
                {phase3.errors.map((e: string, i: number) => (
                  <li key={i} className="flex items-start">
                    <span className="mr-1.5">❌</span>
                    <span>{e}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Comment */}
      <textarea value={comment} onChange={e => setComment(e.target.value)}
        placeholder="Optional: add feedback or corrections..."
        rows={2}
        className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 resize-none"
      />

      {/* Action buttons */}
      <div className="flex gap-2">
        <button onClick={() => handleSubmit('accept')} disabled={submitting}
          className="flex-1 flex items-center justify-center space-x-1.5 px-4 py-2.5 bg-emerald-600 text-white rounded-xl text-xs font-bold hover:bg-emerald-700 disabled:opacity-50 transition-all">
          {submitting && action === 'accept' ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <CheckCircle2 className="w-4 h-4" />
          )}
          <span>Accept</span>
        </button>
        <button onClick={() => handleSubmit('reject')} disabled={submitting}
          className="flex-1 flex items-center justify-center space-x-1.5 px-4 py-2.5 bg-red-600 text-white rounded-xl text-xs font-bold hover:bg-red-700 disabled:opacity-50 transition-all">
          {submitting && action === 'reject' ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <XCircle className="w-4 h-4" />
          )}
          <span>Reject</span>
        </button>
      </div>
    </div>
  );
};

export default ReviewPanel;
