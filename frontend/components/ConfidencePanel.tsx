/**
 * ConfidencePanel — displays source/confidence metadata for CAD entities.
 *
 * Shows a color-coded table of every dimension, its value, source,
 * confidence, and evidence. The user can click to correct/confirm.
 *
 * Source colors:
 *   measured_from_pixels: green
 *   ocr_confirmed: blue
 *   user_confirmed: purple
 *   ratio_estimated: amber
 *   default_template: red
 */

import React, { useState, useMemo } from 'react';

export interface DimItem {
  text: string;
  value_cm: number;
  is_diameter: boolean;
  /** One of: 'measured', 'ocr_confirmed', 'user_confirmed', 'ratio_estimated', 'default_template' */
  source: string;
  confidence: number;
  evidence?: string[];
  assigned_to?: string;
}

interface ConfidencePanelProps {
  /** Dimensions from the accuracy pipeline */
  dimensions: DimItem[];
  /** Associations from dimension_associator */
  associations?: Array<{
    text: string;
    value_cm: number;
    confidence: number;
    is_diameter: boolean;
    evidence?: string[];
    dim_line?: { length_px: number } | null;
    associated_circle?: [number, number, number] | null;
  }>;
  /** Line role data from accuracy pipeline */
  lineRoles?: {
    object_edges?: Array<{ role: string; confidence: number }>;
    dimension_lines?: Array<{ role: string; confidence: number }>;
    leaders?: Array<{ role: string; confidence: number }>;
    unknown?: Array<{ role: string; confidence: number }>;
  };
  /** Callback when user corrects a dimension value */
  onCorrectValue?: (text: string, newValue: number) => void;
  /** Callback when user locks/confirms a dimension */
  onLockDimension?: (text: string) => void;
  /** Callback when user corrects a line role */
  onCorrectLineRole?: (lineId: string, newRole: string) => void;
}

const SOURCE_CONFIG: Record<string, { label: string; color: string; bg: string; icon: string }> = {
  'measured': {
    label: 'Measured from pixels',
    color: 'text-emerald-700',
    bg: 'bg-emerald-50 border-emerald-200',
    icon: '📏',
  },
  'ocr_confirmed': {
    label: 'Read from drawing',
    color: 'text-blue-700',
    bg: 'bg-blue-50 border-blue-200',
    icon: '👁️',
  },
  'user_confirmed': {
    label: 'User confirmed',
    color: 'text-purple-700',
    bg: 'bg-purple-50 border-purple-200',
    icon: '✏️',
  },
  'ratio_estimated': {
    label: 'Estimated from proportions',
    color: 'text-amber-700',
    bg: 'bg-amber-50 border-amber-200',
    icon: '📐',
  },
  'default_template': {
    label: 'Template default — verify!',
    color: 'text-red-700',
    bg: 'bg-red-50 border-red-200',
    icon: '⚠️',
  },
  'unknown': {
    label: 'Unknown source',
    color: 'text-slate-500',
    bg: 'bg-slate-50 border-slate-200',
    icon: '❓',
  },
};

function getSourceConfig(source: string) {
  return SOURCE_CONFIG[source] || SOURCE_CONFIG['unknown'];
}

export const ConfidencePanel: React.FC<ConfidencePanelProps> = ({
  dimensions,
  associations,
  lineRoles,
  onCorrectValue,
  onLockDimension,
  onCorrectLineRole,
}) => {
  const [editingText, setEditingText] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>('');
  const [showLineRoles, setShowLineRoles] = useState(false);
  const [lockedTexts, setLockedTexts] = useState<Set<string>>(() => {
    // Persist lock state in sessionStorage to survive re-renders
    try {
      const stored = sessionStorage.getItem('cad_locked_dims');
      return stored ? new Set(JSON.parse(stored)) : new Set();
    } catch { return new Set(); }
  });

  // Merge associations into dimensions if available
  const mergedItems = useMemo(() => {
    if (!associations || associations.length === 0) return dimensions;

    const assocMap = new Map(associations.map(a => [a.text, a]));
    return dimensions.map(dim => {
      const assoc = assocMap.get(dim.text);
      if (assoc) {
        return {
          ...dim,
          confidence: Math.max(dim.confidence, assoc.confidence),
          evidence: [...(dim.evidence || []), ...(assoc.evidence || [])],
        };
      }
      return dim;
    });
  }, [dimensions, associations]);

  const handleStartEdit = (text: string, currentValue: number) => {
    setEditingText(text);
    setEditValue(String(currentValue));
  };

  const handleSaveEdit = (text: string) => {
    const newVal = parseFloat(editValue);
    if (!isNaN(newVal) && onCorrectValue) {
      onCorrectValue(text, newVal);
    }
    setEditingText(null);
  };

  const persistLocks = (locks: Set<string>) => {
    try { sessionStorage.setItem('cad_locked_dims', JSON.stringify([...locks])); }
    catch {}
  };

  const handleLock = (text: string) => {
    const newLocked = new Set(lockedTexts);
    newLocked.add(text);
    setLockedTexts(newLocked);
    persistLocks(newLocked);
    if (onLockDimension) onLockDimension(text);
  };

  const handleUnlock = (text: string) => {
    const newLocked = new Set(lockedTexts);
    newLocked.delete(text);
    setLockedTexts(newLocked);
    persistLocks(newLocked);
  };

  if (mergedItems.length === 0) {
    return (
      <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-sm text-slate-500 text-center">
        No dimension data available. Upload a drawing to see confidence analysis.
      </div>
    );
  }

  // Summary stats
  const measuredCount = mergedItems.filter(d => d.source === 'measured' || d.source === 'ocr_confirmed').length;
  const estimatedCount = mergedItems.filter(d => d.source === 'ratio_estimated' || d.source === 'default_template').length;
  const userConfirmedCount = lockedTexts.size;
  const avgConfidence = mergedItems.reduce((s, d) => s + d.confidence, 0) / mergedItems.length;

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-emerald-50 p-2 rounded-lg text-center border border-emerald-200">
          <div className="text-lg font-bold text-emerald-700">{measuredCount}</div>
          <div className="text-[10px] text-emerald-600">Measured</div>
        </div>
        <div className="bg-amber-50 p-2 rounded-lg text-center border border-amber-200">
          <div className="text-lg font-bold text-amber-700">{estimatedCount}</div>
          <div className="text-[10px] text-amber-600">Estimated</div>
        </div>
        <div className="bg-purple-50 p-2 rounded-lg text-center border border-purple-200">
          <div className="text-lg font-bold text-purple-700">{userConfirmedCount}</div>
          <div className="text-[10px] text-purple-600">Confirmed</div>
        </div>
      </div>

      {/* Overall confidence bar */}
      <div className="bg-white p-3 rounded-xl border border-slate-200">
        <div className="flex justify-between text-xs mb-1">
          <span className="font-medium text-slate-600">Overall Confidence</span>
          <span className={`font-bold ${avgConfidence >= 0.7 ? 'text-emerald-600' : avgConfidence >= 0.4 ? 'text-amber-600' : 'text-red-600'}`}>
            {(avgConfidence * 100).toFixed(0)}%
          </span>
        </div>
        <div className="w-full bg-slate-100 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all ${
              avgConfidence >= 0.7 ? 'bg-emerald-500' : avgConfidence >= 0.4 ? 'bg-amber-500' : 'bg-red-500'
            }`}
            style={{ width: `${avgConfidence * 100}%` }}
          />
        </div>
        <p className="text-[10px] text-slate-400 mt-1">
          Higher is better. Lock dimensions you've verified to increase confidence.
        </p>
      </div>

      {/* Dimension list */}
      <div className="space-y-2 max-h-80 overflow-y-auto">
        <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider px-1">
          Dimensions
        </h4>
        {mergedItems.map((dim, i) => {
          const config = getSourceConfig(dim.source);
          const isLocked = lockedTexts.has(dim.text);
          const isEditing = editingText === dim.text;

          return (
            <div
              key={i}
              className={`p-3 rounded-xl border transition-all ${
                isLocked
                  ? 'bg-purple-50 border-purple-300 ring-1 ring-purple-200'
                  : config.bg
              }`}
            >
              <div className="flex items-start justify-between mb-1">
                <div className="flex items-center space-x-2">
                  <span className="text-sm">{config.icon}</span>
                  <span className={`text-xs font-semibold ${config.color}`}>
                    {config.label}
                  </span>
                </div>
                <div className="flex items-center space-x-1">
                  {/* Confidence badge */}
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${
                    dim.confidence >= 0.7 ? 'bg-emerald-100 text-emerald-700' :
                    dim.confidence >= 0.4 ? 'bg-amber-100 text-amber-700' :
                    'bg-red-100 text-red-700'
                  }`}>
                    {(dim.confidence * 100).toFixed(0)}%
                  </span>
                  {/* Lock button */}
                  <button
                    onClick={() => isLocked ? handleUnlock(dim.text) : handleLock(dim.text)}
                    className={`text-xs p-1 rounded-full transition-colors ${
                      isLocked ? 'text-purple-600 bg-purple-100' : 'text-slate-400 hover:text-slate-600'
                    }`}
                    title={isLocked ? 'Unlock dimension' : 'Confirm dimension'}
                  >
                    {isLocked ? '🔒' : '🔓'}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  {dim.is_diameter && <span className="text-xs text-slate-400">⌀</span>}
                  <span className="text-sm font-semibold text-slate-800">{dim.text}</span>
                </div>
                {isEditing ? (
                  <div className="flex items-center space-x-1">
                    <input
                      type="number"
                      value={editValue}
                      onChange={e => setEditValue(e.target.value)}
                      className="w-20 px-2 py-1 text-xs border border-indigo-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                      autoFocus
                      onKeyDown={e => {
                        if (e.key === 'Enter') handleSaveEdit(dim.text);
                        if (e.key === 'Escape') setEditingText(null);
                      }}
                    />
                    <span className="text-xs text-slate-400">cm</span>
                    <button
                      onClick={() => handleSaveEdit(dim.text)}
                      className="text-xs px-2 py-1 bg-indigo-600 text-white rounded-lg"
                    >
                      ✓
                    </button>
                    <button
                      onClick={() => setEditingText(null)}
                      className="text-xs px-2 py-1 bg-slate-200 rounded-lg"
                    >
                      ✕
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-bold text-indigo-600">
                      {dim.value_cm} cm
                    </span>
                    {onCorrectValue && (
                      <button
                        onClick={() => handleStartEdit(dim.text, dim.value_cm)}
                        className="text-[10px] text-slate-400 hover:text-indigo-600 transition-colors"
                        title="Correct value"
                      >
                        ✏️
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Evidence chain */}
              {dim.evidence && dim.evidence.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {dim.evidence.slice(0, 3).map((ev, ei) => (
                    <span key={ei} className="text-[10px] bg-white/60 text-slate-500 px-1.5 py-0.5 rounded-full border border-slate-200">
                      {ev.length > 40 ? ev.slice(0, 40) + '…' : ev}
                    </span>
                  ))}
                </div>
              )}

              {isLocked && (
                <div className="mt-1 text-[10px] text-purple-600 font-medium">
                  ✅ User-confirmed — will be used as ground truth
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Line Role Correction (FG-3) */}
      {lineRoles && (
        <div className="border-t border-slate-200 pt-3 mt-3">
          <button
            onClick={() => setShowLineRoles(!showLineRoles)}
            className="w-full flex items-center justify-between px-3 py-2 bg-white rounded-xl border border-slate-200 hover:border-indigo-300 transition-colors"
          >
            <span className="text-xs font-bold text-slate-600 flex items-center">
              <span className="mr-1.5">📐</span>
              Line Roles
            </span>
            <span className={`text-[10px] text-slate-400 transition-transform ${showLineRoles ? 'rotate-180' : ''}`}>
              ▼
            </span>
          </button>
          {showLineRoles && (
            <div className="mt-2 space-y-1">
              {[
                { key: 'object_edges', label: 'Object Edges', color: 'text-slate-700', bg: 'bg-slate-100' },
                { key: 'dimension_lines', label: 'Dimension Lines', color: 'text-blue-700', bg: 'bg-blue-50' },
                { key: 'leaders', label: 'Leaders', color: 'text-amber-700', bg: 'bg-amber-50' },
                { key: 'unknown', label: 'Unclassified', color: 'text-red-600', bg: 'bg-red-50' },
              ].map(({ key, label, color, bg }) => {
                const items = (lineRoles as any)[key] || [];
                const count = items.length;
                if (count === 0) return null;
                return (
                  <div key={key} className={`flex justify-between items-center px-2 py-1.5 rounded-lg text-xs ${bg}`}>
                    <span className={`font-medium ${color}`}>{label}</span>
                    <span className="font-bold">{count} lines</span>
                  </div>
                );
              })}
              {onCorrectLineRole && (
                <p className="text-[10px] text-slate-400 mt-1 px-1">
                  Click a line on the drawing to reclassify it.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ConfidencePanel;
