# 🔄 SuperRoo Agent Updates Log

**Purpose:** Every agent writes updates here — commit messages, bugs found, decisions made.  
**Format:** Each entry: `YYYY-MM-DD HH:MM TZ | Agent | Commit | What | Type`  
**Rule:** Append-only. Never edit or delete entries. Use SUSPECTED/CONFIRMED/FIXED for bugs.

---

## 2026-06-29

| Time (TZ) | Agent | Commit | Update | Type |
|-----------|-------|--------|--------|------|
| 18:29 +08 | SuperRoo | `7daab88` | **Fix template matcher**: Load from ALL directories (25 + 218 = 243 templates). Auto-enrich categories from filenames with 35 regex patterns. Wire visual_dna_index (4,122 lines) into scoring — archetype boost + component overlap. DNA was never used before. | FIX |
| 18:18 +08 | SuperRoo | `2f1fdf6` | **Restore 218 product catalog templates** deleted in ef70fd0. root cause of "no center_table" — files existed on disk but were never loaded. | FIX |
| 18:10 +08 | SuperRoo | `3cb0f12` | Fix 3 audit gaps in furniture-draft: wrong field access (support_type.value crashes), lock state never loaded (get_locked_components existed but was never called), circular import risk | FIX |
| 18:02 +08 | SuperRoo | `2034d76` | **Single /digitize/furniture-draft endpoint** — replaces 4 old routes. Component locking system. Linked views. Confidence review. | FEATURE |
| 17:42 +08 | SuperRoo | `fa34309` | **Linters everywhere**: ESLint + Prettier (frontend), Ruff + MyPy (backend). 144 violations fixed automatically. | FEATURE |

## 2026-06-28

| Time (TZ) | Agent | Commit | Update | Type |
|-----------|-------|--------|--------|------|
| 06:38 +08 | SuperRoo | `31a30f8` | Populated UPDATES_LOG.md with full commit history | DOCS |
| 06:34 +08 | SuperRoo | `6d95734` | Docs: log comparison_agent score-weighting bug + coffee table DXF view gap | DOCS |
| 06:32 +08 | SuperRoo | `cc25b32` | **UPDATES_LOG.md created** — persistent agent update log | FEATURE |
| 06:30 +08 | SuperRoo | `3f74959` | **Self-calibration loop**: crawler → ratio solver | FEATURE |
| 06:28 +08 | SuperRoo | `5b81a02` | **Pipeline wiring**: CFG + SelfCritic + confidence gates in /digitize/unified | FIX |
| 05:37 +08 | SuperRoo | `bcec55f` | **CFG + Grammar + SelfCritic + Heatmap**: 12 new files, ~1,070 lines wrapper | FEATURE |
| 17:28 +08 | SuperRoo | `63d0146` | **259 Shopify product templates** + Visual DNA search engine | FEATURE |
| 16:31 +08 | SuperRoo | `1c46725` | HomeU 25-template upgrade — smart template selector, 7 new DXF types | FEATURE |

---

## 2026-06-30

| Time (TZ) | Agent | Commit | Update | Type |
|-----------|-------|--------|--------|------|
| 10:39 +08 | Kilo | `7eb6d92` | **3-tier API fallback**: gemini-2.5-flash → gemini-2.5-pro → gpt-4o → gpt-4o-mini (8 retries). Handles quota exhaustion gracefully. | FEATURE |
| 10:39 +08 | Kilo | `b679e5e` | **XML parser for SVG**: Replaced fragile regex parsing with `xml.etree.ElementTree`. Handles namespaces, entities, attribute ordering. Regex fallback when XML fails. | FIX |
| 10:39 +08 | Kilo | `fe6bdb0` | **Position-based view fallback**: When `data-view` attributes missing, assigns SVG paths to FRONT/SIDE/TOP/ISO by x-coordinate. | FIX |
| 10:39 +08 | Kilo | `fe6bdb0` | **Arc midpoint sampling**: SVG `A` arc commands now sampled at 12 points with sinusoidal curvature instead of straight-line approximation. | FEATURE |
| 10:39 +08 | Kilo | `fe6bdb0` | **Q/q quad bezier + S/s smooth cubic**: SVG path parser now handles all common path commands (M,L,H,V,C,Q,A,Z). | FEATURE |
| 10:39 +08 | Kilo | `d06a0cf` | **Prompt simplified**: Removed `polyline` field — Gemini produces SVG only. Coordinates extracted server-side. Markdown-wrapped JSON for safe parsing. | FIX |
| 10:39 +08 | Kilo | `23bdbca` | **Switch Flash as primary**: gemini-2.5-flash (cheap, fast) instead of pro. Simplified prompt reduced cognitive load enough for Flash to respond in time. | FEATURE |
| 10:39 +08 | Kilo | `ccceac5` | **Entity-escaped SVG attributes**: `&quot;` entities decoded before SVG parsing. | FIX |
| 10:39 +08 | Kilo | `0e102d0` | **C/c cubic bezier SVG parsing**: Path extractor now handles cubic bezier curves (12 segments each). | FIX |
| 10:39 +08 | Kilo | `71f044d` | **Image resize to 600px** before Gemini call — 4x faster processing, reduces ReadTimeouts. Timeout increased 60→120s. | FIX |
| 10:39 +08 | Kilo | `f9bd371` | **No polyline in prompt**: Gemini produces SVG ONLY. Components array is metadata only. Coordinate extraction is deterministic server-side. | PERF |
| 10:39 +08 | Kilo | `025a78f` | **Self-filling 3-stage classifier**: `enrich_dna_from_crawl()` auto-populates product_dna.json + visual_dna_index.json. 393 products seeded from Shopify batches. | FEATURE |
| 10:39 +08 | Kilo | `47ce545` | **Deep top_shape wiring + bed→rectangular dispatch**: shape signal flows to SVG renderer. Bed now renders as 4-view rectangular table (not 1-view headboard). | FEATURE |
| 10:39 +08 | Kilo | `5dac3e3` | **Isometric helper + 4-view cabinet/sofa/wardrobe**: `_add_isometric_box()` + TOP/ISO views for 3 template types. | FEATURE |
| 10:39 +08 | Kilo | `3a8311e` | **Gemini multi-view extraction**: Single photo → 4-panel SVG (FRONT, SIDE, TOP, ISOMETRIC) from one API call. 1200×300 canvas. | FEATURE |
| 10:39 +08 | Kilo | `03ad0b1` | **StarVector integration plan**: Hybrid pipeline — Gemini detects components → StarVector-1B renders clean SVG per component → DXF converter. See PIPELINE.md. | PLAN |

## Known Issues

| ID | Found | Agent | Description | Status |
|----|-------|-------|-------------|--------|
| AUDIT-008 | 2026-06-29 | SuperRoo | 218 product catalog templates deleted during cleanup — restored in `2f1fdf6` | CONFIRMED-FIXED |
| AUDIT-009 | 2026-06-29 | SuperRoo | template_matcher.py only loaded 25 templates from wrong directory — now loads 243 from both dirs | CONFIRMED-FIXED |
| AUDIT-010 | 2026-06-29 | SuperRoo | visual_dna_index.json (4,122 lines) existed but never imported — now wired into scoring | CONFIRMED-FIXED |
| AUDIT-001-007 | 2026-06-28 | SuperRoo | 7 historical bugs — all confirmed fixed in commits | ALL FIXED |
| AUDIT-011 | 2026-06-30 | Kilo | Gemini SVG inconsistent across models — `data-view` attributes vary, `&quot;` entity usage differs, coordinate format drifts. Mitigated with 3-tier SVG parser (XML→regex→position). Root fix: StarVector integration (PIPELINE.md). | CONFIRMED-MITIGATED |
