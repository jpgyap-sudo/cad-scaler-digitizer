"""
Scrape furniture images from homeu.ph and international brands for ML training.
Collects labeled images organized by furniture type.
"""
import os, sys, json, hashlib, time, requests
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).parent.parent))
DATASET_DIR = Path(__file__).parent.parent / "training_data"
DATASET_DIR.mkdir(exist_ok=True)

FURNITURE_TYPES = [
    "round_pedestal_table", "rectangular_table", "sofa", "cabinet",
    "bed_headboard", "chair", "coffee_table", "dining_chair",
    "wardrobe", "reception_counter"
]

SOURCES = [
    {
        "name": "homeu.ph",
        "base_url": "https://homeu.ph",
        "categories": {
            "sofa": "/collections/sofa",
            "cabinet": "/collections/cabinet",
            "bed_headboard": "/collections/bed",
            "chair": "/collections/chair",
            "coffee_table": "/collections/table",
            "dining_chair": "/collections/dining-chair",
            "wardrobe": "/collections/wardrobe",
        }
    }
]


def download_image(url, save_path, timeout=15):
    """Download image from URL to local path."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 200 and len(r.content) > 1000:
            save_path.write_bytes(r.content)
            return True
    except Exception as e:
        print(f"  Download failed: {e}")
    return False


def scrape_homeu():
    """Scrape furniture images from homeu.ph."""
    base = "https://homeu.ph"
    count = 0

    for ftype, path in SOURCES[0]["categories"].items():
        type_dir = DATASET_DIR / ftype
        type_dir.mkdir(exist_ok=True)
        url = urljoin(base, path)

        print(f"\nScraping {ftype} from {url}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                print(f"  Failed: HTTP {r.status_code}")
                continue

            # Extract image URLs from HTML
            import re
            img_urls = re.findall(r'https://[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*', r.text)
            img_urls = list(set(img_urls))[:30]  # Max 30 per category

            for i, img_url in enumerate(img_urls):
                img_hash = hashlib.md5(img_url.encode()).hexdigest()[:12]
                save_path = type_dir / f"{img_hash}.jpg"
                if save_path.exists():
                    continue
                if download_image(img_url, save_path):
                    count += 1
                    print(f"  [{count}] Downloaded {ftype}/{img_hash}.jpg")
                time.sleep(0.5)  # Be polite
        except Exception as e:
            print(f"  Error: {e}")

    return count


def scrape_minotti():
    """Scrape from Minotti (international high-end brand)."""
    base = "https://www.minotti.com"
    categories = {
        "sofa": "https://www.minotti.com/en/products/sofas/",
        "coffee_table": "https://www.minotti.com/en/products/tables/",
        "cabinet": "https://www.minotti.com/en/products/storage-units/",
        "bed_headboard": "https://www.minotti.com/en/products/beds/",
        "chair": "https://www.minotti.com/en/products/chairs/",
    }
    count = 0
    for ftype, url in categories.items():
        type_dir = DATASET_DIR / ftype
        type_dir.mkdir(exist_ok=True)
        print(f"\nScraping {ftype} from {url}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                print(f"  Failed: HTTP {r.status_code}")
                continue
            import re
            img_urls = re.findall(r'https://[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*', r.text)
            img_urls = list(set(img_urls))[:30]
            for i, img_url in enumerate(img_urls):
                img_hash = hashlib.md5(img_url.encode()).hexdigest()[:12]
                save_path = type_dir / f"{img_hash}.jpg"
                if save_path.exists():
                    continue
                if download_image(img_url, save_path):
                    count += 1
                    print(f"  [{count}] Downloaded {ftype}/{img_hash}.jpg")
                time.sleep(1)
        except Exception as e:
            print(f"  Error: {e}")
    return count


def build_dataset_manifest():
    """Build training manifest from downloaded images."""
    manifest = []
    for ftype in FURNITURE_TYPES:
        type_dir = DATASET_DIR / ftype
        if not type_dir.exists():
            continue
        for img_path in type_dir.glob("*.[jJ][pP][gG]"):
            manifest.append({"path": str(img_path), "label": ftype, "label_id": FURNITURE_TYPES.index(ftype)})
        for img_path in type_dir.glob("*.[pP][nN][gG]"):
            manifest.append({"path": str(img_path), "label": ftype, "label_id": FURNITURE_TYPES.index(ftype)})
        for img_path in type_dir.glob("*.[wW][eE][bB][pP]"):
            manifest.append({"path": str(img_path), "label": ftype, "label_id": FURNITURE_TYPES.index(ftype)})

    manifest_path = DATASET_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\nDataset manifest: {len(manifest)} images across {len(set(m['label'] for m in manifest))} categories")
    return manifest


if __name__ == "__main__":
    print("=" * 60)
    print("Furniture Image Scraper for ML Training")
    print("=" * 60)

    total = 0
    print("\n--- Scraping homeu.ph ---")
    total += scrape_homeu()

    print("\n--- Scraping Minotti ---")
    total += scrape_minotti()

    print(f"\nTotal images downloaded: {total}")
    manifest = build_dataset_manifest()

    print("\nDataset summary:")
    from collections import Counter
    labels = [m["label"] for m in manifest]
    for label, count in sorted(Counter(labels).items()):
        print(f"  {label}: {count} images")
    print(f"\nTotal: {len(manifest)} images")

    if len(manifest) >= 50:
        print("\n✅ Enough data collected for initial ML training!")
        print("Run: python scripts/train_classifier.py")
    else:
        print(f"\n⚠️ Only {len(manifest)} images. Need at least 50 for meaningful training.")
