import docx
from typing import List, Dict, Any
from ingestion.loaders.base import BaseLoader


def _table_to_markdown(table) -> str:
    """Convert a python-docx Table object to a markdown-style string."""
    rows = []
    for i, row in enumerate(table.rows):
        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
        rows.append(" | ".join(cells))
        if i == 0:
            rows.append(" | ".join(["---"] * len(cells)))
    return "\n".join(rows)


class DOCXLoader(BaseLoader):
    def load(self) -> List[Dict[str, Any]]:
        documents = []
        try:
            doc = docx.Document(self.file_path)

            # Walk the document body in order so paragraphs and tables appear
            # in their original sequence (doc.paragraphs skips tables entirely).
            parts: List[str] = []
            for block in doc.element.body:
                tag = block.tag.split("}")[-1]  # strip namespace
                if tag == "p":
                    para = docx.text.paragraph.Paragraph(block, doc)
                    if para.text.strip():
                        parts.append(para.text.strip())
                elif tag == "tbl":
                    table = docx.table.Table(block, doc)
                    md = _table_to_markdown(table)
                    if md.strip():
                        parts.append(md)

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