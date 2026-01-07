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
            
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Splits documents into smaller chunks while preserving metadata.
        Uses spaCy sentence segmentation.
        """
        chunked_docs = []
        
        for doc in documents:
            text = doc.get('content', '')
            base_metadata = doc.get('metadata', {})
            
            # Disable unneeded pipeline components for speed
            doc_spacy = self.nlp(text, disable=["ner", "tagger", "lemmatizer"])
            sentences = [sent.text.strip() for sent in doc_spacy.sents]
            
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
