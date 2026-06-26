"""End-to-end test script for CAD Scaler Digitizer."""
import requests
import sys
import os
from pathlib import Path

BASE = "http://localhost:8001"
FIXTURES = Path(__file__).parent.parent / "fixtures"

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} -- {detail}")

def test_health():
    print("\n[1/7] Health endpoint")
    r = requests.get(f"{BASE}/health", timeout=10)
    assert r.status_code == 200
    data = r.json()
    check("health returns ok", data.get("ok") == True)
    check("has hybrid flag", isinstance(data.get("hybrid"), bool))

def test_fixtures_list():
    print("\n[2/7] Benchmark fixtures list")
    r = requests.get(f"{BASE}/api/benchmark/fixtures", timeout=10)
    assert r.status_code == 200
    data = r.json()
    check("12 fixtures loaded", data.get("count") == 12)
    fixture_names = [f["name"] for f in data.get("fixtures", [])]
    for fn in ["center-table-round-100", "fabric-sofa-105x92x87", "queen-bed-150x200"]:
        check(f"fixture {fn} present", fn in fixture_names)
    for f in data.get("fixtures", []):
        check(f"fixture {f['name']} has expected_dxf", f.get("has_expected_dxf") == True)

def test_benchmark():
    print("\n[3/7] Run accuracy benchmark")
    r = requests.get(f"{BASE}/api/benchmark", timeout=180)
    assert r.status_code == 200
    data = r.json()
    check("12 fixtures tested", data.get("total_fixtures") == 12)
    check("avg score >= 70", data.get("average_score", 0) >= 70)
    check("all fixtures have results", len(data.get("fixtures", [])) == 12)
    # Check DXF comparison field
    for fx in data.get("fixtures", []):
        name = fx.get("name", "")
        if name in ("round_table", "center-table-round-100"):
            check(f"{name} DXF match field present", "dxf_match" in fx)

def test_digitize_with_image():
    print("\n[4/7] Digitize with fixture image")
    img_path = FIXTURES / "center-table-round-100" / "reference.jpg"
    assert img_path.exists(), f"Image not found: {img_path}"
    
    with open(img_path, "rb") as f:
        r = requests.post(
            f"{BASE}/api/digitize",
            files={"file": ("test.jpg", f, "image/jpeg")},
            timeout=120,
        )
    assert r.status_code == 200, f"Status {r.status_code}: {r.text[:200]}"
    data = r.json()
    
    check("has job_id", bool(data.get("job_id")))
    check("has dxf_file", bool(data.get("dxf_file")))
    check("has download path", bool(data.get("download")))
    check("furniture type detected", bool(data.get("furniture", {}).get("type")))
    check("furniture confidence > 0", data.get("furniture", {}).get("confidence", 0) > 0)
    check("has resolved_dimensions", isinstance(data.get("resolved_dimensions"), dict))
    check("component_schema returned", data.get("component_schema") is not None)
    check("accuracy_pipeline returned", data.get("accuracy_pipeline") is not None)
    
    fp = data.get("furniture", {})
    check("missing_dimensions field present", "missing_dimensions" in fp)
    check("needs_confirmation field present", "needs_confirmation" in fp)
    
    ap = data.get("accuracy_pipeline", {})
    check("associations present", ap.get("associations") is not None)
    check("line_roles present", ap.get("line_roles") is not None)
    check("scale present", ap.get("scale") is not None)
    check("reconstruction present", ap.get("reconstruction") is not None)
    
    # Verify DXF was actually created
    dxf_path = Path(tempfile.gettempdir()) / "cad_digitizer_outputs" / data["dxf_file"]
    check("DXF file exists on disk", dxf_path.exists())
    if dxf_path.exists():
        check("DXF file non-empty", dxf_path.stat().st_size > 100)

    return data


def test_digitize_with_explicit_type():
    """Verify the full pipeline works when furniture type is known
    (bypasses OpenCV classifier which has limited synthetic-image detection).
    This validates resolved_dimensions, component_schema, and missing_dimensions."""
    print("\n[4b/7] Digitize with explicit furniture type")
    img_path = FIXTURES / "center-table-round-100" / "reference.jpg"
    with open(img_path, "rb") as f:
        r = requests.post(
            f"{BASE}/api/digitize",
            files={"file": ("test.jpg", f, "image/jpeg")},
            data={"furniture_type": "round_pedestal_table", "real_width_cm": "100"},
            timeout=120,
        )
    assert r.status_code == 200
    data = r.json()
    ft = data.get("furniture", {}).get("type", "")
    check("type equals round_pedestal_table", ft == "round_pedestal_table",
          f"got {ft}")
    rd = data.get("resolved_dimensions")
    check("resolved_dimensions with explicit type", isinstance(rd, dict) and len(rd) > 0,
          f"got {rd}")
    cs = data.get("component_schema")
    check("component_schema with explicit type", cs is not None and len(cs) >= 3,
          f"got {len(cs) if cs else 0} sections")
    check("top_diameter_cm resolved", rd and rd.get("top_diameter_cm", 0) > 0,
          f"got {rd}")
    return data


def test_correction_endpoints(session_id):
    print("\n[5/7] Correction endpoints")
    # Submit dimension correction
    r = requests.post(
        f"{BASE}/api/corrections/submit",
        data={
            "session_id": session_id,
            "dimension_corrections": json.dumps([{
                "ocr_text": "test",
                "original_value_cm": 80,
                "corrected_value_cm": 100,
                "is_locked": True,
            }]),
            "line_role_corrections": json.dumps([{
                "line_id": "line_0",
                "original_role": "UNKNOWN",
                "corrected_role": "OBJECT_EDGE",
            }]),
        },
        timeout=10,
    )
    assert r.status_code == 200
    check("correction submit ok", r.status_code == 200 and r.json().get("corrections_saved", 0) > 0)
    
    # Get corrections
    r = requests.get(f"{BASE}/api/corrections/{session_id}", timeout=10)
    assert r.status_code == 200
    check("correction retrieval ok", r.status_code == 200)

def test_presets():
    print("\n[6/7] Presets endpoint")
    r = requests.get(f"{BASE}/api/presets", timeout=10)
    assert r.status_code == 200
    data = r.json()
    check("presets returned", "presets" in data)
    check("preset count is integer", isinstance(data.get("count"), int))

def test_dxf_download(dxf_file):
    print("\n[7/7] DXF download")
    r = requests.get(f"{BASE}/api/download/{dxf_file}", timeout=10)
    assert r.status_code == 200
    check("DXF download returns file", len(r.content) > 100)
    check("DXF content is ASCII DXF", r.content.startswith(b" ") or b"0\nSECTION" in r.content[:200])


if __name__ == "__main__":
    import json
    import tempfile
    
    print("=" * 50)
    print("E2E Test Suite for CAD Scaler Digitizer")
    print("=" * 50)
    
    test_health()
    test_fixtures_list()
    test_benchmark()
    result = test_digitize_with_image()
    result2 = test_digitize_with_explicit_type()
    session_id = result2.get("job_id", result.get("job_id", "test-session"))
    dxf_file = result2.get("dxf_file", result.get("dxf_file", ""))
    test_correction_endpoints(session_id)
    test_presets()
    if dxf_file:
        test_dxf_download(dxf_file)
    
    print("\n" + "=" * 50)
    print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 50)
    
    if failed > 0:
        sys.exit(1)
