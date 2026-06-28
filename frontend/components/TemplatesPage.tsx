import React, { useState, useEffect } from "react";
import { BookOpen, Ruler, Loader2, Search, SlidersHorizontal, Play } from "lucide-react";

const ENGINE_BASE = import.meta.env.VITE_CAD_ENGINE_URL || "/py-api";

interface TemplateParam { name: string; min_value?: number; max_value?: number; default?: number; description?: string }
interface Template { id: string; name: string; family: string; product_type: string; parameters: TemplateParam[] }

function TemplateSvg({ family, name }: { family: string; name: string }) {
  const size = 90;
  const c = size / 2;
  const svg = (children: React.ReactNode) => (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0">
      {children}
    </svg>
  );

  // Table family
  if (family.includes("table")) {
    if (name.toLowerCase().includes("round") || name.toLowerCase().includes("pedestal")) {
      return svg(
        <>
          <ellipse cx={c} cy={35} rx={32} ry={18} fill="#e0e7ff" stroke="#6366f1" strokeWidth={1.5} />
          <rect x={c - 4} y={52} width={8} height={22} rx={2} fill="#c7d2fe" stroke="#6366f1" strokeWidth={1} />
          <rect x={c - 8} y={72} width={16} height={6} rx={3} fill="#a5b4fc" stroke="#6366f1" strokeWidth={1} />
        </>
      );
    }
    if (name.toLowerCase().includes("console") || name.toLowerCase().includes("sofa")) {
      return svg(
        <>
          <rect x={12} y={25} width={66} height={14} rx={2} fill="#e0e7ff" stroke="#6366f1" strokeWidth={1.5} />
          <rect x={16} y={38} width={4} height={30} rx={1} fill="#c7d2fe" stroke="#6366f1" strokeWidth={1} />
          <rect x={70} y={38} width={4} height={30} rx={1} fill="#c7d2fe" stroke="#6366f1" strokeWidth={1} />
        </>
      );
    }
    if (name.toLowerCase().includes("coffee")) {
      return svg(
        <>
          <rect x={15} y={32} width={60} height={16} rx={3} fill="#e0e7ff" stroke="#6366f1" strokeWidth={1.5} />
          <rect x={20} y={47} width={4} height={18} rx={1} fill="#c7d2fe" stroke="#6366f1" strokeWidth={1} />
          <rect x={66} y={47} width={4} height={18} rx={1} fill="#c7d2fe" stroke="#6366f1" strokeWidth={1} />
        </>
      );
    }
    // Default rectangular table
    return svg(
      <>
        <rect x={15} y={28} width={60} height={18} rx={2} fill="#e0e7ff" stroke="#6366f1" strokeWidth={1.5} />
        <rect x={18} y={45} width={5} height={24} rx={1} fill="#c7d2fe" stroke="#6366f1" strokeWidth={1} />
        <rect x={67} y={45} width={5} height={24} rx={1} fill="#c7d2fe" stroke="#6366f1" strokeWidth={1} />
        <rect x={18} y={75} width={54} height={4} rx={1} fill="#a5b4fc" stroke="#6366f1" strokeWidth={1} />
      </>
    );
  }

  // Seating (sofa, chair)
  if (family.includes("seating") || family.includes("chair")) {
    if (name.toLowerCase().includes("sofa") || name.toLowerCase().includes("couch")) {
      return svg(
        <>
          <rect x={10} y={28} width={70} height={22} rx={6} fill="#d1fae5" stroke="#10b981" strokeWidth={1.5} />
          <rect x={6} y={30} width={8} height={30} rx={3} fill="#a7f3d0" stroke="#10b981" strokeWidth={1} />
          <rect x={76} y={30} width={8} height={30} rx={3} fill="#a7f3d0" stroke="#10b981" strokeWidth={1} />
          <rect x={16} y={49} width={58} height={18} rx={3} fill="#d1fae5" stroke="#10b981" strokeWidth={1} />
          <rect x={22} y={66} width={4} height={8} rx={1} fill="#a7f3d0" stroke="#10b981" strokeWidth={1} />
          <rect x={64} y={66} width={4} height={8} rx={1} fill="#a7f3d0" stroke="#10b981" strokeWidth={1} />
        </>
      );
    }
    // Chair
    return svg(
      <>
        <rect x={20} y={32} width={50} height={14} rx={2} fill="#d1fae5" stroke="#10b981" strokeWidth={1.5} />
        <rect x={46} y={10} width={12} height={22} rx={2} fill="#a7f3d0" stroke="#10b981" strokeWidth={1} />
        <rect x={24} y={45} width={4} height={24} rx={1} fill="#a7f3d0" stroke="#10b981" strokeWidth={1} />
        <rect x={62} y={45} width={4} height={24} rx={1} fill="#a7f3d0" stroke="#10b981" strokeWidth={1} />
      </>
    );
  }

  // Bed
  if (family.includes("bed")) {
    return svg(
      <>
        <rect x={8} y={32} width={74} height={30} rx={3} fill="#f3e8ff" stroke="#9333ea" strokeWidth={1.5} />
        <rect x={4} y={28} width={10} height={34} rx={2} fill="#e9d5ff" stroke="#9333ea" strokeWidth={1} />
        <rect x={76} y={28} width={10} height={34} rx={2} fill="#e9d5ff" stroke="#9333ea" strokeWidth={1} />
        <line x1={20} y1={40} x2={70} y2={40} stroke="#d8b4fe" strokeWidth={1} strokeDasharray="2,2" />
        <rect x={30} y={70} width={8} height={6} rx={1} fill="#e9d5ff" stroke="#9333ea" strokeWidth={1} />
        <rect x={52} y={70} width={8} height={6} rx={1} fill="#e9d5ff" stroke="#9333ea" strokeWidth={1} />
      </>
    );
  }

  // Cabinet
  if (family.includes("cabinet")) {
    if (name.toLowerCase().includes("nightstand") || name.toLowerCase().includes("bedside")) {
      return svg(
        <>
          <rect x={22} y={20} width={46} height={52} rx={3} fill="#fef3c7" stroke="#d97706" strokeWidth={1.5} />
          <rect x={28} y={26} width={34} height={18} rx={1} fill="#fde68a" stroke="#d97706" strokeWidth={1} />
          <circle cx={60} cy={36} r={2} fill="#d97706" />
          <rect x={28} y={48} width={34} height={18} rx={1} fill="#fde68a" stroke="#d97706" strokeWidth={1} />
          <circle cx={60} cy={58} r={2} fill="#d97706" />
        </>
      );
    }
    if (name.toLowerCase().includes("tv") || name.toLowerCase().includes("media")) {
      return svg(
        <>
          <rect x={12} y={35} width={66} height={35} rx={2} fill="#fef3c7" stroke="#d97706" strokeWidth={1.5} />
          <rect x={16} y={40} width={58} height={10} rx={1} fill="#fde68a" stroke="#d97706" strokeWidth={1} />
          <rect x={16} y={54} width={26} height={12} rx={1} fill="#fef3c7" stroke="#d97706" strokeWidth={1} />
          <rect x={48} y={54} width={26} height={12} rx={1} fill="#fef3c7" stroke="#d97706" strokeWidth={1} />
          <rect x={26} y={72} width={4} height={5} rx={1} fill="#fde68a" />
          <rect x={60} y={72} width={4} height={5} rx={1} fill="#fde68a" />
        </>
      );
    }
    return svg(
      <>
        <rect x={16} y={18} width={58} height={56} rx={2} fill="#fef3c7" stroke="#d97706" strokeWidth={1.5} />
        <rect x={20} y={22} width={50} height={14} rx={1} fill="#fde68a" stroke="#d97706" strokeWidth={1} />
        <rect x={20} y={39} width={50} height={14} rx={1} fill="#fef3c7" stroke="#d97706" strokeWidth={1} />
        <rect x={20} y={56} width={50} height={14} rx={1} fill="#fde68a" stroke="#d97706" strokeWidth={1} />
        <circle cx={66} cy={30} r={2} fill="#d97706" />
        <circle cx={66} cy={46} r={2} fill="#d97706" />
        <circle cx={66} cy={63} r={2} fill="#d97706" />
      </>
    );
  }

  // Desk
  if (family.includes("desk")) {
    return svg(
      <>
        <rect x={10} y={25} width={70} height={12} rx={2} fill="#cffafe" stroke="#0891b2" strokeWidth={1.5} />
        <rect x={14} y={36} width={4} height={32} rx={1} fill="#a5f3fc" stroke="#0891b2" strokeWidth={1} />
        <rect x={72} y={36} width={4} height={32} rx={1} fill="#a5f3fc" stroke="#0891b2" strokeWidth={1} />
        <rect x={14} y={72} width={62} height={4} rx={1} fill="#67e8f9" stroke="#0891b2" strokeWidth={1} />
        {/* Modesty panel */}
        <rect x={30} y={38} width={30} height={20} rx={1} fill="#a5f3fc" stroke="#0891b2" strokeWidth={0.5} opacity={0.4} />
      </>
    );
  }

  // Reception counter
  if (family.includes("counter")) {
    return svg(
      <>
        <rect x={12} y={30} width={66} height={38} rx={2} fill="#ffe4e6" stroke="#e11d48" strokeWidth={1.5} />
        <rect x={12} y={30} width={30} height={38} rx={2} fill="#fecdd3" stroke="#e11d48" strokeWidth={1} />
        <line x1={42} y1={30} x2={42} y2={68} stroke="#e11d48" strokeWidth={0.5} />
        <text x={22} y={55} fontSize={8} fill="#e11d48" textAnchor="middle" fontWeight="bold">TOP</text>
        <text x={62} y={55} fontSize={8} fill="#e11d48" textAnchor="middle">BASE</text>
      </>
    );
  }

  // Wardrobe
  if (family.includes("wardrobe")) {
    return svg(
      <>
        <rect x={18} y={14} width={54} height={62} rx={2} fill="#f3f4f6" stroke="#6b7280" strokeWidth={1.5} />
        <rect x={22} y={18} width={24} height={30} rx={1} fill="#e5e7eb" stroke="#6b7280" strokeWidth={1} />
        <rect x={48} y={18} width={20} height={30} rx={1} fill="#e5e7eb" stroke="#6b7280" strokeWidth={1} />
        <rect x={22} y={52} width={46} height={18} rx={1} fill="#f9fafb" stroke="#6b7280" strokeWidth={1} />
        <circle cx={60} cy={34} r={2} fill="#6b7280" />
      </>
    );
  }

  // Generic fallback
  return svg(
    <rect x={15} y={15} width={60} height={60} rx={4} fill="#f3f4f6" stroke="#9ca3af" strokeWidth={1.5} />
  );
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
  for (const [key, color] of Object.entries(FAMILY_COLORS)) { if (family.includes(key)) return color; }
  return "bg-gray-100 text-gray-700 border-gray-200";
}

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch(`${ENGINE_BASE}/templates`)
      .then((r) => r.json())
      .then((data) => { setTemplates(data.templates || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const filtered = search
    ? templates.filter((t) => t.name.toLowerCase().includes(search.toLowerCase()) || t.id.toLowerCase().includes(search.toLowerCase()))
    : templates;

  const grouped: Record<string, Template[]> = {};
  for (const t of filtered) { if (!grouped[t.family]) grouped[t.family] = []; grouped[t.family].push(t); }

  if (loading) return <div className="flex items-center justify-center py-16"><Loader2 size={20} className="animate-spin text-gray-400" /></div>;

  return (
    <div className="max-w-4xl mx-auto py-6 px-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
            <BookOpen size={18} className="text-indigo-500" />
            {templates.length} Engineering Templates
          </h2>
          <p className="text-xs text-gray-500">Visual CAD templates with parameter ranges — click a card to see details.</p>
        </div>
        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Search..." className="w-36 pl-7 pr-2 py-1.5 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none" />
        </div>
      </div>

      {Object.entries(grouped).map(([family, items]) => (
        <div key={family} className="mb-4">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 px-1">{family.replace(/_/g, " ")}</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
            {items.map((t) => (
              <details key={t.id} className="bg-white border border-gray-200 rounded-lg overflow-hidden hover:border-indigo-300 transition-colors group">
                <summary className="cursor-pointer">
                  <div className="flex flex-col items-center p-3">
                    <TemplateSvg family={t.family} name={t.name} />
                    <span className="text-xs font-semibold text-gray-800 mt-1.5 text-center leading-tight">{t.name}</span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded border font-medium mt-1 ${getFamilyColor(t.family)}`}>{t.family}</span>
                  </div>
                </summary>
                <div className="px-3 pb-3 pt-0 border-t border-gray-100">
                  <p className="text-[9px] text-gray-400 font-mono mt-1.5 mb-1">{t.id}</p>
                  {t.parameters && t.parameters.length > 0 && (
                    <TemplateSliders template={t} />
                  )}
                </div>
              </details>
            ))}
          </div>
        </div>
      ))}

      {filtered.length === 0 && <p className="text-sm text-gray-400 text-center py-8">No templates match "{search}"</p>}
    </div>
  );
}

function TemplateSliders({ template }: { template: Template }) {
  const params = template.parameters.slice(0, 6);
  const [values, setValues] = useState<Record<string, number>>({});
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const init: Record<string, number> = {};
    for (const p of params) {
      init[p.name] = p.default ?? ((p.min_value ?? 0) + (p.max_value ?? 100)) / 2;
    }
    setValues(init);
  }, [template.id]);

  const suggest = async () => {
    setLoading(true);
    const searchParams = new URLSearchParams();
    searchParams.set("furniture_type", template.product_type);
    for (const [k, v] of Object.entries(values)) {
      if (k.includes("length") || k.includes("width") || k === "diameter_mm") searchParams.set("width_cm", String(v / 10));
      if (k.includes("height")) searchParams.set("height_cm", String(v / 10));
      if (k.includes("depth")) searchParams.set("depth_cm", String(v / 10));
    }
    try {
      const r = await fetch(`${ENGINE_BASE}/templates/suggest?${searchParams.toString()}`, { signal: AbortSignal.timeout(10000) });
      const data = await r.json();
      setResult(data);
    } catch { setResult({ error: "Request failed" }); }
    setLoading(false);
  };

  return (
    <div className="px-1 pt-1 space-y-2">
      <div className="space-y-1.5">
        {params.map((p) => {
          const minV = p.min_value ?? 0;
          const maxV = p.max_value ?? 500;
          const stepV = Math.max(1, (maxV - minV) / 50);
          return (
            <div key={p.name}>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-gray-500 truncate">{p.name.replace(/_/g, " ")}</span>
                <span className="text-indigo-600 font-semibold w-14 text-right">{values[p.name] ?? minV}mm</span>
              </div>
              <input type="range" min={minV} max={maxV} step={stepV}
                value={values[p.name] ?? minV}
                onChange={(e) => setValues({ ...values, [p.name]: parseFloat(e.target.value) })}
                className="w-full h-1 bg-gray-200 rounded-full appearance-none cursor-pointer accent-indigo-500" />
            </div>
          );
        })}
      </div>
      <button onClick={suggest} disabled={loading}
        className="w-full flex items-center justify-center gap-1 py-1 text-[10px] bg-indigo-50 text-indigo-600 rounded hover:bg-indigo-100 disabled:opacity-50">
        {loading ? "..." : <><Play size={10} /> Suggest Template</>}
      </button>
      {result && (
        <div className="text-[9px] text-gray-500 bg-gray-50 rounded p-1.5 mt-1">
          {result.error ? <span className="text-red-500">{result.error}</span> : (
            <>
              <p>Solved: {result.solved_dimensions?.width_cm ?? "?"} × {result.solved_dimensions?.depth_cm ?? "?"} × {result.solved_dimensions?.overall_height_cm ?? "?"}cm</p>
              <p>Confidence: {(result.overall_confidence * 100).toFixed(0)}%</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
