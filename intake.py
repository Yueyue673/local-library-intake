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
    rows = []
    for row in records:
        output = f'<a href="{html.escape(row["text"], quote=True)}">Read text</a>' if "text" in row else html.escape(row.get("reason", ""))
        rows.append(f'<tr><td>{html.escape(row["source"])}</td><td>{html.escape(row["status"])}</td><td>{output}</td></tr>')
    page = '<!doctype html><meta charset="utf-8"><title>Local library intake</title>'
    page += '<style>body{font:17px system-ui;max-width:1000px;margin:48px auto;padding:0 24px;color:#192b38}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:16px;border-bottom:1px solid #ddd}a{color:#075fb3}code{font-size:14px}</style>'
    page += '<h1>Your original files, plus readable text.</h1><p>Offline TXT, Markdown and EPUB intake demo. Originals are copied byte for byte. <a href="manifest.json">Inspect file hashes and results</a>.</p>'
    page += '<table><tr><th>Source</th><th>Result</th><th>Output</th></tr>' + ''.join(rows) + '</table>'
    page += '<p>PDF, OCR, DRM, semantic categorization and CAD are outside this demo. Markdown stays as text. No network code or external packages.</p>'
    (destination / "index.html").write_text(page, encoding="utf-8")
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
