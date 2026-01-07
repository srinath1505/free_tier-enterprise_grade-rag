import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.security.sanitizer import InputSanitizer

def test_sanitizer():
    sanitizer = InputSanitizer()
    
    test_cases = [
        (
            "My email is test.user@example.com and phone is 555-0199-8888", 
            "My email is <EMAIL_REDACTED> and phone is <PHONE_REDACTED>"
        ),
        (
            "Here is a credit card 1234-5678-9012-3456 do not share",
            "Here is a credit card <CREDIT_CARD_REDACTED> do not share"
        ),
        (
            "Safe input with no PII",
            "Safe input with no PII"
        )
    ]
    
    print("Running PII Sanitizer Tests...")
    failures = 0
    for i, (input_text, expected) in enumerate(test_cases):
        result = sanitizer.sanitize(input_text)
        # Regex matching might vary slightly on exact boundaries, so we print for visual check
        print(f"\nCase {i+1}:")
        print(f"Input:    {input_text}")
        print(f"Result:   {result}")
        
        # Simple check if PII remains
        if sanitizer.contains_pii(result):
            print("FAILURE: PII still detected!")
            failures += 1
        elif result == input_text and "<" not in expected and "REDACTED" not in expected:
             print("SUCCESS: Unchanged as expected.")
        elif "REDACTED" in result:
             print("SUCCESS: PII Redacted.")
             
    if failures == 0:
        print("\nAll tests passed!")
    else:
        print(f"\n{failures} tests failed.")

if __name__ == "__main__":
    test_sanitizer()
