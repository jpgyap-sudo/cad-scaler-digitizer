import React, { useState, useEffect, useRef, useCallback } from "react";
import { BookOpen, Loader2, Search, Play, FileText, Eye } from "lucide-react";

const ENGINE_BASE = import.meta.env.VITE_CAD_ENGINE_URL || "/py-api";

interface TemplateParam { name: string; min_value?: number; max_value?: number; default?: number; description?: string }
interface Template { id: string; name: string; family: string; product_type: string; parameters: TemplateParam[] }

function FallbackSvg({ family }: { family: string }) {
  const s = (c: React.ReactNode) => <svg width={90} height={90} viewBox="0 0 90 90" className="shrink-0">{c}</svg>;
  if (family.includes("table")) return s(<><rect x={15} y={28} width={60} height={18} rx={2} fill="#e0e7ff" stroke="#6366f1" strokeWidth={1.5} /><rect x={18} y={45} width={5} height={24} rx={1} fill="#c7d2fe" stroke="#6366f1" strokeWidth={1} /><rect x={67} y={45} width={5} height={24} rx={1} fill="#c7d2fe" stroke="#6366f1" strokeWidth={1} /></>);
  if (family.includes("seating")) return s(<><rect x={20} y={32} width={50} height={14} rx={2} fill="#d1fae5" stroke="#10b981" strokeWidth={1.5} /><rect x={46} y={10} width={12} height={22} rx={2} fill="#a7f3d0" stroke="#10b981" strokeWidth={1} /><rect x={24} y={45} width={4} height={24} rx={1} fill="#a7f3d0" stroke="#10b981" strokeWidth={1} /><rect x={62} y={45} width={4} height={24} rx={1} fill="#a7f3d0" stroke="#10b981" strokeWidth={1} /></>);
  if (family.includes("cabinet")) return s(<><rect x={16} y={18} width={58} height={56} rx={2} fill="#fef3c7" stroke="#d97706" strokeWidth={1.5} /><rect x={20} y={22} width={50} height={14} rx={1} fill="#fde68a" stroke="#d97706" strokeWidth={1} /><rect x={20} y={39} width={50} height={14} rx={1} fill="#fef3c7" stroke="#d97706" strokeWidth={1} /><rect x={20} y={56} width={50} height={14} rx={1} fill="#fde68a" stroke="#d97706" strokeWidth={1} /><circle cx={66} cy={30} r={2} fill="#d97706" /><circle cx={66} cy={46} r={2} fill="#d97706" /><circle cx={66} cy={63} r={2} fill="#d97706" /></>);
  if (family.includes("bed")) return s(<><rect x={8} y={32} width={74} height={30} rx={3} fill="#f3e8ff" stroke="#9333ea" strokeWidth={1.5} /><rect x={4} y={28} width={10} height={34} rx={2} fill="#e9d5ff" stroke="#9333ea" strokeWidth={1} /><rect x={76} y={28} width={10} height={34} rx={2} fill="#e9d5ff" stroke="#9333ea" strokeWidth={1} /></>);
  if (family.includes("desk")) return s(<><rect x={10} y={25} width={70} height={12} rx={2} fill="#cffafe" stroke="#0891b2" strokeWidth={1.5} /><rect x={14} y={36} width={4} height={32} rx={1} fill="#a5f3fc" stroke="#0891b2" strokeWidth={1} /><rect x={72} y={36} width={4} height={32} rx={1} fill="#a5f3fc" stroke="#0891b2" strokeWidth={1} /></>);
  return s(<rect x={15} y={15} width={60} height={60} rx={4} fill="#f3f4f6" stroke="#9ca3af" strokeWidth={1.5} />);
}

function SkeletonPreview({ productType, values }: { productType: string; values: Record<string, number> }) {
  const [svg, setSvg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  const w = Object.entries(values).find(([k]) => k.includes("length") || k.includes("width"))?.[1] ?? 1000;
  const h = Object.entries(values).find(([k]) => k.includes("height"))?.[1] ?? 800;
  const d = Object.entries(values).find(([k]) => k.includes("depth"))?.[1];

  const fetchSvg = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({ width_cm: String(w / 10), height_cm: String(h / 10) });
    if (d) params.set("depth_cm", String(d / 10));
    fetch(`${ENGINE_BASE}/skeleton/${productType}?${params}`, { signal: AbortSignal.timeout(5000) })
      .then(r => r.ok ? r.text() : Promise.reject())
      .then(s => setSvg(s))
      .catch(() => setSvg(null))
      .finally(() => setLoading(false));
  }, [productType, w, h, d]);

  useEffect(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(fetchSvg, 400);
    return () => clearTimeout(timer.current);
  }, [fetchSvg]);

  if (loading && !svg) return <div className="w-full h-[120px] flex items-center justify-center bg-gray-50 rounded"><Loader2 size={16} className="animate-spin text-gray-300" /></div>;
  if (svg) return <div className="w-full h-[120px] overflow-hidden bg-white border border-gray-100 rounded" dangerouslySetInnerHTML={{ __html: svg }} />;
  return null;
}

const FAMILY_COLORS: Record<string, string> = {
  table: "bg-blue-100 text-blue-700 border-blue-200",
  seating: "bg-green-100 text-green-700 border-green-200",
  bed: "bg-purple-100 text-purple-700 border-purple-200",
  cabinet: "bg-amber-100 text-amber-700 border-amber-200",
  desk: "bg-cyan-100 text-cyan-700 border-cyan-200",
  reception_counter: "bg-rose-100 text-rose-700 border-rose-200",
  counter: "bg-rose-100 text-rose-700 border-rose-200",
};

function getFamilyColor(family: string): string {
  for (const [k, c] of Object.entries(FAMILY_COLORS)) { if (family.includes(k)) return c; }
  return "bg-gray-100 text-gray-700 border-gray-200";
}

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch(`${ENGINE_BASE}/templates`)
      .then(r => r.json())
      .then(d => { setTemplates(d.templates || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const filtered = search
    ? templates.filter(t => t.name.toLowerCase().includes(search.toLowerCase()) || t.id.toLowerCase().includes(search.toLowerCase()))
    : templates;

  const grouped: Record<string, Template[]> = {};
  for (const t of filtered) { if (!grouped[t.family]) grouped[t.family] = []; grouped[t.family].push(t); }

  if (loading) return <div className="flex items-center justify-center py-16"><Loader2 size={20} className="animate-spin text-gray-400" /></div>;

  return (
    <div className="max-w-5xl mx-auto py-6 px-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
            <BookOpen size={18} className="text-indigo-500" />
            {templates.length} Parametric CAD Templates
          </h2>
          <p className="text-xs text-gray-500">Live skeleton preview updates as you adjust parameters — click to expand.</p>
        </div>
        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input type="text" value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search..." className="w-36 pl-7 pr-2 py-1.5 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none" />
        </div>
      </div>

      {Object.entries(grouped).map(([family, items]) => (
        <div key={family} className="mb-6">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 px-1">{family.replace(/_/g, " ")}</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {items.map(t => <TemplateCard key={t.id} template={t} />)}
          </div>
        </div>
      ))}

      {filtered.length === 0 && <p className="text-sm text-gray-400 text-center py-8">No templates match "{search}"</p>}
    </div>
  );
}

function TemplateCard({ template }: { template: Template }) {
  const [open, setOpen] = useState(false);

  return (
    <div className={`bg-white border rounded-lg transition-all ${open ? 'border-indigo-300 shadow-sm' : 'border-gray-200 hover:border-indigo-200'}`}>
      <button onClick={() => setOpen(!open)} className="w-full text-left p-3 flex items-center gap-3">
        <FallbackSvg family={template.family} />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-gray-800 truncate">{template.name}</p>
          <p className="text-[10px] text-gray-400 font-mono truncate mt-0.5">{template.id}</p>
          <span className={`inline-block text-[9px] px-1.5 py-0.5 rounded border font-medium mt-1 ${getFamilyColor(template.family)}`}>{template.family}</span>
        </div>
        <div className={`w-5 h-5 rounded-full border border-gray-300 flex items-center justify-center transition-transform ${open ? 'rotate-180 bg-indigo-50 border-indigo-300' : ''}`}>
          <svg width="10" height="6" viewBox="0 0 10 6" fill="none"><path d="M1 1l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </div>
      </button>

      {open && template.parameters && template.parameters.length > 0 && (
        <TemplateSliders template={template} />
      )}
    </div>
  );
}

function TemplateSliders({ template }: { template: Template }) {
  const params = template.parameters.slice(0, 6);
  const [values, setValues] = useState<Record<string, number>>({});
  const [dxfSvg, setDxfSvg] = useState<string | null>(null);
  const [dxfLoading, setDxfLoading] = useState(false);

  useEffect(() => {
    const init: Record<string, number> = {};
    for (const p of params) init[p.name] = p.default ?? ((p.min_value ?? 0) + (p.max_value ?? 100)) / 2;
    setValues(init);
    setDxfSvg(null);
  }, [template.id]);

  const set = (name: string, val: number) => {
    setValues(v => ({ ...v, [name]: val }));
    setDxfSvg(null);
  };

  const generateDxf = async () => {
    setDxfLoading(true);
    setDxfSvg(null);
    const sp = new URLSearchParams({ furniture_type: template.product_type });
    for (const [k, v] of Object.entries(values)) {
      if (k.includes("length") || k.includes("width") || k === "diameter_mm") sp.set("width_cm", String(v / 10));
      if (k.includes("height")) sp.set("height_cm", String(v / 10));
      if (k.includes("depth")) sp.set("depth_cm", String(v / 10));
    }
    try {
      const r = await fetch(`${ENGINE_BASE}/templates/suggest?${sp}`, { signal: AbortSignal.timeout(15000) });
      const data = await r.json();
      if (data.solved_dimensions) {
        const { width_cm, depth_cm, overall_height_cm } = data.solved_dimensions;
        const sk = await fetch(`${ENGINE_BASE}/skeleton/${template.product_type}?width_cm=${width_cm}&height_cm=${overall_height_cm}&depth_cm=${depth_cm}`, { signal: AbortSignal.timeout(5000) });
        if (sk.ok) setDxfSvg(await sk.text());
      }
    } catch { /* silent */ }
    setDxfLoading(false);
  };

  const dims = {
    w: Object.entries(values).find(([k]) => k.includes("length") || k.includes("width"))?.[1] ?? 1000,
    h: Object.entries(values).find(([k]) => k.includes("height"))?.[1] ?? 800,
    d: Object.entries(values).find(([k]) => k.includes("depth"))?.[1],
  };

  return (
    <div className="border-t border-gray-100">
      <div className="p-3">
        <SkeletonPreview productType={template.product_type} values={values} />
      </div>
      <div className="px-3 pb-3 space-y-2">
        {params.map(p => {
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
                onChange={e => set(p.name, parseFloat(e.target.value))}
                className="w-full h-1 bg-gray-200 rounded-full appearance-none cursor-pointer accent-indigo-500" />
            </div>
          );
        })}
        <div className="flex gap-2 pt-1">
          <button onClick={generateDxf} disabled={dxfLoading}
            className="flex-1 flex items-center justify-center gap-1 py-1.5 text-[10px] bg-indigo-50 text-indigo-600 rounded hover:bg-indigo-100 disabled:opacity-50">
            {dxfLoading ? <Loader2 size={10} className="animate-spin" /> : <Eye size={10} />}
            {dxfLoading ? "Generating..." : "Preview DXF"}
          </button>
          <a href={`${ENGINE_BASE}/crawl-to-dxf?url=&category=${template.product_type}`}
            className="flex-1 flex items-center justify-center gap-1 py-1.5 text-[10px] bg-emerald-50 text-emerald-600 rounded hover:bg-emerald-100">
            <FileText size={10} /> New from URL
          </a>
        </div>
        {dxfSvg && (
          <div className="mt-2 border border-gray-200 rounded overflow-hidden">
            <div className="text-[9px] text-gray-400 px-2 py-1 bg-gray-50 border-b border-gray-200">DXF Preview (skeleton)</div>
            <div className="w-full h-[150px] overflow-hidden bg-white" dangerouslySetInnerHTML={{ __html: dxfSvg }} />
          </div>
        )}
      </div>
    </div>
  );
}
