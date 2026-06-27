import React, { useState, useEffect } from "react";
import { BookOpen, Ruler, Loader2 } from "lucide-react";

const ENGINE_BASE = import.meta.env.VITE_CAD_ENGINE_URL || "/py-api";

interface TemplateParam {
  min?: number;
  max?: number;
  default?: number;
}

interface Template {
  id: string;
  name: string;
  family: string;
  parameters: Record<string, TemplateParam>;
}

const FAMILY_COLORS: Record<string, string> = {
  table: "bg-blue-100 text-blue-700 border-blue-200",
  seating: "bg-green-100 text-green-700 border-green-200",
  bed: "bg-purple-100 text-purple-700 border-purple-200",
  cabinet: "bg-amber-100 text-amber-700 border-amber-200",
  desk: "bg-cyan-100 text-cyan-700 border-cyan-200",
  reception_counter: "bg-rose-100 text-rose-700 border-rose-200",
  wardrobe: "bg-gray-100 text-gray-700 border-gray-200",
  chair: "bg-green-100 text-green-700 border-green-200",
};

function getFamilyColor(family: string): string {
  for (const [key, color] of Object.entries(FAMILY_COLORS)) {
    if (family.includes(key)) return color;
  }
  return "bg-gray-100 text-gray-700 border-gray-200";
}

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch(`${ENGINE_BASE}/api/templates`)
      .then((r) => r.json())
      .then((data) => {
        setTemplates(data.templates || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const filtered = search
    ? templates.filter((t) =>
        t.name.toLowerCase().includes(search.toLowerCase()) ||
        t.id.toLowerCase().includes(search.toLowerCase()) ||
        t.family.toLowerCase().includes(search.toLowerCase())
      )
    : templates;

  const grouped: Record<string, Template[]> = {};
  for (const t of filtered) {
    if (!grouped[t.family]) grouped[t.family] = [];
    grouped[t.family].push(t);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 size={20} className="animate-spin text-gray-400" />
        <span className="ml-2 text-sm text-gray-500">Loading templates...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto py-6 px-4 text-center">
        <p className="text-sm text-red-500">Failed to load templates: {error}</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto py-6 px-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
            <BookOpen size={18} className="text-indigo-500" />
            Engineering Templates ({templates.length})
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            CAD templates used for DXF generation. Detected dimensions are matched against template parameters.
          </p>
        </div>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search templates..."
          className="w-44 px-3 py-1.5 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
        />
      </div>

      {Object.entries(grouped).map(([family, items]) => (
        <div key={family} className="mb-4">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 px-1">
            {family.replace(/_/g, " ")}
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {items.map((t) => (
              <div
                key={t.id}
                className="bg-white border border-gray-200 rounded-lg p-3 hover:border-indigo-300 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-semibold text-gray-800">{t.name}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${getFamilyColor(t.family)}`}>
                    {t.family}
                  </span>
                </div>
                <p className="text-[10px] text-gray-400 mt-1 font-mono truncate">{t.id}</p>
                {t.parameters && Object.keys(t.parameters).length > 0 && (
                  <div className="mt-2 space-y-0.5">
                    {Object.entries(t.parameters).slice(0, 4).map(([key, param]) => (
                      <div key={key} className="flex items-center gap-1.5 text-[10px] text-gray-500">
                        <Ruler size={10} className="shrink-0" />
                        <span className="font-medium">{key.replace(/_/g, " ")}:</span>
                        <span>
                          {param.min ?? "?"}–{param.max ?? "?"}mm
                          {param.default != null && ` (default: ${param.default})`}
                        </span>
                      </div>
                    ))}
                    {Object.keys(t.parameters).length > 4 && (
                      <p className="text-[10px] text-gray-400 pl-4">+{Object.keys(t.parameters).length - 4} more params</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
