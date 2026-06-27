"""Audit syntax for all recently changed Python files."""
import py_compile, sys

files = [
    '/app/app/services/crawl_to_dxf.py',
    '/app/app/api/routes.py',
    '/app/app/services/hallucination_verifier.py',
    '/app/app/queue_worker.py',
    '/app/app/services/validation_service.py',
    '/app/app/services/embedding_service.py',
    '/app/app/backend/anti_hallucination_validator.py',
    '/app/app/backend/dimension_validator.py',
    '/app/app/backend/reference_ratio_solver.py',
    '/app/app/backend/reference_confidence_scorer.py',
]

all_ok = True
for path in files:
    try:
        py_compile.compile(path, doraise=True)
        name = path.split("/")[-1]
        print("  PASS  " + name)
    except py_compile.PyCompileError as e:
        print("  FAIL  " + path.split("/")[-1] + ": " + str(e))
        all_ok = False

sys.exit(0 if all_ok else 1)
