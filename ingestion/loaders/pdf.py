import base64
import os
from pathlib import Path
from typing import List, Dict, Any

import pdfplumber

from ingestion.loaders.base import BaseLoader


def _table_to_markdown(table: List[List]) -> str:
    """Convert a pdfplumber table (list of rows) to markdown."""
    if not table:
        return ""
    rows = []
    for i, row in enumerate(table):
        cells = [str(cell or "").strip().replace("\n", " ") for cell in row]
        rows.append(" | ".join(cells))
        if i == 0:
            rows.append(" | ".join(["---"] * len(cells)))
    return "\n".join(rows)


def _caption_images(page, filename: str, page_num: int) -> List[str]:
    """
    Extract images from a pdfplumber page and caption them via Groq vision
    (llama-4-scout-17b-16e-instruct). Returns a list of caption strings.
    Falls back silently if GROQ_API_KEY is not set or image extraction fails.
    """
    captions: List[str] = []
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        return captions

    try:
        import requests
        from PIL import Image
        import io

        for img_info in page.images:
            try:
                # pdfplumber exposes the raw stream bytes
                raw = img_info.get("stream")
                if raw is None:
                    continue
                data = raw.get_data() if hasattr(raw, "get_data") else bytes(raw)
                if not data:
                    continue

                # Convert to PNG via Pillow (handles JPEG, PNG, etc.)
                img = Image.open(io.BytesIO(data)).convert("RGB")
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
                        captions.append(
                            f"[Image on page {page_num} of {filename}]: {caption}"
                        )
            except Exception:
                continue  # skip individual image failures silently

    except ImportError:
        pass  # Pillow not installed — skip image extraction

    return captions


class PDFLoader(BaseLoader):
    def load(self) -> List[Dict[str, Any]]:
        documents = []
        try:
            with pdfplumber.open(self.file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_num = i + 1
                    parts: List[str] = []

                    # ── 1. Plain text (excluding table bounding boxes) ──────
                    table_bboxes = [t.bbox for t in page.find_tables()]

                    def outside_tables(obj):
                        for bbox in table_bboxes:
                            x0, top, x1, bottom = bbox
                            if (obj["x0"] >= x0 and obj["x1"] <= x1
                                    and obj["top"] >= top and obj["bottom"] <= bottom):
                                return False
                        return True

                    if table_bboxes:
                        filtered = page.filter(outside_tables)
                        text = filtered.extract_text() or ""
                    else:
                        text = page.extract_text() or ""

                    if text.strip():
                        parts.append(text.strip())

                    # ── 2. Tables ────────────────────────────────────────────
                    for table in page.find_tables():
                        rows = table.extract()
                        if rows:
                            md = _table_to_markdown(rows)
                            if md.strip():
                                parts.append(md)

                    # ── 3. Images (captioned via Groq vision) ────────────────
                    parts.extend(_caption_images(page, self.filename, page_num))

                    if parts:
                        documents.append({
                            "content": "\n\n".join(parts),
                            "metadata": {
                                "source": self.filename,
                                "page": page_num,
                                "type": "pdf",
                            },
                        })

        except Exception as e:
            print(f"Error loading PDF {self.filename}: {e}")
        return documents