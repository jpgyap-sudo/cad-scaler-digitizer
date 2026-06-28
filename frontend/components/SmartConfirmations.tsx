import React, { useState, useEffect } from 'react';

export type SmartQuestion = {
  id: string;
  type: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | string;
  title: string;
  message: string;
  options: Array<{ label: string; value: string }>;
  default_value?: string;
  required?: boolean;
  affects_dxf?: boolean;
};

/** Format from furniture_intelligence template_proposal.questions */
export type UncertaintyQuestion = {
  field: string;
  question: string;
  options: string[];
};

type Props = {
  questions: SmartQuestion[];
  uncertaintyQuestions?: UncertaintyQuestion[];
  disabled?: boolean;
  onApply: (answers: Record<string, string>) => void;
};

function uncertaintyToSmartQuestions(uqs: UncertaintyQuestion[]): SmartQuestion[] {
  return uqs.map((u) => ({
    id: u.field,
    type: 'field_confirmation',
    severity: 'high' as const,
    title: u.question,
    message: u.question,
    options: u.options.map((o) => ({ label: o, value: o })),
    required: true,
    affects_dxf: true,
  }));
}

export default function SmartConfirmations({ questions, uncertaintyQuestions, disabled, onApply }: Props) {
  const [answers, setAnswers] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const q of questions || []) {
      if (q.default_value) init[q.id] = String(q.default_value);
    }
    const uqs = uncertaintyQuestions || [];
    for (const uq of uqs) {
      if (uq.options.length > 0) init[uq.field] = uq.options[0];
    }
    return init;
  });

  // Rebuild answers when prop changes
  useEffect(() => {
    setAnswers((prev) => {
      const next = { ...prev };
      const uqs = uncertaintyQuestions || [];
      for (const uq of uqs) {
        if (!(uq.field in next) && uq.options.length > 0) {
          next[uq.field] = uq.options[0];
        }
      }
      return next;
    });
  }, [uncertaintyQuestions]);

  // Merge uncertainty questions as SmartQuestions
  const smartQuestions = questions || [];
  const uqSmart = uncertaintyQuestions ? uncertaintyToSmartQuestions(uncertaintyQuestions) : [];
  const allQuestions = [...smartQuestions, ...uqSmart];

  // De-duplicate by id
  const seen = new Set<string>();
  const deduped = allQuestions.filter((q) => {
    if (seen.has(q.id)) return false;
    seen.add(q.id);
    return true;
  });

  // Separate dimension_review questions (handled by dimension correction panel)
  const dimQuestions = deduped.filter((q) => q.type === 'dimension_review');
  const confirmQuestions = deduped.filter((q) => q.type !== 'dimension_review');

  if (deduped.length === 0) return null;

  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 my-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-amber-900">Review before final DXF</h3>
          <p className="text-sm text-amber-800 mt-1">
            The engine only asks when the answer can change scale, template, or DXF accuracy.
          </p>
        </div>
        <span className="text-xs font-semibold bg-white border border-amber-200 text-amber-700 px-2 py-1 rounded-full">
          {deduped.length} smart check{deduped.length > 1 ? 's' : ''}
        </span>
      </div>

      <div className="mt-4 space-y-3">
        {confirmQuestions.map((q) => (
          <div key={q.id} className="bg-white rounded-xl border border-amber-100 p-3">
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase tracking-wide font-bold text-amber-700">{q.severity}</span>
              <h4 className="font-semibold text-slate-900">{q.title}</h4>
            </div>
            <p className="text-sm text-slate-600 mt-1">{q.message}</p>

            {q.type === 'dimension_review' ? (
              <div className="mt-3 text-sm text-slate-500">
                Use the dimension correction panel below for these values.
              </div>
            ) : (
              <select
                className="mt-3 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
                value={answers[q.id] || ''}
                disabled={disabled}
                onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
              >
                <option value="">Choose...</option>
                {q.options.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            )}
          </div>
        ))}
      </div>

      {dimQuestions.length > 0 && (
        <div className="mt-3 text-sm text-amber-700 bg-amber-100 rounded-xl p-3">
          {dimQuestions.length} dimension review question{dimQuestions.length > 1 ? 's' : ''} pending — resolve in the dimension correction panel below.
        </div>
      )}

      <button
        disabled={disabled || confirmQuestions.length === 0}
        onClick={() => onApply(answers)}
        className="mt-4 w-full rounded-xl bg-amber-600 text-white font-bold py-2.5 hover:bg-amber-700 disabled:opacity-50"
      >
        Apply answers and regenerate
      </button>
    </div>
  );
}
