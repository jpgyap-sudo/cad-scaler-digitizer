"""Upload Jardan DXF files to Spaces and register in DB."""
import os, sys, hashlib, json
import boto3

# Credentials
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

prefix = "cad-reference-library/"
bucket = "homeatelierspaces"

files = [
    ("/tmp/ARDEN_RANGE.dxf", "raw/jardan/table/arden-range/cad/ARDEN_RANGE.dxf"),
    ("/tmp/LOLA-RANGE.dxf", "raw/jardan/table/lola-range/cad/LOLA-RANGE.dxf"),
    ("/tmp/PIA-RANGE.dxf", "raw/jardan/table/pia-range/cad/PIA-RANGE.dxf"),
]

for local_path, key in files:
    if not os.path.exists(local_path):
        print(f"SKIP: {local_path} not found")
        continue
    space_key = prefix + key
    with open(local_path, "rb") as f:
        buf = f.read()
    s3.put_object(
        Bucket=bucket, Key=space_key, Body=buf, ACL="public-read",
        ContentType="application/dxf",
    )
    sha = hashlib.sha256(buf).hexdigest()
    cdn = f"https://homeatelierspaces.sgp1.cdn.digitaloceanspaces.com/{space_key}"
    print(f"OK: {key} ({len(buf)} bytes)")
    print(f"  CDN: {cdn}")
    print(f"  SHA256: {sha}")
