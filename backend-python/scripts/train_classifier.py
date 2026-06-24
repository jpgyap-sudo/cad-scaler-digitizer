"""
Train initial furniture classifier (simple MLP baseline).
Creates models/furniture_classifier.onnx for /api/ml/predict.
"""
import sys, os, json, numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
MODELS_DIR = Path(__file__).parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

# Generate synthetic training data (384-dim embeddings for 10 classes)
CLASSES = [
    "round_pedestal_table", "rectangular_table", "sofa", "cabinet",
    "bed_headboard", "chair", "coffee_table", "dining_chair",
    "wardrobe", "reception_counter"
]
N_SAMPLES = 200
N_FEATURES = 384

np.random.seed(42)
X = np.random.randn(N_SAMPLES * len(CLASSES), N_FEATURES).astype(np.float32)
y = np.repeat(np.arange(len(CLASSES)), N_SAMPLES)

# Simple MLP with sklearn
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

clf = MLPClassifier(
    hidden_layer_sizes=(256, 128),
    activation='relu',
    max_iter=200,
    random_state=42,
    verbose=False
)
clf.fit(X_train, y_train)

y_pred = clf.predict(X_test)
acc = accuracy_score(y_test, y_pred)
print(f"Accuracy: {acc:.4f}")
print(classification_report(y_test, y_pred, target_names=CLASSES))

# Convert to ONNX
try:
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType

    initial_type = [('float_input', FloatTensorType([None, N_FEATURES]))]
    onx = convert_sklearn(clf, initial_types=initial_type)
    onnx_path = MODELS_DIR / "furniture_classifier.onnx"
    with open(onnx_path, "wb") as f:
        f.write(onx.SerializeToString())
    print(f"ONNX model saved: {onnx_path} ({onnx_path.stat().st_size} bytes)")

    # Update registry
    registry_path = MODELS_DIR / "registry.json"
    registry = {"models": [], "active": {}}
    if registry_path.exists():
        registry = json.loads(registry_path.read_text())
    registry["active"]["furniture_classifier"] = len(registry["models"]) + 1
    registry["models"].append({
        "version": len(registry["models"]) + 1,
        "type": "furniture_classifier",
        "path": str(onnx_path),
        "accuracy": float(acc),
        "samples": N_SAMPLES * len(CLASSES),
        "trained_at": __import__('datetime').datetime.utcnow().isoformat()
    })
    registry_path.write_text(json.dumps(registry, indent=2))
    print(f"Registry updated: {len(registry['models'])} models tracked")
except ImportError:
    print("skl2onnx not installed. ONNX export skipped.")
    print("Install: pip install skl2onnx onnxruntime")

print("Training complete!")
