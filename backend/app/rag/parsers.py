import io
from dataclasses import dataclass

import docx
from pypdf import PdfReader


@dataclass
class ParsedPage:
    text: str
    page_no: int | None = None  # PDF 页码(docx/txt/md 为 0)


def parse_document(content: bytes, file_type: str) -> list[ParsedPage]:
    """按文件类型分发到解析器,统一返回逐页文本。"""
    parser = _PARSERS.get(file_type.lower())
    if parser is None:
        raise ValueError(f"Unsupported file type: {file_type}")
    return parser(content)


def _parse_txt(content: bytes) -> list[ParsedPage]:
    return [ParsedPage(text=content.decode("utf-8", errors="replace"), page_no=0)]


def _parse_pdf(content: bytes) -> list[ParsedPage]:
    reader = PdfReader(io.BytesIO(content))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append(ParsedPage(text=text, page_no=i))
    return pages


def _parse_docx(content: bytes) -> list[ParsedPage]:
    doc = docx.Document(io.BytesIO(content))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [ParsedPage(text=text, page_no=0)]


_PARSERS = {
    "pdf": _parse_pdf,
    "docx": _parse_docx,
    "md": _parse_txt,
    "markdown": _parse_txt,
    "txt": _parse_txt,
}
