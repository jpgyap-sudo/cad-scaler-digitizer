"""Append product search endpoints to routes.py."""
import os

# Fix: go up one level from scripts/ to backend-python/
HERE = os.path.dirname(os.path.abspath(__file__))
ROUTES = os.path.join(HERE, '..', 'app', 'api', 'routes.py')

with open(ROUTES, 'r', encoding='utf-8') as f:
    content = f.read()

if '/products/search' in content:
    print('ALREADY EXISTS - skipping')
else:
    addition = r'''

# ---------------------------------------------------------------------------
# Product Catalog Search API (259 Shopify templates)
# ---------------------------------------------------------------------------

@router.get("/products/search")
async def products_search(
    q: Optional[str] = None,
    shape: Optional[str] = None,
    base: Optional[str] = None,
    leg: Optional[str] = None,
    category: Optional[str] = None,
    text: Optional[str] = None,
    top_k: int = 5,
):
    """Search 259 product templates by visual DNA and/or text."""
    try:
        from app.backend.product_search import search_combined
        params = {}
        if q: params["text"] = q
        if shape: params["shape"] = shape
        if base: params["base"] = base
        if leg: params["leg"] = leg
        if category: params["category"] = category
        if text: params["text"] = text
        if params:
            result = search_combined(params, top_k=top_k)
        else:
            from app.backend.product_search import catalog_stats
            result = catalog_stats()
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


@router.get("/products/search/similar")
async def products_search_similar(template_id: str, top_k: int = 5):
    """Find products visually similar to a template."""
    try:
        from app.backend.product_search import get_similar
        results = get_similar(template_id, top_k=top_k)
        return JSONResponse({"results": results, "total": len(results), "query": template_id})
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


@router.get("/products/search/semantic")
async def products_search_semantic(q: str, top_k: int = 5):
    """Semantic search via Qdrant."""
    try:
        from app.backend.product_search import search_semantic
        results = search_semantic(q, top_k=top_k)
        return JSONResponse({"results": results, "total": len(results), "mode": "semantic" if results else "fallback"})
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


@router.post("/products/learn")
async def products_learn(payload: dict):
    """Save confirmed product match to local storage + Qdrant."""
    try:
        from app.backend.product_search import learn_product
        td = payload.get("template_data", {})
        corrections = payload.get("corrections")
        if not td:
            return JSONResponse({"error": "template_data is required"}, status_code=400)
        result = learn_product(td, corrections)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


@router.get("/products/catalog")
async def products_catalog():
    """Catalog statistics."""
    try:
        from app.backend.product_search import catalog_stats
        return JSONResponse(catalog_stats())
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


@router.get("/products/family/{family_name}")
async def products_family(family_name: str):
    """Visual DNA for a template family."""
    try:
        from app.backend.product_search import get_family_visual_dna, load_catalog
        dna = get_family_visual_dna(family_name)
        if not dna:
            return JSONResponse({"error": f"Family '{family_name}' not found"}, status_code=404)
        catalog = load_catalog()
        members = [e for e in catalog["registry"] if e.get("template_family") == family_name]
        return JSONResponse({"family": family_name, "visual_dna": dna, "members": members, "count": len(members)})
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)
'''

    with open(ROUTES, 'a', encoding='utf-8') as f:
        f.write(addition)
    print(f'OK - appended routes to {ROUTES}')
