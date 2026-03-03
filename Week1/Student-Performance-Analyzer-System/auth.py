"""
==============================================================
FILE: auth.py
DESCRIPTION: User authentication and session management
==============================================================
"""

import csv
import os
from colorama import Fore, Style
from utils import record_action


# -------------------- User Class --------------------
class User:
    """Represents an authenticated system user"""
    
    def __init__(self, username: str, role: str):
        self.username = username
        self.role = role.lower()
    
    def is_admin(self) -> bool:
        """Check if user has administrator privileges"""
        return self.role == "admin"
    
    def __str__(self) -> str:
        return f"User({self.username}, {self.role})"


# -------------------- Authentication Functions --------------------
def load_users(file_path: str) -> dict:
    """
    Load users from CSV file.
    Returns: dict {username: {"password": str, "role": str}}
    """
    users = {}
    
    # Return empty dict if file doesn't exist
    if not os.path.exists(file_path):
        print(Fore.YELLOW + f"Warning: User file '{file_path}' not found")
        return users
    
    try:
        with open(file_path, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                users[row["username"]] = {
                    "password": row["password"],
                    "role": row["role"]
                }
        
        print(Fore.GREEN + f"✓ Loaded {len(users)} users from file")
        
    except Exception as e:
        print(Fore.RED + f"Error loading users: {e}")
    
    return users


def login(users_db: dict):
    """
    Handle user login process.
    Returns User object if successful, None otherwise.
    """
    print(Fore.CYAN + "\n" + "="*40)
    print(Fore.CYAN + "🔐 LOGIN SYSTEM")
    print(Fore.CYAN + "="*40 + Style.RESET_ALL)
    
    # Get credentials
    username = input("Username: ").strip()
    password = input("Password: ").strip()
    
    # Validate input
    if not username or not password:
        print(Fore.RED + "❌ Username and password cannot be empty")
        return None
    
    # Check credentials
    if username in users_db and users_db[username]["password"] == password:
        role = users_db[username]["role"]
        
        # Success message
        print(Fore.GREEN + f"\n✅ Welcome, {username}!")
        print(Fore.YELLOW + f"Role: {role.upper()}")
        
        # Log the action
        record_action(f"LOGIN user={username} role={role}")
        
        return User(username, role)
    
    # Failed login
    print(Fore.RED + "❌ Invalid username or password")
    record_action(f"FAILED_LOGIN attempt for username={username}")
    
    return None


def logout(user: User) -> None:
    """Log out the current user"""
    if user:
        print(Fore.CYAN + f"\n👋 Goodbye, {user.username}!")
        record_action(f"LOGOUT user={user.username}")