"""Render a notebook's Mermaid diagrams to PNG: black background, 2x scale, the shared dark theme.

Each diagram lives in a markdown cell next to its image, followed by its source:
    ![alt](img/<name>.png)  or  <img src="img/<name>.png" alt="..." width="N">
    <details><summary>Mermaid source</summary> ```mermaid ... ``` </details>
so the notebook keeps the source and shows the picture (VS Code renders the PNG; it has no Mermaid).

Notebooks show a PNG at its pixel width, so a 2x render of a narrow diagram appears twice too large. For
<img> tags, rendering also sets width="N" to half the PNG's width: every diagram then shows at 1x and stays
sharp on high-density screens.

    python tools/diagrams/render.py path/to/notebook.ipynb            # every diagram in the notebook
    python tools/diagrams/render.py path/to/notebook.ipynb name ...   # only these img/<name>.png
"""
import json
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MMDC = next(Path.home().glob(".npm/_npx/*/node_modules/.bin/mmdc"), None)
IMAGE = re.compile(r'\]\(img/([\w-]+)\.png\)|<img src="img/([\w-]+)\.png"')
IMG_WIDTH = re.compile(r'(<img src="img/([\w-]+)\.png"[^>]*?width=")\d+(")')


def diagrams(notebook: Path) -> dict[str, str]:
    found = {}
    for cell in json.loads(notebook.read_text())["cells"]:
        text = "".join(cell["source"])
        for image in IMAGE.finditer(text):     # each image takes the next Mermaid block
            block = re.compile(r"```mermaid\n(.*?)```", re.S).search(text, image.end())
            if block:
                found[image.group(1) or image.group(2)] = block.group(1)
    return found


def png_width(path: Path) -> int:
    return struct.unpack(">I", path.read_bytes()[16:20])[0]


def set_widths(notebook: Path) -> None:
    """Give each <img> half the pixel width of its PNG."""
    raw = notebook.read_text()
    nb = json.loads(raw)
    widths = {p.stem: png_width(p) // 2 for p in (notebook.parent / "img").glob("*.png")}
    for cell in nb["cells"]:
        text = "".join(cell["source"])
        new = IMG_WIDTH.sub(lambda m: f"{m.group(1)}{widths.get(m.group(2), 600)}{m.group(3)}", text)
        if new != text:
            cell["source"] = new.splitlines(keepends=True)
    out = json.dumps(nb, indent=1, ensure_ascii=False) + "\n"
    if out != raw:
        notebook.write_text(out)
        print("image widths updated")


def render(notebook: Path, names: list[str]) -> None:
    if MMDC is None:
        raise SystemExit("mmdc not found: run `npx -y @mermaid-js/mermaid-cli --version` once")
    found = diagrams(notebook)
    out_dir = notebook.parent / "img"
    out_dir.mkdir(exist_ok=True)
    for name in names or sorted(found):
        if name not in found:
            print(f"{name}: no Mermaid source next to img/{name}.png")
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".mmd", delete=False) as src:
            src.write(found[name])
        png = out_dir / f"{name}.png"
        r = subprocess.run([str(MMDC), "-i", src.name, "-o", str(png), "-c", str(HERE / "theme.json"),
                            "-b", "#000000", "-s", "2", "-w", "1200", "-q"], capture_output=True, text=True)
        print(f"{name}: " + (f"FAILED {r.stderr[-500:]}" if r.returncode else f"ok ({png.stat().st_size // 1024} KB)"))
    set_widths(notebook)


if __name__ == "__main__":
    render(Path(sys.argv[1]).resolve(), sys.argv[2:])
