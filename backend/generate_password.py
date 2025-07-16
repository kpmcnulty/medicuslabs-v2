#!/usr/bin/env python3
"""Generate a new admin password hash"""

import bcrypt
import getpass
import sys

def generate_password_hash(password: str) -> str:
    """Generate bcrypt hash for password"""
    # Generate salt and hash the password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def main():
    if len(sys.argv) > 1:
        # Password provided as argument
        password = sys.argv[1]
    else:
        # Prompt for password
        password = getpass.getpass("Enter new admin password: ")
        confirm = getpass.getpass("Confirm password: ")
        
        if password != confirm:
            print("Passwords don't match!")
            sys.exit(1)
    
    if len(password) < 6:
        print("Password must be at least 6 characters long!")
        sys.exit(1)
    
    # Generate hash
    password_hash = generate_password_hash(password)
    
    print(f"\nGenerated password hash:")
    print(f"ADMIN_PASSWORD_HASH={password_hash}")
    print(f"\nUpdate your .env file with this hash.")
    print(f"Then restart the services: docker-compose restart api")

if __name__ == "__main__":
    main()