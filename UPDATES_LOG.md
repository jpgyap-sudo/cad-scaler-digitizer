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

## Known Issues

| ID | Found | Agent | Description | Status |
|----|-------|-------|-------------|--------|
| AUDIT-008 | 2026-06-29 | SuperRoo | 218 product catalog templates deleted during cleanup — restored in `2f1fdf6` | CONFIRMED-FIXED |
| AUDIT-009 | 2026-06-29 | SuperRoo | template_matcher.py only loaded 25 templates from wrong directory — now loads 243 from both dirs | CONFIRMED-FIXED |
| AUDIT-010 | 2026-06-29 | SuperRoo | visual_dna_index.json (4,122 lines) existed but never imported — now wired into scoring | CONFIRMED-FIXED |
| AUDIT-001-007 | 2026-06-28 | SuperRoo | 7 historical bugs — all confirmed fixed in commits | ALL FIXED |
