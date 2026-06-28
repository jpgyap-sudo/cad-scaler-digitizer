# 🔄 SuperRoo Agent Updates Log

**Purpose:** Every agent writes updates here — commit messages, bugs found, decisions made.  
**Format:** Each entry: `YYYY-MM-DD HH:MM TZ | Agent | Commit | What | Type`  
**Rule:** Append-only. Never edit or delete entries. Use SUSPECTED/CONFIRMED/FIXED for bugs.

---

## 2026-06-28

| Time (TZ) | Agent | Commit | Update | Type |
|-----------|-------|--------|--------|------|
| 06:38 +08 | SuperRoo | `31a30f8` | **Populated UPDATES_LOG.md** with full 40+ entry commit history from 2026-06-28 | DOCS |
| 06:34 +08 | SuperRoo | `6d95734` | Docs: log comparison_agent score-weighting bug + coffee table DXF view gap | DOCS |
| 06:32 +08 | SuperRoo | `cc25b32` | **UPDATES_LOG.md** created — persistent agent update log with commit tracking, known issues, usage guide | FEATURE |
| 06:30 +08 | SuperRoo | `3f74959` | **Self-calibration loop**: crawler → ratio solver. `scripts/auto_calibrate_from_crawled.py` writes `calibration_ledger.json`; `reference_ratio_solver` reads it at runtime. 259 products feed ALL digitizations. | FEATURE |
| 06:28 +08 | SuperRoo | `5b81a02` | **Pipeline wiring**: CFG + SelfCritic + confidence gates in `/digitize/unified` Phases 7-9. Audit bugs B-1 through B-9 verified fixed. `ftype` variable dedup, image path fix for self-critic. | FIX |
| 06:20 +08 | SuperRoo | `adabcff` | Docs: log production DB schema gap found+fixed during audit | DOCS |
| 05:58 +08 | SuperRoo | `578d73b` | Fix: `real_h`/`real_d` UnboundLocalError regression, remove dead shape-detection code | FIX |
| 05:38 +08 | Kilo/Codex | `ccc2e52` | Chore: final commit — all pending changes, stale files removed, cfg/self_critic/grammar modules added | CHORE |
| 05:37 +08 | SuperRoo | `bcec55f` | **CFG + Grammar + SelfCritic + Heatmap**: 12 new files, ~1,070 lines wrapper. 25+ template types across 6 families. render→compare→repair loop. Confidence color overlay on CAD preview. | FEATURE |
| 20:38 +08 | SuperRoo | `90be31f` | Fix: Vivaldi 80x80→80x140 + CFG canonical import + `validate_drawing` alias | FIX |
| 20:21 +08 | SuperRoo | `f1407c6` | Fix: shape-based template dispatch + `real_d` bug (depth was never used) | FIX |
| 20:02 +08 | SuperRoo | `db8ea5c` | Audit complete — all bugs fixed, 10/10 dims, commit + deploy | FIX |
| 19:45 +08 | SuperRoo | `a0c3803` | SVG skeleton preview in frontend + accuracy benchmark script | FEATURE |
| 19:33 +08 | SuperRoo | `d373d6f` | Fix: add Query import, deduplicate save functions, restore deleted template graph .v1.json files | FIX |
| 19:15 +08 | SuperRoo | `feafb78` | Fix: Glenn sofa height (2→82cm median) + Evon bed (W)x(L)x(H) dimension pattern | FIX |
| 18:50 +08 | SuperRoo | `36191f6` | All 5 phases integrated and verified | FEATURE |
| 18:22 +08 | SuperRoo | `ba9185e` | Fix: 8 remaining audit issues — duplicates, stale files, dead code, swagger | FIX |
| 18:11 +08 | SuperRoo | `b58f4ef` | Fix: audit — 7 critical+high wiring gaps + engineering agent | FIX |
| 18:04 +08 | SuperRoo | `7e4e234` | Fix: coffee_table dispatch never used or exposed depth, breaking crawled tables | FIX |
| 17:59 +08 | Kilo/Codex | `a2eaa35` | Fix: add missing Query import to routes.py | FIX |
| 17:55 +08 | SuperRoo | `58e4f67` | 7-phase Product DNA Architecture — Phase 1/2/3/5/7 | FEATURE |
| 17:42 +08 | All | `44ffe5e` | Deploy all updates — Nginx DNS fix, MCP server, all containers | DEPLOY |
| 17:35 +08 | All | `ad8d1ef` | Fix: Nginx 502 error — dynamic DNS resolution for upstream containers | FIX |
| 17:28 +08 | SuperRoo | `63d0146` | **259 Shopify product templates** + Visual DNA search engine | FEATURE |
| 17:04 +08 | SuperRoo | `d3841d9` | Fix: 9 audit bugs in confirmation loop integration | FIX |
| 16:54 +08 | SuperRoo | `6a62eff` | Integrate confirmation loop pack — structured AI analysis → template match → user confirm → DXF/SVG | FEATURE |
| 16:41 +08 | SuperRoo | `2aa3ba7` | Fix: add missing save functions, dispatch, and manifest entries for lounge_chair, sideboard, tv_console, 7 new fixture types | FIX |
| 16:37 +08 | SuperRoo | `b8506ea` | Fix: audit findings — deduplicated save functions, `_save_drawing_model` for 7 new types, bed alias fix | FIX |
| 16:31 +08 | SuperRoo | `1c46725` | HomeU 25-template upgrade — smart template selector, 7 new DXF types, dynamic schema builder | FEATURE |
| 16:18 +08 | SuperRoo | `4bb6ee6` | MCP server for ChatGPT — 13 tools to control the CAD digitizer | FEATURE |
| 16:12 +08 | SuperRoo | `43cc7c4` | Real image benchmark, 7 new fixture specs, trained ML classifier, correction feedback loop | FEATURE |
| 16:10 +08 | SuperRoo | `4067875` | Wire correction feedback into ML retraining loop | FEATURE |
| 16:02 +08 | SuperRoo | `c43ce0d` | Fix: body_html dimension extraction — mm units, H-prefix, (H) labels | FIX |
| 15:48 +08 | SuperRoo | `22809a6` | Fix: standardize DXF layers (OBJECT/DIMENSION/LEADER/CENTERLINE/MTEXT/HATCH) across all helpers | FIX |
| 15:43 +08 | SuperRoo | `1ca5074` | Fix: crawl-to-dxf used the wrong digitize endpoint for real product photos | FIX |
| 15:36 +08 | SuperRoo | `6b8abc0` | Fix: add fixtures bind mount to python-worker container for benchmark endpoints | FIX |
| 15:32 +08 | SuperRoo | `0aec00c` | Fix: 3 audit gaps — SmartConfirmations wiring, furniture crash, endpoint robustness | FIX |
| 15:27 +08 | SuperRoo | `ba2aa77` | Fix: audit round 2 — merged_dims crash, SVG preview hardcode, scale pipeline, section_predictor, benchmarks | FIX |
| 15:19 +08 | SuperRoo | `a83b227` | Smart Auto Workflow — single endpoint, no mode selection | FEATURE |
| 15:07 +08 | SuperRoo | `73b4849` | Add engine mode explanations to How It Works tab | FEATURE |
| 15:05 +08 | SuperRoo | `809474c` | Fix: add missing ResourcesPage.tsx that broke the frontend build entirely | FIX |
| 14:57 +08 | SuperRoo | `fe0b89d` | Fix: engineering template sliders never rendered for any of the 18 templates | FIX |

---

## Known Issues (Open)

| ID | Found | Agent | Description | Status |
|----|-------|-------|-------------|--------|
| AUDIT-001 | 2026-06-27 | SuperRoo | `Reference graph files (.v1.json)` deleted by Kilo during cleanup — restored in `d373d6f` | CONFIRMED-FIXED |
| AUDIT-002 | 2026-06-27 | SuperRoo | `Coffee table dispatch` ignores `depth_cm` — tables always generate wrong side view | CONFIRMED-FIXED |
| AUDIT-003 | 2026-06-27 | SuperRoo | `LAST_PROPOSAL` global state — not thread-safe between users | CONFIRMED-FIXED |
| AUDIT-004 | 2026-06-28 | SuperRoo | `ProvenanceEntry` had no `note` field — fixed via evidence list | CONFIRMED-FIXED |
| AUDIT-005 | 2026-06-28 | SuperRoo | `cfg_to_drawing_model` double-appended polygons — fixed | CONFIRMED-FIXED |
| AUDIT-006 | 2026-06-28 | SuperRoo | Self-critic router passed empty `image_path` — added UploadFile | CONFIRMED-FIXED |
| AUDIT-007 | 2026-06-28 | SuperRoo | `from_unified_result` only extracted 2 of 6 fields — extended | CONFIRMED-FIXED |

---

## How To Use This Log

**For agents:**
```python
# Append an entry after any commit:
# 1. Open UPDATES_LOG.md
# 2. Add a row under the current date section
# 3. Format: | HH:MM TZ | AgentName | `ab12def` | Description (max 200 chars) | TYPE |
# Types: FEATURE | FIX | DEPLOY | DOCS | CHORE | BREAKING
# TZ examples: +08 for Manila, +00 for UTC
```

**For bug tracking:**
- If you find a bug, add it to the Known Issues table
- Mark as `SUSPECTED` → `CONFIRMED` → `FIXED` → `CONFIRMED-FIXED`
- Reference the commit hash that fixed it

**For humans:**
- Scroll up for the latest changes
- Check Known Issues for unresolved bugs
- Each commit hash is clickable in VSCode
