"""
Save the 5 generated DXF files as reference files for product improvement.
Uploads each to Spaces, creates a product reference record, and stores
the comparison data for iteration tracking.
"""
import os, json, hashlib, glob
from datetime import datetime

OUTPUT_DIR = "/tmp/cad_digitizer_outputs"
PREFIX = "cad-reference-library/references/"

# Map product URLs to their metadata
PRODUCTS = {
    "tangerie-dining-table": {
        "name": "Tangerie Dining Table",
        "url": "https://homeu.ph/products/tangerie-dining-table",
        "category": "dining-table",
        "dimensions": {"width_cm": 100, "height_cm": 75},
    },
    "glenn-modern-sofa": {
        "name": "Glenn Modern Sofa",
        "url": "https://homeu.ph/products/glenn-modern-sofa",
        "category": "sofa",
        "dimensions": {"width_cm": 250, "height_cm": 82},
    },
    "evon-modern-bed": {
        "name": "Evon Modern Bed",
        "url": "https://homeu.ph/products/evon-modern-bed",
        "category": "bed",
        "dimensions": {"width_cm": 150},
    },
    "aeris-console-table": {
        "name": "Aeris Console Table",
        "url": "https://homeu.ph/products/aeris-console-table",
        "category": "table",
        "dimensions": {},
    },
    "bruno-modern-dining-chair": {
        "name": "Bruno Dining Chair",
        "url": "https://homeu.ph/products/bruno-modern-dining-chair",
        "category": "chair",
        "dimensions": {"width_cm": 63, "height_cm": 48},
    },
}

def main():
    # Find the most recent DXF files (one per product, last 10 minutes)
    recent_cutoff = datetime.now().timestamp() - 600  # 10 min ago
    dxf_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*_digitized.dxf")), key=os.path.getmtime, reverse=True)

    # Upload each DXF to Spaces as a reference
    try:
        import boto3
        s3 = boto3.client(
            "s3",
            endpoint_url="https://sgp1.digitaloceanspaces.com",
            region_name="sgp1",
            aws_access_key_id="DO00M6AC44YMBXXVA92U",
            aws_secret_access_key="OOXgoRMlb4iqpNWQW8kjQxyqgxsgOlQeWc59c1gDT1I",
            config=boto3.session.Config(signature_version="s3v4"),
        )
    except ImportError:
        print("boto3 not available, saving locally only")
        s3 = None

    processed = 0
    for dxf_path in dxf_files:
        mtime = os.path.getmtime(dxf_path)
        if mtime < recent_cutoff:
            break  # older files

        basename = os.path.basename(dxf_path)
        job_id = basename.replace("_digitized.dxf", "")

        # Find matching product
        slug = None
        for key in PRODUCTS:
            if key in basename or any(key in p["name"].lower() for p in [PRODUCTS[key]]):
                slug = key
                break

        if not slug:
            # Use the most recent product from our list
            slug = list(PRODUCTS.keys())[processed] if processed < len(PRODUCTS) else None
            if not slug:
                continue

        product = PRODUCTS[slug]

        # Try to find corresponding JSON with detected geometry
        json_path = dxf_path.replace("_digitized.dxf", "_digitized.json")
        geo_data = None
        if os.path.exists(json_path):
            with open(json_path) as f:
                geo_data = json.load(f)

        # Upload to Spaces
        space_key = f"{PREFIX}{slug}/{basename}"
        cdn_url = None
        if s3:
            try:
                with open(dxf_path, "rb") as f:
                    buf = f.read()
                s3.put_object(Bucket="homeatelierspaces", Key=space_key, Body=buf, ACL="public-read")
                cdn_url = f"https://homeatelierspaces.sgp1.cdn.digitaloceanspaces.com/{space_key}"
                print(f"Uploaded {basename} -> {cdn_url}")
            except Exception as e:
                print(f"S3 upload failed: {e}")
        else:
            print(f"Local only: {basename}")

        # Try to create a product reference via Node API
        try:
            import httpx
            api_base = "http://node-api:4000"
            r = httpx.post(
                f"{api_base}/api/product-references",
                json={
                    "manufacturer": "homeu",
                    "productName": product["name"],
                    "category": product["category"],
                    "sourceUrl": product["url"],
                    "metadata": {
                        "type": "reference_digitization",
                        "job_id": job_id,
                        "page_dimensions": product["dimensions"],
                        "has_cdn": cdn_url is not None,
                        "created_at": datetime.utcnow().isoformat(),
                    },
                },
                timeout=10,
            )
            if r.status_code in (200, 201):
                print(f"  -> Product reference created: {r.json().get('id', 'ok')}")
            else:
                print(f"  -> API response: {r.status_code} {r.text[:100]}")
        except Exception as e:
            print(f"  -> API error: {e}")

        processed += 1

    print(f"\nSaved {processed} reference DXF files")

if __name__ == "__main__":
    main()
