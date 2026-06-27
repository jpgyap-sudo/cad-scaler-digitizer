"""Automated gap scan — finds missing connections in the Unified Intelligence pipeline."""
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend-python'))
issues = {}


def gap(name: str, severity: str, detail: str):
    issues[name] = f"[{severity}] {detail}"


# 1. Unified pipeline exists?
try:
    from app.backend.cad_intelligence.unified_router import run_unified_pipeline, UnifiedResult
    gap("01_unified_module", "OK", "unified_router.py loads cleanly")
except Exception as e:
    gap("01_unified_module", "CRITICAL", f"unified_router.py failed: {e}")

# 2. Unified endpoint registered?
try:
    from app.api.routes import router
    unified_routes = [r.path for r in router.routes if 'unified' in r.path]
    if unified_routes:
        gap("02_unified_endpoint", "OK", f"Registered: {unified_routes}")
    else:
        gap("02_unified_endpoint", "CRITICAL", "No /digitize/unified route found")
except Exception as e:
    gap("02_unified_endpoint", "CRITICAL", f"Routes import failed: {e}")

# 3. Unified endpoint has DXF/SVG/Download?
try:
    from app.api.routes import router
    for route in router.routes:
        path = getattr(route, 'path', '')
        if 'digitize/unified' in path:
            import inspect
            fn = route.endpoint
            src = inspect.getsource(fn)
            has_dxf = 'dxf_file' in src or 'DXF' in src or 'dxf' in src.lower()
            has_svg = 'svg' in src.lower()
            gap("03_unified_export", "MEDIUM" if not has_dxf else "OK",
                f"Has DXF export: {has_dxf}, Has SVG: {has_svg}")
            break
except Exception as e:
    gap("03_unified_export", "MEDIUM", f"Check failed: {e}")

# 4. Frontend has digitizeUnified?
fe_services = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'services', 'cadEngine.ts')
if os.path.exists(fe_services):
    with open(fe_services, encoding='utf-8') as f:
        content = f.read()
    has_fn = 'export async function digitizeUnified' in content
    has_type = 'UnifiedResult' in content
    has_source = 'UnifiedDimSource' in content
    gap("04_frontend_unified", "OK" if has_fn else "CRITICAL",
        f"Function: {has_fn}, Type: {has_type}, DimSource: {has_source}")
else:
    gap("04_frontend_unified", "CRITICAL", "cadEngine.ts not found")

# 5. App.tsx has "Smart" or "Unified" mode button?
app_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'App.tsx')
if os.path.exists(app_path):
    with open(app_path, encoding='utf-8') as f:
        app_content = f.read()
    has_smart_mode = 'smart' in app_content.lower() or 'unified' in app_content.lower()
    has_digitize_call = 'digitizeUnified' in app_content
    gap("05_app_tsx_unified", "MEDIUM" if not has_smart_mode else "OK",
        f"Has smart mode: {has_smart_mode}, Calls unified: {has_digitize_call}")

# 6. Unified result returns dimensions with provenance
try:
    from app.backend.cad_intelligence.unified_router import UnifiedResult, ProvenanceValue
    ur = UnifiedResult()
    ur.product_type = ProvenanceValue("round_pedestal_table", "ai_vision", 0.85, "AI vision")
    ur.dimensions["diameter_cm"] = ProvenanceValue(80.0, "ocr", 0.91, "OCR: '80 DIA'")
    api = ur.to_api_dict()
    has_type_source = 'product_type' in api and api['product_type'] is not None
    has_dim_source = 'dimensions' in api and len(api['dimensions']) > 0
    gap("06_unified_provenance", "OK" if has_type_source and has_dim_source else "MEDIUM",
        f"Type with source: {has_type_source}, Dims with source: {has_dim_source}")
except Exception as e:
    gap("06_unified_provenance", "MEDIUM", f"Provenance check failed: {e}")

# 7. Template graph attached?
try:
    api = ur.to_api_dict()
    gap("07_unified_template", "MEDIUM" if 'template' not in api else "OK",
        "Template graph in response" if 'template' in api else "Template graph MISSING from response")
except:
    pass

# 8. Tests pass?
try:
    import subprocess
    r = subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_templates.py', '-q', '--tb=no'],
                       capture_output=True, text=True, cwd=os.path.join(os.path.dirname(__file__), '..', 'backend-python'))
    gap("08_tests_passing", "OK" if r.returncode == 0 else "CRITICAL",
        f"Exit code: {r.returncode}, {r.stdout.strip()[-100:] if r.stdout else 'no output'}")
except Exception as e:
    gap("08_tests_passing", "MEDIUM", f"Could not run tests: {e}")

# 9. Unified endpoint has error handling?
try:
    from app.api.routes import router
    for route in router.routes:
        path = getattr(route, 'path', '')
        if 'digitize/unified' in path:
            import inspect
            src = inspect.getsource(route.endpoint)
            has_error_handling = 'except Exception' in src
            has_cleanup = 'os.remove' in src
            gap("09_unified_error_handling", "OK" if has_error_handling and has_cleanup else "MEDIUM",
                f"Try/except: {has_error_handling}, Cleanup: {has_cleanup}")
            break
except Exception as e:
    gap("09_unified_error_handling", "MEDIUM", f"Check failed: {e}")

# 10. AI Vision integration?
try:
    from app.api.routes import router
    for route in router.routes:
        path = getattr(route, 'path', '')
        if 'digitize/unified' in path:
            import inspect
            src = inspect.getsource(route.endpoint)
            has_vision = 'OPENAI_API_KEY' in src or 'gpt-4o' in src or 'gemini' in src.lower()
            gap("10_unified_ai_vision", "OK" if has_vision else "MEDIUM",
                "AI Vision integration" if has_vision else "No AI Vision fallback detected")
            break
except Exception as e:
    gap("10_unified_ai_vision", "MEDIUM", f"Check failed: {e}")

# Print results
print("=" * 60)
print("UNIFIED INTELLIGENCE — GAP SCAN REPORT")
print("=" * 60)
findings = {k: v for k, v in issues.items()}
critical = [k for k, v in findings.items() if "[CRITICAL]" in v]
medium = [k for k, v in findings.items() if "[MEDIUM]" in v]
ok = [k for k, v in findings.items() if "[OK]" in v]

for k in sorted(findings.keys()):
    print(f"  {findings[k]}")

print(f"\n  CRITICAL: {len(critical)}")
print(f"  MEDIUM:   {len(medium)}")
print(f"  OK:       {len(ok)}")
print(f"\nTotal: {len(findings)} checks")
