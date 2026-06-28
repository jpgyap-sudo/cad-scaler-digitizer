import React, { useState } from 'react';

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

type Props = {
  questions: SmartQuestion[];
  disabled?: boolean;
  onApply: (answers: Record<string, string>) => void;
};

export default function SmartConfirmations({ questions, disabled, onApply }: Props) {
  const [answers, setAnswers] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const q of questions || []) {
      if (q.default_value) init[q.id] = String(q.default_value);
    }
    return init;
  });

  if (!questions || questions.length === 0) return null;

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
          {questions.length} smart check{questions.length > 1 ? 's' : ''}
        </span>
      </div>

      <div className="mt-4 space-y-3">
        {questions.map((q) => (
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

      <button
        disabled={disabled}
        onClick={() => onApply(answers)}
        className="mt-4 w-full rounded-xl bg-amber-600 text-white font-bold py-2.5 hover:bg-amber-700 disabled:opacity-50"
      >
        Apply answers and regenerate
      </button>
    </div>
  );
}
