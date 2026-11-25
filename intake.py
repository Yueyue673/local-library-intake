"""Small offline TXT/Markdown/EPUB intake demo. Python 3.10+, standard library."""

import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import posixpath
import re
from urllib.parse import unquote
import xml.etree.ElementTree as ET
import zipfile

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 100 * 1024 * 1024
MAX_FILES = 100
MAX_EPUB_EXPANDED = 100 * 1024 * 1024


class PlainText(HTMLParser):
    """Read text without executing markup or fetching any linked resources."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "head"}:
            self.hidden += 1
        if not self.hidden and tag in {"p", "div", "br", "h1", "h2", "h3", "li", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "head"} and self.hidden:
            self.hidden -= 1
        if not self.hidden and tag in {"p", "div", "h1", "h2", "h3", "li", "section"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

    def text(self):
        lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in "".join(self.parts).split("\n")]
        return "\n".join(line for line in lines if line)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def member_path(base, href):
    name = posixpath.normpath(posixpath.join(base, unquote(href.split("#", 1)[0])))
    if not name or name == ".." or name.startswith(("../", "/")) or "\\" in name or ":" in name:
        raise ValueError("invalid EPUB member path")
    return name


def epub_text(path):
    with zipfile.ZipFile(path) as book:
        entries = book.infolist()
        if len(entries) > 5000 or sum(item.file_size for item in entries) > MAX_EPUB_EXPANDED:
            raise ValueError("EPUB expanded size or member count exceeds demo limit")
        if len({item.filename for item in entries}) != len(entries):
            raise ValueError("EPUB contains duplicate member names")
        if any(item.flag_bits & 1 for item in entries):
            raise ValueError("encrypted EPUB is unsupported")
        if "META-INF/encryption.xml" in book.namelist():
            raise ValueError("EPUB encryption needs separate assessment")
        container = ET.fromstring(book.read("META-INF/container.xml"))
        rootfile = container.find(".//{*}rootfile")
        if rootfile is None:
            raise ValueError("EPUB has no package file")
        package_path = member_path("", rootfile.attrib["full-path"])
        package = ET.fromstring(book.read(package_path))
        manifest = {item.attrib["id"]: item for item in package.findall("./{*}manifest/{*}item")}
        chapters = []
        for ref in package.findall("./{*}spine/{*}itemref"):
            if ref.attrib.get("linear") == "no":
                continue
            item = manifest.get(ref.attrib.get("idref"))
            if item is None:
                raise ValueError("EPUB spine references a missing manifest item")
            if item.attrib.get("media-type") not in {"application/xhtml+xml", "text/html"}:
                raise ValueError("unsupported EPUB spine media type")
            chapter_path = member_path(posixpath.dirname(package_path), item.attrib["href"])
            # Let the XML declaration select the text encoding for XHTML.
            chapter = ET.fromstring(book.read(chapter_path))
            # Strip namespace prefixes generically before sending well-formed XML to HTMLParser.
            parser = PlainText()
            for node in chapter.iter():
                if isinstance(node.tag, str):
                    node.tag = node.tag.rsplit("}", 1)[-1]
            parser.feed(ET.tostring(chapter, encoding="unicode"))
            text = parser.text()
            if text:
                chapters.append(text)
        if not chapters:
            raise ValueError("EPUB has no readable linear chapters")
        return "\n\n".join(chapters) + "\n"


def input_files(root):
    files = []
    for folder, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names:
            path = Path(folder) / name
            if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                raise ValueError("linked files and folders are unsupported")
        files.extend(Path(folder) / name for name in names)
    files.sort(key=lambda path: path.relative_to(root).as_posix())
    if len(files) > MAX_FILES or sum(path.stat().st_size for path in files) > MAX_TOTAL_BYTES:
        raise ValueError("demo input limit: 100 files / 100 MiB total")
    if any(not path.is_file() or path.stat().st_size > MAX_FILE_BYTES for path in files):
        raise ValueError("demo input limit: regular files up to 20 MiB each")
    return files


OVERVIEW_STYLE = """\
:root {
  color-scheme: light;
  --paper: #f7f5ef;
  --ink: #243d34;
  --muted: #61746a;
  --line: #dce2d7;
  --green: #315e4b;
  --err: #a03535;
}
* { box-sizing: border-box; }
html { background: var(--paper); }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font: 17px/1.75 "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans SC", "Source Han Sans SC", "WenQuanYi Micro Hei", "Droid Sans Fallback", system-ui, sans-serif;
}
main {
  max-width: 40rem;
  margin: 0 auto;
  padding: 5rem 1.5rem 4.5rem;
}
h1 {
  margin: 0;
  font-size: 1.65rem;
  font-weight: 500;
  letter-spacing: 0.02em;
  line-height: 1.4;
}
.lead {
  margin: 0.85rem 0 2.4rem;
  color: var(--muted);
}
a {
  color: var(--green);
  text-decoration-thickness: 1px;
  text-underline-offset: 0.22em;
}
a:hover { color: var(--ink); }
a:focus-visible { outline: 2px solid var(--green); outline-offset: 3px; }
table {
  width: max-content;
  max-width: 100%;
  border-collapse: collapse;
  font-size: 1rem;
  line-height: 1.5;
}
th, td { text-align: left; vertical-align: baseline; }
th {
  padding: 0 2.25rem 0.5rem 0;
  border-bottom: 1px solid var(--ink);
  color: var(--muted);
  font-size: 0.82rem;
  font-weight: 500;
}
td {
  padding: 0.8rem 2.25rem 0.8rem 0;
  border-bottom: 1px solid var(--line);
}
td:first-child { overflow-wrap: anywhere; max-width: 16rem; }
td:nth-child(2) { white-space: nowrap; }
td:nth-child(3) { overflow-wrap: anywhere; max-width: 16rem; }
th:last-child, td:last-child { padding-right: 0; }
.err { color: var(--err); }
.foot {
  margin: 2.15rem 0 0;
  color: var(--muted);
  font-size: 0.88rem;
  line-height: 1.7;
}
@media (max-width: 640px) {
  main { padding: 2.5rem 1.15rem 3rem; }
  th, td { padding-right: 1rem; }
}
@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --paper: #17231f;
    --ink: #e0e8dc;
    --muted: #b0bfae;
    --line: #3b4b3f;
    --green: #85b59a;
    --err: #ffb8b0;
  }
}
"""

OVERVIEW_NOTE = (
    "只收 UTF-8 的 TXT、Markdown，以及没加密的文字 EPUB。Markdown 还是原文。"
    "PDF、扫描识别、带锁的书、按内容归类和 CAD 没有处理。不联网，也没有额外安装的包。"
)


def overview_page(records):
    """Local file record. Labels only; file status values stay in the manifest."""
    labels = {"converted": "已抽出文字", "unsupported": "格式不支持", "error": "出错"}
    rows = []
    for row in records:
        if "text" in row:
            output = f'<a href="{html.escape(row["text"], quote=True)}">打开文本</a>'
        else:
            output = html.escape(row.get("reason", ""))
        label = labels.get(row["status"], row["status"])
        mark = ' class="err"' if row["status"] == "error" else ""
        rows.append(
            "    <tr>\n"
            f"      <td>{html.escape(row['source'])}</td>\n"
            f"      <td{mark}>{html.escape(label)}</td>\n"
            f"      <td>{output}</td>\n"
            "    </tr>"
        )
    if records:
        lead = (
            f"这一批一共 {len(records)} 个文件。原件按字节原样复制，"
            '哈希在<a href="manifest.json">清单</a>里。'
        )
        table = (
            "<table>\n"
            "<thead>\n"
            "<tr><th>原文件</th><th>情况</th><th>文本</th></tr>\n"
            "</thead>\n"
            "<tbody>\n"
            + "\n".join(rows)
            + "\n</tbody>\n</table>\n"
        )
    else:
        lead = '这一批没有文件。清单在<a href="manifest.json">这里</a>。'
        table = ""
    parts = [
        "<!doctype html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>文件收件记录</title>",
        "<style>",
        OVERVIEW_STYLE.rstrip("\n"),
        "</style>",
        "</head>",
        "<body>",
        "<main>",
        "<h1>文件收件记录</h1>",
        f'<p class="lead">{lead}</p>',
    ]
    if table:
        parts.append(table.rstrip("\n"))
    parts.extend([
        f'<p class="foot">{OVERVIEW_NOTE}</p>',
        "</main>",
        "</body>",
        "</html>",
        "",
    ])
    return "\n".join(parts)


def run(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_dir():
        raise ValueError("input must be an existing directory")
    if destination == source or source in destination.parents or destination in source.parents:
        raise ValueError("input and output must be separate, non-nested directories")
    if destination.exists():
        raise ValueError("output already exists; choose a new output directory")
    files = input_files(source)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "originals").mkdir()
    (destination / "text").mkdir()
    records = []
    for number, path in enumerate(files, 1):
        label = f"{number:04d}-" + re.sub(r"[^\w. -]", "_", path.name)[:110]
        archive = destination / "originals" / label
        row = {"source": path.relative_to(source).as_posix(), "archive": archive.relative_to(destination).as_posix()}
        records.append(row)
        try:
            with path.open("rb") as handle:
                raw = handle.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES:
                raise ValueError("file grew past the 20 MiB limit")
            archive.write_bytes(raw)
            row.update(source_sha256=digest(raw), archived_sha256=digest(archive.read_bytes()), bytes=len(raw))
            if row["source_sha256"] != row["archived_sha256"]:
                raise OSError("archive verification failed")
            suffix = path.suffix.lower()
            if suffix in {".txt", ".md"}:
                text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
                if "\x00" in text:
                    raise ValueError("input contains binary NUL characters")
            elif suffix == ".epub":
                text = epub_text(archive)
            else:
                row.update(status="unsupported", reason="demo supports UTF-8 TXT/Markdown and unencrypted text EPUB")
                continue
            if not text.strip():
                raise ValueError("no readable text found")
            target = destination / "text" / (label + ".txt")
            target.write_text(text, encoding="utf-8", newline="\n")
            row.update(status="converted", text=target.relative_to(destination).as_posix(), text_sha256=digest(target.read_bytes()))
        except (OSError, ValueError, KeyError, ET.ParseError, zipfile.BadZipFile, NotImplementedError, RuntimeError) as exc:
            row.update(status="error", reason=str(exc))
    (destination / "manifest.json").write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (destination / "index.html").write_text(overview_page(records), encoding="utf-8")
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    try:
        result = run(arguments.source, arguments.destination)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(json.dumps({status: sum(row["status"] == status for row in result) for status in ("converted", "unsupported", "error")}))
    raise SystemExit(1 if any(row["status"] == "error" for row in result) else 0)
