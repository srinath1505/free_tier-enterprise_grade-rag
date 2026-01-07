from typing import List, Dict, Any
from abc import ABC, abstractmethod
import os

class BaseLoader(ABC):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.filename = os.path.basename(file_path)

    @abstractmethod
    def load(self) -> List[Dict[str, Any]]:
        """
        Load document and return a list of dictionary with content and metadata.
        Format: [{'content': '...', 'metadata': {'source': '...', 'page': 1, ...}}]
        """
        pass
