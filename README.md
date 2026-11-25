# 本地文库收件

把一堆离线文件先收进来：原文原样存一份，再抽出能读的文本，并记下每个文件发生了什么。

[查看结果页](demo/delivery/index.html) · [带文件哈希的清单](demo/delivery/manifest.json) · [EPUB 抽出的文本示例](demo/delivery/text/0001-garden.epub.txt)

下载仓库后，在本地打开 `demo/delivery/index.html` 就能点开结果链接。GitHub 上打开这个 HTML 只会看到源码，不会当成网页跑。

## 在自己电脑上运行

需要 Python 3.10 或更新版本。不额外装包，也不联网、不调模型。

```text
python intake.py path/to/input path/to/new-output
```

新的输出目录里会有：

- `originals/`：按字节原样保存的副本
- `text/`：抽出的 UTF-8 文本
- `manifest.json`：SHA-256 哈希和每个文件的处理结果
- 一份本地 HTML 总览

清单里的输入路径相对于你选的输入文件夹。

- UTF-8 的 TXT 和 Markdown：保留文本，换行会规范化，可选的编码标记会去掉。Markdown 语法仍按文本留下。
- 未加密的文本 EPUB：按书里声明的阅读顺序抽出章节。图片、脚本、样式和文首元数据不会进派生文本，也不会去拉链接里的地址。
- 暂不支持的格式：原文仍会归档，并在结果里标明状态。转换失败会记成错误，不会写成抽取成功。
- 已有的输出目录，以及输入输出套叠的路径，会被拒绝。再跑一次请换一个新的目标目录。

一次运行最多 100 个文件、合计 100 MiB、单个输入文件 20 MiB；EPUB 展开后最多 100 MiB / 5,000 个条目。输入里的链接文件或文件夹会被拒绝。中途打断可能留下不完整的输出目录，重试时请换新目录。

目前只处理上面这些格式，不做 PDF、OCR、DOCX，也不能解开带数字版权保护的文件。归档会保留原文的全部字节。

## 验收

```text
python -m unittest -v
python build_demo.py
```

第二条会在 `demo-run/` 下生成新的示例输入和输出；目录已存在就会拒绝。仓库里现成的示例在 `demo/`。

测试覆盖：EPUB 阅读顺序和被省略的非文本资源、原文哈希保持不变、可重复的输出、失败和不支持的格式、重复的文件名、HTML 转义、大小限制，以及拒绝覆盖。在 Windows、Python 3.12.14 上 8 项测试全部通过。环境和具体结果见 `VALIDATION.txt`。

MIT 许可。

<details>
<summary>English</summary>

This tool takes offline files, keeps a byte-for-byte copy of each original, extracts readable text, and records what happened to every file.

Open `demo/delivery/index.html` locally after downloading the repository. GitHub will show the HTML source rather than a rendered page.

Requires Python 3.10 or newer. No extra packages or network access:

```text
python intake.py path/to/input path/to/new-output
```

The new output directory contains `originals/`, extracted UTF-8 files in `text/`, a `manifest.json` with SHA-256 hashes, and a local HTML overview. See the Chinese section above for format rules and size limits. Run `python -m unittest -v` and `python build_demo.py` to verify. On Windows with Python 3.12.14, 8 tests passed.

</details>
