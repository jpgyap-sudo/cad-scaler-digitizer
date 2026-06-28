# 🔄 SuperRoo Agent Updates Log

**Purpose:** Every agent writes updates here — commit messages, bugs found, decisions made.  
**Format:** Each entry: `YYYY-MM-DD HH:MM UTC | Agent | Commit | What | Bug/Success`  
**Rule:** Append-only. Never edit or delete entries. Use SUSPECTED/CONFIRMED/FIXED for bugs.

---

## 2026-06-28

| Time (UTC) | Agent | Commit | Update | Type |
|------------|-------|--------|--------|------|
| 22:30 | SuperRoo | `3f74959` | **Calibration ledger**: crawler → ratio solver self-calibration loop. 259+ products now feed dimension averages into ALL future digitizations. Script: `scripts/auto_calibrate_from_crawled.py` writes `resources/calibration_ledger.json`; `reference_ratio_solver.get_reference_ratios()` reads it at runtime. | FEATURE |
| 22:28 | SuperRoo | `5b81a02` | **Pipeline wiring**: CFG + SelfCritic + confidence gates integrated into `/digitize/unified` as Phases 7-9. Response now returns `cfg`, `self_critic`, `confidence_gate` alongside existing data. Audit bugs B-1 through B-9 verified already fixed in live code. | FIX |
| 22:26 | SuperRoo | `adabcff` | Docs: log production DB schema gap found+fixed during audit | DOCS |
| 21:37 | SuperRoo | `bcec55f` | **CFG + Grammar + SelfCritic + Heatmap**: 12 new files, ~1,070 lines wrapper code. 25+ template types in grammar across 6 families. render→compare→repair loop. Confidence color overlay on CAD preview. | FEATURE |

## 2026-06-27

| Time (UTC) | Agent | Commit | Update | Type |
|------------|-------|--------|--------|------|
| — | Kilo/Codex | `ccc2e52` | Chore: final commit — all pending changes, stale files removed, cfg/self_critic/grammar modules added | CHORE |
| — | SuperRoo | `90be31f` | Fix: Vivaldi 80x80→80x140 + CFG canonical import + validate_drawing alias | FIX |
| — | SuperRoo | `f1407c6` | Fix: shape-based template dispatch + real_d bug fix | FIX |
| — | SuperRoo | `db8ea5c` | Audit complete — all bugs fixed, 10/10 dims, commit + deploy | FIX |
| — | SuperRoo | `a0c3803` | SVG skeleton preview in frontend + accuracy benchmark script | FEATURE |
| — | SuperRoo | `d373d6f` | Fix: add Query import, deduplicate save functions, restore template graph files | FIX |
| — | SuperRoo | `feafb78` | Fix: Glenn sofa height (2→82cm median) + Evon bed (W)x(L)x(H) pattern | FIX |
| — | SuperRoo | `36191f6` | All 5 phases integrated and verified | FEATURE |
| — | SuperRoo | `ba9185e` | Fix: 8 remaining audit issues — duplicates, stale files, dead code, swagger | FIX |
| — | SuperRoo | `b58f4ef` | Fix: audit — 7 critical+high wiring gaps + engineering agent | FIX |
| — | SuperRoo | `7e4e234` | Fix: coffee_table dispatch never used or exposed depth, breaking crawled tables | FIX |
| — | Kilo/Codex | `a2eaa35` | Fix: add missing Query import to routes.py | FIX |
| — | SuperRoo | `58e4f67` | 7-phase Product DNA Architecture — Phase 1/2/3/5/7 | FEATURE |
| — | All agents | `44ffe5e` | Deploy all updates — Nginx DNS fix, MCP server, all containers | DEPLOY |
| — | All agents | `ad8d1ef` | Fix: Nginx 502 error — dynamic DNS resolution for upstream containers | FIX |

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
# 3. Format: | HH:MM | AgentName | `commit_short` | Description (max 200 chars) | TYPE |
# Types: FEATURE | FIX | DEPLOY | DOCS | CHORE | BREAKING
```

**For bug tracking:**
- If you find a bug, add it to the Known Issues table
- Mark as `SUSPECTED` → `CONFIRMED` → `FIXED` → `CONFIRMED-FIXED`
- Reference the commit hash that fixed it

**For humans:**
- Scroll up for the latest changes
- Check Known Issues for unresolved bugs
- Each commit hash is clickable in VSCode
