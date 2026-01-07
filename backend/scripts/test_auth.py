import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.security.auth import verify_password, create_access_token, get_user, fake_users_db
from jose import jwt, JWTError

def test_authentication_logic():
    print("Testing Auth Logic...")

    # 1. Test Password Verification
    user = get_user(fake_users_db, "admin")
    if user and verify_password("password", user.hashed_password):
        print("SUCCESS: Password verification working.")
    else:
        print("FAILURE: Password verification failed.")

    # 2. Test Token Creation
    data = {"sub": "testuser", "role": "viewer"}
    token = create_access_token(data)
    print(f"Token generated: {token[:20]}...")

    # 3. Test Token Decode
    try:
        payload = jwt.decode(token, "super-secret-key-change-this-in-prod", algorithms=["HS256"])
        if payload["sub"] == "testuser" and payload["role"] == "viewer":
            print("SUCCESS: Token decoded correctly.")
        else:
            print("FAILURE: Token payload mismatch.")
    except JWTError as e:
        print(f"FAILURE: Token decode error: {e}")

if __name__ == "__main__":
    test_authentication_logic()
