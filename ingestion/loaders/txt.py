from typing import List, Dict, Any
from ingestion.loaders.base import BaseLoader

class TXTLoader(BaseLoader):
    def load(self) -> List[Dict[str, Any]]:
        documents = []
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                text = f.read()
                if text.strip():
                    documents.append({
                        'content': text,
                        'metadata': {
                            'source': self.filename,
                            'type': 'txt'
                        }
                    })
        except Exception as e:
            print(f"Error loading TXT {self.filename}: {e}")
        return documents
