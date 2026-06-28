import React, { useState, useEffect } from "react";
import { Cpu, Layers, Wrench, Ruler, Package, HardHat, Database, Shield, BarChart3, Loader2, ExternalLink } from "lucide-react";

const ENGINE_BASE = import.meta.env.VITE_CAD_ENGINE_URL || "/py-api";
const API = "http://localhost:4000";

interface EngineeringResult {
  product_id: string;
  furniture_type: string;
  furniture_subtype: string;
  family: string;
  overall_dimensions: Record<string, number>;
  dimensions_confidence: number;
  materials: Array<{ component: string; material: string; confidence: number; alternatives?: string[] }>;
  joinery: Array<{ type: string; probability: number; description: string }>;
  structural_notes: string[];
  manufacturing_notes: string[];
  bill_of_materials: Array<{ component: string; quantity: number; material: string; size_mm: string }>;
  recommended_layers: string[];
  confidence_scores: Record<string, number>;
}

export default function EngineeringPage() {
  const [productId, setProductId] = useState("homeu-tangerie-table");
  const [furnitureType, setFurnitureType] = useState("dining_table");
  const [result, setResult] = useState<EngineeringResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeSection, setActiveSection] = useState<string>("dims");
  const [recent, setRecent] = useState<any[]>([]);

  useEffect(() => {
    fetch(`${ENGINE_BASE}/engineer/families`).then(r => r.json()).then(d => {
      const types: string[] = [];
      Object.values(d.families as Record<string, string[]>).forEach(arr => types.push(...arr));
      if (types.length > 0) setFurnitureType(types[0]);
    }).catch(() => {});
    fetch(`${ENGINE_BASE}/engineer/analyses`).then(r => r.json()).then(d => setRecent(d)).catch(() => {});
  }, []);

  const analyze = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${ENGINE_BASE}/engineer/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id: productId, furniture_type: furnitureType }),
      });
      setResult(await r.json());
    } catch {}
    setLoading(false);
  };

  const Section = ({ id, icon, title, children }: { id: string; icon: React.ReactNode; title: string; children: React.ReactNode }) => (
    <details open={activeSection === id} className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <summary onClick={() => setActiveSection(id)} className="px-4 py-2.5 flex items-center gap-2 cursor-pointer hover:bg-gray-50 text-xs font-semibold text-gray-700">
        {icon} {title}
      </summary>
      <div className="px-4 pb-3 pt-1 border-t border-gray-100 text-xs text-gray-600">{children}</div>
    </details>
  );

  return (
    <div className="max-w-4xl mx-auto py-6 px-4 space-y-4">
      <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
        <Cpu size={18} className="text-amber-500" />
        Furniture Engineering Agent
      </h2>

      <div className="flex gap-2">
        <input value={productId} onChange={e => setProductId(e.target.value)}
          placeholder="Product ID" className="flex-1 px-3 py-2 text-sm border rounded-lg" />
        <select value={furnitureType} onChange={e => setFurnitureType(e.target.value)}
          className="px-3 py-2 text-sm border rounded-lg bg-white">
          {["dining_table","sofa","coffee_table","desk","cabinet","dining_chair","bed","armchair","wardrobe","console_table"].map(t =>
            <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
          )}
        </select>
        <button onClick={analyze} disabled={loading}
          className="px-4 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-700 disabled:opacity-50 flex items-center gap-2">
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Cpu size={14} />}
          Analyze
        </button>
      </div>

      {result && (
        <div className="space-y-3">
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-amber-800">{result.furniture_type.replace(/_/g, " ")} — {result.product_id}</p>
              <p className="text-xs text-amber-600">Family: {result.family} | Subtype: {result.furniture_subtype}</p>
            </div>
            <div className="text-right text-xs text-amber-700">
              Confidence: {(result.dimensions_confidence * 100).toFixed(0)}%
            </div>
          </div>

          <Section id="dims" icon={<Ruler size={14} />} title="Overall Dimensions">
            <div className="grid grid-cols-3 gap-2 mt-1">
              {Object.entries(result.overall_dimensions).map(([k, v]) => (
                <div key={k} className="bg-gray-50 rounded p-2">
                  <p className="text-gray-400">{k.replace(/_/g, " ")}</p>
                  <p className="font-semibold">{v}cm</p>
                </div>
              ))}
            </div>
          </Section>

          <Section id="materials" icon={<Database size={14} />} title="Materials">
            {result.materials.map((m, i) => (
              <div key={i} className="flex items-center justify-between py-1 border-b border-gray-50">
                <span className="font-medium">{m.component}</span>
                <span className="text-gray-500">{m.material} ({(m.confidence)}%)</span>
              </div>
            ))}
          </Section>

          <Section id="joinery" icon={<Wrench size={14} />} title="Joinery Analysis">
            {result.joinery.map((j, i) => (
              <div key={i} className="py-1 border-b border-gray-50">
                <p className="font-medium">{j.type.replace(/_/g, " ")} — {j.components}</p>
                <p className="text-gray-400">{j.description} ({(j.probability)}%)</p>
              </div>
            ))}
          </Section>

          <Section id="bom" icon={<Package size={14} />} title="Bill of Materials">
            <table className="w-full text-[10px]">
              <thead><tr className="text-gray-400"><th className="text-left">Component</th><th>Qty</th><th>Material</th><th>Size</th></tr></thead>
              <tbody>
                {result.bill_of_materials.map((b, i) => (
                  <tr key={i} className="border-b border-gray-50">
                    <td className="py-1">{b.component}</td>
                    <td className="text-center">{b.quantity}</td>
                    <td>{b.material}</td>
                    <td className="text-right">{b.size_mm}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>

          <Section id="structural" icon={<Shield size={14} />} title="Structural Notes">
            <ul className="list-disc pl-4 space-y-1">
              {result.structural_notes.map((n, i) => <li key={i}>{n}</li>)}
            </ul>
          </Section>

          <Section id="manufacturing" icon={<HardHat size={14} />} title="Manufacturing Notes">
            <ul className="list-disc pl-4 space-y-1">
              {result.manufacturing_notes.map((n, i) => <li key={i}>{n}</li>)}
            </ul>
          </Section>

          <Section id="layers" icon={<Layers size={14} />} title="Recommended CAD Layers">
            <div className="grid grid-cols-2 gap-1">
              {result.recommended_layers.map((l, i) => (
                <div key={i} className="bg-gray-50 rounded px-2 py-1 text-[10px] font-mono">{l}</div>
              ))}
            </div>
          </Section>

          <Section id="confidence" icon={<BarChart3 size={14} />} title="Confidence Scores">
            <div className="space-y-1">
              {Object.entries(result.confidence_scores).map(([k, v]) => (
                <div key={k} className="flex items-center gap-2">
                  <span className="w-36">{k.replace(/_/g, " ")}</span>
                  <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${v}%`, backgroundColor: v > 80 ? "#22c55e" : v > 60 ? "#eab308" : "#ef4444" }} />
                  </div>
                  <span className="w-8 text-right">{v}%</span>
                </div>
              ))}
            </div>
          </Section>
        </div>
      )}

      {recent.length > 0 && !result && (
        <div className="bg-white border border-gray-200 rounded-lg p-3">
          <p className="text-xs font-semibold text-gray-700 mb-2">Recent Analyses</p>
          {recent.map((r: any, i: number) => (
            <div key={i} className="flex items-center justify-between py-1 text-xs text-gray-500 border-b border-gray-50">
              <span>{r.furniture_type} — {r.product_id}</span>
              <span>{r.created_at}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
