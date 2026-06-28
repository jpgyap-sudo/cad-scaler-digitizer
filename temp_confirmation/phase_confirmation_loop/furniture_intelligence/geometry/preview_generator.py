from __future__ import annotations
from pathlib import Path
from furniture_intelligence.schemas.furniture_analysis import ApprovedTemplate


def generate_svg_preview(approved: ApprovedTemplate, out_path: str) -> str:
    p = approved.parameters_mm
    a = approved.final_analysis
    L = p.get('overall_length', 1200)
    D = p.get('overall_depth', 700)
    H = p.get('overall_height', 360)
    T = p.get('top_thickness', 22)
    bowl = p.get('bowl_diameter', 220)
    base_bot = p.get('base_bottom_diameter', 520)
    base_top = p.get('base_top_diameter', 320)
    scale = 0.38

    def sx(v): return v * scale

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="900" viewBox="0 0 1400 900">
<style>
.label{{font:16px Arial; font-weight:700}} .note{{font:13px Arial}} .dim{{font:12px Arial}} .line{{stroke:#111;stroke-width:2;fill:none}} .thin{{stroke:#333;stroke-width:1;fill:none}} .dash{{stroke:#555;stroke-width:1;stroke-dasharray:6 6;fill:none}} .stone{{fill:#ddd;stroke:#111;stroke-width:2}} .metal{{fill:#b08a45;stroke:#111;stroke-width:2}} .hatch{{fill:url(#hatch)}}
</style>
<defs><pattern id="hatch" patternUnits="userSpaceOnUse" width="8" height="8"><path d="M0,8 L8,0" stroke="#999" stroke-width="1"/></pattern></defs>
<rect x="10" y="10" width="1380" height="880" fill="white" stroke="#111"/>
<text x="30" y="45" class="label">MELINA / OVAL SCULPTURAL PEDESTAL COFFEE TABLE — TEMPLATE PREVIEW</text>
<text x="930" y="45" class="note">AI describes → User confirms → Code generates CAD</text>

<rect x="25" y="70" width="430" height="330" fill="none" stroke="#111"/>
<text x="40" y="98" class="label">TOP VIEW / PLAN</text>
<ellipse cx="240" cy="235" rx="{sx(L)/2}" ry="{sx(D)/2}" class="stone"/>
<ellipse cx="240" cy="235" rx="{sx(bowl)/2}" ry="{sx(bowl)/2}" class="metal"/>
<ellipse cx="240" cy="235" rx="{sx(bowl*0.72)/2}" ry="{sx(bowl*0.72)/2}" class="thin"/>
<line x1="{240-sx(L)/2-30}" y1="235" x2="{240+sx(L)/2+30}" y2="235" class="dash"/>
<line x1="240" y1="{235-sx(D)/2-30}" x2="240" y2="{235+sx(D)/2+30}" class="dash"/>
<text x="170" y="380" class="dim">Oval top, recessed circular brass bowl</text>

<rect x="475" y="70" width="430" height="330" fill="none" stroke="#111"/>
<text x="490" y="98" class="label">FRONT ELEVATION</text>
<rect x="{690-sx(L)/2}" y="165" width="{sx(L)}" height="{max(4,sx(T))}" class="stone"/>
<path d="M {690-sx(base_top)/2} 185 L {690+sx(base_top)/2} 185 L {690+sx(base_bot)/2} {185+sx(H-T)} L {690-sx(base_bot)/2} {185+sx(H-T)} Z" class="metal"/>
<line x1="690" y1="135" x2="690" y2="380" class="dash"/>
<text x="520" y="382" class="dim">Thin slab + tapered truncated cone pedestal</text>

<rect x="925" y="70" width="430" height="330" fill="none" stroke="#111"/>
<text x="940" y="98" class="label">SIDE ELEVATION</text>
<rect x="{1140-sx(D)/2}" y="165" width="{sx(D)}" height="{max(4,sx(T))}" class="stone"/>
<path d="M {1140-sx(base_top)/2} 185 L {1140+sx(base_top)/2} 185 L {1140+sx(base_bot)/2} {185+sx(H-T)} L {1140-sx(base_bot)/2} {185+sx(H-T)} Z" class="metal"/>
<line x1="1140" y1="135" x2="1140" y2="380" class="dash"/>
<text x="980" y="382" class="dim">Side view uses depth, not same as plan length</text>

<rect x="25" y="420" width="610" height="300" fill="none" stroke="#111"/>
<text x="40" y="448" class="label">SECTION A-A</text>
<rect x="90" y="520" width="{sx(L)}" height="{max(6,sx(T))}" class="hatch" stroke="#111"/>
<path d="M {90+sx(L)/2-sx(bowl)/2} 520 Q {90+sx(L)/2} 585 {90+sx(L)/2+sx(bowl)/2} 520" fill="#b08a45" stroke="#111" stroke-width="2"/>
<rect x="{90+sx(L)/2-sx(base_top)/2}" y="545" width="{sx(base_top)}" height="12" fill="#777" stroke="#111"/>
<path d="M {90+sx(L)/2-sx(base_top)/2} 557 L {90+sx(L)/2+sx(base_top)/2} 557 L {90+sx(L)/2+sx(base_bot)/2} 675 L {90+sx(L)/2-sx(base_bot)/2} 675 Z" class="hatch" stroke="#111"/>
<text x="520" y="540" class="note">Stone top</text><text x="520" y="570" class="note">Recessed brass bowl</text><text x="520" y="600" class="note">Hidden steel plate</text><text x="520" y="630" class="note">Hollow brushed brass base</text>

<rect x="660" y="420" width="695" height="300" fill="none" stroke="#111"/>
<text x="675" y="448" class="label">APPROVED STRUCTURE JSON</text>
<text x="680" y="485" class="note">Category: {a.category}</text>
<text x="680" y="510" class="note">Top shape: {a.top_shape}</text>
<text x="680" y="535" class="note">Base type: {a.base_type}</text>
<text x="680" y="560" class="note">Components: {', '.join([c.type for c in a.components])}</text>
<text x="680" y="590" class="note">Views: {', '.join(a.required_views)}</text>
<text x="680" y="625" class="note">Template: {approved.proposal.template_name}</text>
<text x="680" y="655" class="note">Generate DXF only after user approves this structure.</text>
</svg>'''
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(svg, encoding='utf-8')
    return out_path
