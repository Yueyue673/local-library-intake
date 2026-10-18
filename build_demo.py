"""Create original synthetic book fixtures and a reproducible example delivery."""
from pathlib import Path
import argparse
from test_intake import make_epub
from intake import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_root", type=Path, nargs="?", default=Path("demo-run"))
    args = parser.parse_args()
    if args.output_root.exists():
        parser.exit(2, "Choose a new demo directory; nothing was changed.\n")
    source = args.output_root / "input"
    source.mkdir(parents=True, exist_ok=False)
    (source / "workshop.txt").write_text("Original synthetic workshop note.\nMeasure, mark, and check the drawing before use.\n", encoding="utf-8")
    (source / "recipe.md").write_text("# Original synthetic kitchen note\nStore dry ingredients in a labeled container.\n", encoding="utf-8")
    make_epub(source / "garden.epub")
    run(source, args.output_root / "delivery")
