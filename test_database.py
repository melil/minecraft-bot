#!/usr/bin/env python3
"""
Test script to verify database functionality
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_db, UserRole

def test_database():
    """Test database operations"""
    print("=" * 50)
    print("Testing Database Functionality")
    print("=" * 50)
    
    db = get_db()
    
    # Test 1: Create a test user
    print("\n[Test 1] Creating test user...")
    user = db.get_or_create_user(
        telegram_id=12345,
        username="testuser",
        first_name="Test",
        last_name="User",
        auto_promote_ids=[]
    )
    print(f"✅ Created user: {user}")
    
    # Test 2: Check user role
    print("\n[Test 2] Checking user role...")
    is_admin = db.is_admin(12345)
    print(f"Is admin: {is_admin}")
    assert is_admin == False, "New user should not be admin"
    print("✅ Role check passed")
    
    # Test 3: Promote to admin
    print("\n[Test 3] Promoting to admin...")
    db.update_user_role(12345, UserRole.ADMIN)
    is_admin = db.is_admin(12345)
    print(f"Is admin after promotion: {is_admin}")
    assert is_admin == True, "User should be admin after promotion"
    print("✅ Promotion successful")
    
    # Test 4: Update Minecraft nickname
    print("\n[Test 4] Setting Minecraft nickname...")
    success = db.update_user_minecraft_nickname(12345, "TestPlayer123")
    assert success == True, "Should successfully update nickname"
    user = db.get_user_by_telegram_id(12345)
    print(f"Minecraft nickname: {user.minecraft_nickname}")
    print("✅ Nickname updated")
    
    # Test 5: Get all admins
    print("\n[Test 5] Getting all admins...")
    admins = db.get_all_admins()
    print(f"Total admins: {len(admins)}")
    for admin in admins:
        role = "👑 SUPER_ADMIN" if admin.is_super_admin() else "🔑 ADMIN"
        print(f"  - {admin.telegram_id} ({role}) - {admin.get_display_name()}")
    print("✅ Admin list retrieved")
    
    # Test 6: Test super admin
    print("\n[Test 6] Testing super admin...")
    db.update_user_role(12345, UserRole.SUPER_ADMIN)
    is_super_admin = db.is_super_admin(12345)
    print(f"Is super admin: {is_super_admin}")
    assert is_super_admin == True, "User should be super admin"
    print("✅ Super admin test passed")
    
    print("\n" + "=" * 50)
    print("✅ All tests passed!")
    print("=" * 50)

if __name__ == "__main__":
    try:
        test_database()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
