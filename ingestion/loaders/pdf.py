import PyPDF2
from typing import List, Dict, Any
from ingestion.loaders.base import BaseLoader

class PDFLoader(BaseLoader):
    def load(self) -> List[Dict[str, Any]]:
        documents = []
        try:
            reader = PyPDF2.PdfReader(self.file_path)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text.strip():
                    documents.append({
                        'content': text,
                        'metadata': {
                            'source': self.filename,
                            'page': i + 1,
                            'type': 'pdf'
                        }
                    })
        except Exception as e:
            print(f"Error loading PDF {self.filename}: {e}")
        return documents
