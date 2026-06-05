import base64
import os
import docx
import docx.text.paragraph
import docx.table
from typing import List, Dict, Any

from ingestion.loaders.base import BaseLoader

try:
    from docx.oxml.ns import qn as _qn
except ImportError:  # pragma: no cover
    _qn = None


def _table_to_markdown(table) -> str:
    """Convert a python-docx Table object to a markdown-style string."""
    rows = []
    for i, row in enumerate(table.rows):
        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
        rows.append(" | ".join(cells))
        if i == 0:
            rows.append(" | ".join(["---"] * len(cells)))
    return "\n".join(rows)


def _image_blobs_from_paragraph(para, doc) -> List[bytes]:
    """Return the raw image bytes for every embedded picture in a paragraph."""
    if _qn is None:
        return []
    blobs: List[bytes] = []
    for blip in para._element.iter(_qn("a:blip")):
        r_id = blip.get(_qn("r:embed"))
        if not r_id:
            continue
        try:
            blobs.append(doc.part.related_parts[r_id].blob)
        except (KeyError, AttributeError):
            continue
    return blobs


def _caption_blob(blob: bytes, source: str, idx: int) -> str:
    """
    Caption one image blob via Groq vision (llama-4-scout-17b-16e-instruct).
    Returns "" silently on any failure or when GROQ_API_KEY is not set.
    """
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        return ""
    try:
        import io
        import requests
        from PIL import Image

        img = Image.open(io.BytesIO(blob)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        payload = {
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Describe this image concisely for a search index. "
                                "Include all visible text, numbers, labels, and what "
                                "the image depicts. Be factual and specific."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
            "max_tokens": 256,
        }
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        if resp.ok:
            caption = resp.json()["choices"][0]["message"]["content"].strip()
            if caption:
                return f"[Image {idx} in {source}]: {caption}"
    except Exception:
        pass
    return ""


def _process_paragraph(para, doc, source: str, parts: List[str], img_counter: list) -> None:
    """Append paragraph text and any image captions to parts in document order."""
    if para.text.strip():
        parts.append(para.text.strip())
    for blob in _image_blobs_from_paragraph(para, doc):
        img_counter[0] += 1
        caption = _caption_blob(blob, source, img_counter[0])
        if caption:
            parts.append(caption)


class DOCXLoader(BaseLoader):
    def load(self) -> List[Dict[str, Any]]:
        documents = []
        try:
            doc = docx.Document(self.file_path)

            parts: List[str] = []
            img_counter = [0]  # mutable so _process_paragraph can increment it

            for block in doc.element.body:
                tag = block.tag.split("}")[-1]
                if tag == "p":
                    para = docx.text.paragraph.Paragraph(block, doc)
                    _process_paragraph(para, doc, self.filename, parts, img_counter)
                elif tag == "tbl":
                    table = docx.table.Table(block, doc)
                    md = _table_to_markdown(table)
                    if md.strip():
                        parts.append(md)
                    # Images embedded inside table cells
                    for row in table.rows:
                        for cell in row.cells:
                            for para in cell.paragraphs:
                                for blob in _image_blobs_from_paragraph(para, doc):
                                    img_counter[0] += 1
                                    caption = _caption_blob(
                                        blob, self.filename, img_counter[0]
                                    )
                                    if caption:
                                        parts.append(caption)

            if parts:
                documents.append({
                    "content": "\n\n".join(parts),
                    "metadata": {
                        "source": self.filename,
                        "type": "docx",
                    },
                })
        except Exception as e:
            print(f"Error loading DOCX {self.filename}: {e}")
        return documents