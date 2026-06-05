import spacy
from typing import List, Dict, Any

class SemanticChunker:
    def __init__(self, model_name: str = "en_core_web_sm", chunk_size: int = 500, chunk_overlap: int = 50):
        try:
            self.nlp = spacy.load(model_name)
        except OSError:
            print(f"Downloading spaCy model {model_name}...")
            from spacy.cli import download
            download(model_name)
            self.nlp = spacy.load(model_name)

        # NER/tagger/parser are disabled during chunking so memory pressure is
        # minimal — raise the limit to handle large PDFs and long MDX files.
        self.nlp.max_length = 10_000_000
        self._spacy_batch = 900_000   # split texts larger than this before nlp()

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _sentences_from_text(self, text: str) -> List[str]:
        """Run spaCy sentence segmentation, splitting oversized texts into fixed batches."""
        if len(text) <= self._spacy_batch:
            doc = self.nlp(text, disable=["ner", "tagger", "lemmatizer"])
            return [s.text.strip() for s in doc.sents if s.text.strip()]

        sentences: List[str] = []
        for start in range(0, len(text), self._spacy_batch):
            batch = text[start:start + self._spacy_batch]
            doc = self.nlp(batch, disable=["ner", "tagger", "lemmatizer"])
            sentences.extend(s.text.strip() for s in doc.sents if s.text.strip())
        return sentences

    def chunk(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Splits documents into smaller chunks while preserving metadata.
        Uses spaCy sentence segmentation.
        """
        chunked_docs = []

        for doc in documents:
            text = doc.get('content', '')
            base_metadata = doc.get('metadata', {})
            
            sentences = self._sentences_from_text(text)
            
            current_chunk = []
            current_length = 0
            
            for sentence in sentences:
                sent_len = len(sentence)
                
                if current_length + sent_len > self.chunk_size and current_chunk:
                    # Finalize current chunk
                    chunk_text = " ".join(current_chunk)
                    chunked_docs.append({
                        'content': chunk_text,
                        'metadata': base_metadata
                    })
                    
                    # Start new chunk with overlap (simple approach: just reset, 
                    # advanced: keep last sentence if fit)
                    # For simplicity here: just start fresh with current sentence
                    current_chunk = [sentence]
                    current_length = sent_len
                else:
                    current_chunk.append(sentence)
                    current_length += sent_len
            
            # Add remaining
            if current_chunk:
                chunked_docs.append({
                    'content': " ".join(current_chunk),
                    'metadata': base_metadata
                })
                
        return chunked_docs
