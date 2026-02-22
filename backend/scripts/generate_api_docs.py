#!/usr/bin/env python3
"""
Generate standalone HTML API documentation from OpenAPI spec.
Uses Redoc for rendering.
"""

import json
from pathlib import Path

import yaml


def load_openapi_spec(spec_path: Path) -> dict:
    """Load OpenAPI specification from YAML file."""
    with open(spec_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_html(spec: dict, output_path: Path) -> None:
    """Generate standalone HTML documentation using Redoc."""
    spec_json = json.dumps(spec, indent=2)

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{spec.get("info", {}).get("title", "API Documentation")}</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
        }}
    </style>
</head>
<body>
    <redoc spec-url='#'></redoc>
    <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
    <script>
        const spec = {spec_json};
        Redoc.init(spec, {{}}, document.querySelector('redoc'));
    </script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_template)

    print(f"✓ API documentation generated: {output_path}")
    print(f"  Open in browser: file://{output_path.absolute()}")


def main() -> None:
    """Main entry point."""
    backend_dir = Path(__file__).parent.parent
    spec_path = backend_dir / "openapi.yaml"
    output_path = backend_dir / "docs" / "api.html"

    if not spec_path.exists():
        raise FileNotFoundError(f"OpenAPI spec not found: {spec_path}")

    print(f"Loading OpenAPI spec from: {spec_path}")
    spec = load_openapi_spec(spec_path)

    print("Generating HTML documentation...")
    generate_html(spec, output_path)


if __name__ == "__main__":
    main()
