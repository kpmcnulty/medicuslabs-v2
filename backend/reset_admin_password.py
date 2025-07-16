#!/usr/bin/env python3
"""
Secure admin password reset script - can only be run via docker exec
"""

import asyncio
import getpass
import sys
from core.auth import get_password_hash
from core.database import get_pg_connection

async def reset_admin_password():
    """Reset admin password securely"""
    print("🔐 Admin Password Reset")
    print("=" * 30)
    
    # Get username (default to admin)
    username = input("Username (default: admin): ").strip() or "admin"
    
    # Get new password
    while True:
        password = getpass.getpass("New password: ")
        confirm = getpass.getpass("Confirm password: ")
        
        if password != confirm:
            print("❌ Passwords don't match! Try again.")
            continue
            
        if len(password) < 6:
            print("❌ Password must be at least 6 characters long!")
            continue
            
        break
    
    # Generate hash
    print("🔄 Generating password hash...")
    password_hash = get_password_hash(password)
    
    # Update database
    print("💾 Updating database...")
    async with get_pg_connection() as conn:
        result = await conn.execute("""
            UPDATE admin_users 
            SET password_hash = $1, updated_at = NOW()
            WHERE username = $2
        """, password_hash, username)
        
        if result == "UPDATE 0":
            print(f"❌ Admin user '{username}' not found!")
            return False
    
    print(f"✅ Password updated successfully for '{username}'!")
    print("🔄 Restart the API service: docker-compose restart api")
    return True

async def list_admin_users():
    """List existing admin users"""
    async with get_pg_connection() as conn:
        users = await conn.fetch("SELECT username, created_at FROM admin_users ORDER BY created_at")
        
        if not users:
            print("No admin users found.")
            return
            
        print("\nExisting admin users:")
        for user in users:
            print(f"  - {user['username']} (created: {user['created_at'].strftime('%Y-%m-%d')})")

if __name__ == "__main__":
    async def main():
        if len(sys.argv) > 1 and sys.argv[1] == "list":
            await list_admin_users()
        else:
            await reset_admin_password()
    
    asyncio.run(main())