import sys
import os
import pickle

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.config import settings

def debug_metadata():
    meta_path = os.path.join(settings.VECTOR_STORE_PATH, "metadata.pkl")
    print(f"Checking metadata file: {meta_path}")
    
    if not os.path.exists(meta_path):
        print("Metadata file NOT FOUND.")
        return

    with open(meta_path, "rb") as f:
        metadata = pickle.load(f)
        
    print(f"Loaded {len(metadata)} items.")
    if len(metadata) > 0:
        first_item = metadata[0]
        print("First Item Keys:", first_item.keys())
        if 'content' in first_item:
            print("Content Snippet:", first_item['content'][:100])
        else:
            print("CRITICAL: 'content' key MISSING in metadata.")
            
if __name__ == "__main__":
    debug_metadata()
