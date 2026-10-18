# Local library intake

A small working example of the first step in an offline library pipeline: retain originals, extract readable text, and show what happened to every file.

**This is an original portfolio demo, using synthetic documents. It is not a client delivery or a paid case study.**

## See the result

[Delivery overview](demo/delivery/index.html) · [manifest with file hashes](demo/delivery/manifest.json) · [example EPUB output](demo/delivery/text/0001-garden.epub.txt)

Download the repository and open `demo/delivery/index.html` locally to follow the output links. GitHub shows HTML source rather than a hosted application.

## Run locally

Requires Python 3.10 or newer. No extra packages, account, cloud API, model, or network connection is used by the tool.

```text
python intake.py path/to/input path/to/new-output
```

The new output directory contains byte-for-byte archived copies in `originals/`, extracted UTF-8 files in `text/`, a `manifest.json` with SHA-256 hashes and per-file outcomes, and a local HTML overview. Input paths in the manifest are relative to the selected input folder.

- UTF-8 TXT and Markdown: text is preserved with normalized line endings and an optional encoding marker removed. Markdown syntax remains text.
- Unencrypted text EPUB: chapters follow the book's declared reading order. Images, scripts, styles and document-head metadata are omitted from the derived text. Nothing is fetched from linked URLs.
- Unsupported formats: originals are still archived and their status is reported. Failed conversions are errors, never presented as successful extraction.
- Existing output directories and nested input/output layouts are rejected. Use a new destination for another run.

Demo bounds: 100 files, 100 MiB total, 20 MiB per input file; EPUB expanded size up to 100 MiB / 5,000 members. Linked input files/folders are rejected. An interrupted run may leave a partial output directory; retry into a new directory.

PDF, OCR, DOCX, DRM, topic inference, CAD, machine operation and the remaining stages of a larger intelligence system are outside this demo. It does not claim to detect every kind of tracking or sanitize arbitrary documents. Original archives deliberately retain all original bytes.

## Verification

```text
python -m unittest -v
python build_demo.py
```

The second command creates new synthetic inputs and outputs under `demo-run/`; an existing directory is refused. The checked-in example is under `demo/`.

The tests exercise EPUB reading order and omitted non-text resources, preserved original hashes, repeatable outputs, failed and unsupported formats, duplicate basenames, HTML escaping, size limits and overwrite refusal. See `VALIDATION.txt` for actual results and environment.

MIT license.
