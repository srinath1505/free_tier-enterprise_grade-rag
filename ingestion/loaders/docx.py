import docx
from typing import List, Dict, Any
from ingestion.loaders.base import BaseLoader

class DOCXLoader(BaseLoader):
    def load(self) -> List[Dict[str, Any]]:
        documents = []
        try:
            doc = docx.Document(self.file_path)
            # Naive approach: treat each paragraph as potential content
            # Better approach: group by headings or sections (Phase 1 simplistic)
            full_text = []
            for para in doc.paragraphs:
                if para.text.strip():
                    full_text.append(para.text)
            
            if full_text:
                documents.append({
                    'content': "\n".join(full_text),
                    'metadata': {
                        'source': self.filename,
                        'type': 'docx'
                    }
                })
        except Exception as e:
            print(f"Error loading DOCX {self.filename}: {e}")
        return documents
