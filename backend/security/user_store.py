import json
import os
from typing import Dict, Optional, Any
from backend.core.config import settings

# Path to the persistent user store
USER_DB_PATH = os.path.join(settings.BASE_DIR, "users.json")

class UserStore:
    def __init__(self):
        self.db: Dict[str, Any] = {}
        self.load_users()

    def load_users(self):
        """Load users from JSON file, or initialize with default admin if missing."""
        if os.path.exists(USER_DB_PATH):
            try:
                with open(USER_DB_PATH, "r") as f:
                    self.db = json.load(f)
            except json.JSONDecodeError:
                self.db = {}
        
        # Ensure default admin always exists if DB is empty or corrupt
        if not self.db or "admin" not in self.db:
            from backend.security.auth import pwd_context # Lazy import to avoid cycle
            
            # Default: admin / password
            default_password_hash = pwd_context.hash("password")
            self.db["admin"] = {
                "username": "admin",
                "role": "admin",
                "hashed_password": default_password_hash
            }
            self.save_users()

    def save_users(self):
        """Persist current memory DB to disk."""
        with open(USER_DB_PATH, "w") as f:
            json.dump(self.db, f, indent=4)

    def get_user(self, username: str) -> Optional[Dict]:
        return self.db.get(username)

    def create_user(self, username: str, password_hash: str, role: str = "viewer") -> bool:
        if username in self.db:
            return False # User already exists
        
        self.db[username] = {
            "username": username,
            "role": role,
            "hashed_password": password_hash
        }
        self.save_users()
        return True

    def delete_user(self, username: str) -> bool:
        if username in self.db and username != "admin": # Protect admin
            del self.db[username]
            self.save_users()
            return True
        return False

# Global instance
user_store = UserStore()
