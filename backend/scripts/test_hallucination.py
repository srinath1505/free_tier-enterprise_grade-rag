import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.security.hallucination import HallucinationDetector

def test_hallucination():
    detector = HallucinationDetector()
    
    # Context about a specific topic (e.g., Enterprise RAG)
    context = [
        "The Enterprise RAG Platform runs on free-tier resources.",
        "It uses FAISS for vector storage and Phi-3-mini for generation.",
        "Memory usage is constrained to 512MB per service."
    ]
    
    print("Context:")
    for c in context:
        print(f" - {c}")
    print("-" * 30)

    # Case 1: Grounded Answer
    answer_1 = "The platform uses FAISS and keeps memory under 512MB."
    is_grounded, score, reason = detector.check_grounding(answer_1, context)
    print(f"\nAnswer 1: {answer_1}")
    print(f"Result: {is_grounded} (Score: {score:.3f}) - {reason}")
    if not is_grounded:
        print("FAILURE: Should be grounded.")

    # Case 2: Hallucination (Unrelated fact)
    answer_2 = "The Eiffel Tower is located in Paris, France."
    is_grounded, score, reason = detector.check_grounding(answer_2, context)
    print(f"\nAnswer 2: {answer_2}")
    print(f"Result: {is_grounded} (Score: {score:.3f}) - {reason}")
    if is_grounded:
        print("FAILURE: Should be detected as hallucination.")
        
    # Case 3: Hallucination (Contradiction/Fabrication)
    answer_3 = "The system runs on a massive GPU cluster with 100GB RAM."
    is_grounded, score, reason = detector.check_grounding(answer_3, context)
    print(f"\nAnswer 3: {answer_3}")
    print(f"Result: {is_grounded} (Score: {score:.3f}) - {reason}")
    # Note: Semantic similarity might be high if keywords overlap ("RAM", "System"). 
    # This is a known limitation of pure embedding similarity vs NLI.
    # We'll see how it performs.

if __name__ == "__main__":
    test_hallucination()
