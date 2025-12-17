"""Sample submission for manual testing."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    print(f"Config file: {args.config}")
    print(f"Output directory: {args.output}")

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Simulate some work
    print("Training model...")
    print("Evaluating model...")

    # Output metrics.json (required)
    metrics_path = output_dir / "metrics.json"
    results = {
        "params": {
            "method": "padim",
            "dataset": "mvtec_ad",
            "category": "bottle",
            "backbone": "resnet18",
        },
        "metrics": {
            "image_auc": 0.985,
            "pixel_auc": 0.972,
            "image_f1": 0.934,
            "pixel_f1": 0.887,
        }
    }

    with open(metrics_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to {metrics_path}")
    print("Completed successfully!")

if __name__ == "__main__":
    main()
