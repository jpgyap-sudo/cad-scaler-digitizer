"""
PDF Dimension Extractor — extracts product dimensions from spec sheet PDFs.
Uses the S3 API (not HTTP CDN) to avoid rate limiting.
Downloads each PDF, extracts text, finds dimensions, stores in Postgres.
"""
import os, re, json, io, tempfile
import boto3
from pypdf import PdfReader

AWS_KEY = "DO00M6AC44YMBXXVA92U"
AWS_SECRET = "OOXgoRMlb4iqpNWQW8kjQxyqgxsgOlQeWc59c1gDT1I"

s3 = boto3.client(
    "s3",
    endpoint_url="https://sgp1.digitaloceanspaces.com",
    region_name="sgp1",
    aws_access_key_id=AWS_KEY,
    aws_secret_access_key=AWS_SECRET,
    config=boto3.session.Config(signature_version="s3v4"),
)

bucket = "homeatelierspaces"
prefix = "cad-reference-library/raw/jardan/"

# --- Dimension extraction patterns ---

def extract_dimensions(text):
    """Extract product dimensions from PDF text."""
    dims = {}

    # Pattern 1: "W: 218cm  H: 86cm  D: 75cm" or "W 218cm, H 86cm, D 75cm"
    patterns = [
        (r"(?:W|Width|width)[:\s]*(\d+[\.]?\d*)\s*(?:cm|mm)?", "width_cm"),
        (r"(?:H|Height|height)[:\s]*(\d+[\.]?\d*)\s*(?:cm|mm)?", "height_cm"),
        (r"(?:D|Depth|depth)[:\s]*(\d+[\.]?\d*)\s*(?:cm|mm)?", "depth_cm"),
        (r"(?:L|Length|length)[:\s]*(\d+[\.]?\d*)\s*(?:cm|mm)?", "length_cm"),
    ]

    for pattern, key in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            val = float(match.group(1))
            # Convert mm to cm if needed
            unit_match = re.search(rf"{pattern}[^\d]*?(cm|mm)", text[:match.end() + 10], re.I)
            if unit_match and unit_match.group(1) == "mm":
                val /= 10
            dims[key] = round(val, 1)

    # Pattern 2: "200 x 300cm" (W x H or W x L)
    wxh = re.findall(r"(\d+[\.]?\d*)\s*x\s*(\d+[\.]?\d*)\s*(?:cm|mm)?", text, re.I)
    if len(wxh) >= 1:
        if "width_cm" not in dims:
            dims["width_cm"] = float(wxh[0][0])
        if "height_cm" not in dims and "length_cm" not in dims:
            dims["height_cm"] = float(wxh[0][1])

    # Pattern 3: "Available in 200 x 300cm, 250 x 350cm"
    sizes = re.findall(r"(\d+[\.]?\d*)\s*x\s*(\d+[\.]?\d*)\s*(?:cm|mm)", text, re.I)
    if sizes and ("width_cm" not in dims or "height_cm" not in dims):
        dims["sizes_available"] = [f"{w}x{h}" for w, h in sizes]

    return dims


def extract_from_pdf(s3_key):
    """Download PDF from Spaces and extract dimensions."""
    try:
        obj = s3.get_object(Bucket=bucket, Key=s3_key)
        pdf_bytes = obj["Body"].read()
        reader = PdfReader(io.BytesIO(pdf_bytes))
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
        return extract_dimensions(full_text), full_text[:500]
    except Exception as e:
        return {"error": str(e)}, ""


def main():
    # List all PDFs in Spaces
    print("Scanning for PDF spec sheets...")
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    pdfs = [obj["Key"] for obj in resp.get("Contents", []) 
            if obj["Key"].lower().endswith(".pdf")]
    print(f"Found {len(pdfs)} PDF files")

    results = []
    for pdf_key in pdfs:
        # Extract product name from key path
        parts = pdf_key.split("/")
        product_name = parts[4] if len(parts) > 4 else "unknown"
        category = parts[3] if len(parts) > 3 else "unknown"
        filename = parts[-1]

        print(f"  Processing: {product_name}/{filename}...", end=" ")
        dims, preview = extract_from_pdf(pdf_key)
        if dims and not dims.get("error"):
            keys = [k for k in dims.keys() if k != "sizes_available"]
            if keys:
                dim_str = ", ".join(f"{k}={v}cm" for k, v in dims.items() if k != "sizes_available")
                sizes = dims.get("sizes_available", [])
                size_str = f" [{', '.join(sizes[:3])}]" if sizes else ""
                print(f"EXTRACTED: {dim_str}{size_str}")
                results.append({
                    "product": product_name,
                    "category": category,
                    "filename": filename,
                    "dimensions": {k: v for k, v in dims.items() if k != "sizes_available"},
                    "sizes": dims.get("sizes_available", []),
                    "s3_key": pdf_key,
                })
            else:
                print("no dimensions found")
        else:
            err = dims.get("error", "unknown")
            print(f"error: {err[:60]}")

    # Summary
    print(f"\n=== SUMMARY ===")
    print(f"Total PDFs: {len(pdfs)}")
    print(f"Dimensions extracted: {len(results)}")
    for r in results[:15]:
        print(f"  {r['product']}: {r['dimensions']}")

    # Save results to JSON for the Node API to consume
    output = json.dumps(results, indent=2)
    with open("/tmp/extracted-dimensions.json", "w") as f:
        f.write(output)
    print(f"\nSaved to /tmp/extracted-dimensions.json ({len(results)} products)")


if __name__ == "__main__":
    main()
