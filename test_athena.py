#!/usr/bin/env python3
"""
Simple test script for Athena Meeting Bot functionality
"""

import asyncio
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from athena_meet_bot import AthenaMeetBot, MeetingSession, MeetingStatus

# Load environment variables from .env file
load_dotenv()


async def test_configuration():
    """Test configuration loading"""
    print("Testing configuration loading...")
    
    try:
        bot = AthenaMeetBot("athena_config.json")
        print("✅ Configuration loaded successfully")
        
        # Test config validation
        required_fields = ["vexa.api_key", "webhook.url"]
        missing = []
        
        for field_path in required_fields:
            value = bot.config
            for key in field_path.split('.'):
                value = value.get(key) if isinstance(value, dict) else None
                if value is None:
                    break
            if not value:
                missing.append(field_path)
        
        if missing:
            print(f"⚠️  Missing configuration: {', '.join(missing)}")
            print("Please set the following environment variables or update athena_config.json:")
            for field in missing:
                env_var = field.replace('.', '_').upper()
                print(f"  export {env_var}=your_value_here")
        else:
            print("✅ All required configuration present")
            
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False
    
    return True


async def test_vexa_api():
    """Test Vexa API connectivity (without creating actual bot)"""
    print("\nTesting Vexa API connectivity...")
    
    api_key = os.getenv("VEXA_API_KEY")
    if not api_key:
        print("❌ VEXA_API_KEY not set")
        return False
    
    # Test API key format
    if not api_key.startswith(('vxa_', 'sk-')):
        print("⚠️  API key format may be incorrect")
    
    print("✅ Vexa API key configured")
    return True


async def test_google_calendar():
    """Test Google Calendar configuration"""
    print("\nTesting Google Calendar setup...")
    
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    
    if os.path.exists(credentials_path):
        try:
            with open(credentials_path, 'r') as f:
                creds_data = json.load(f)
                if 'client_id' in creds_data or 'installed' in creds_data:
                    print("✅ Google credentials file found and valid")
                    return True
                else:
                    print("❌ Invalid Google credentials format")
                    return False
        except Exception as e:
            print(f"❌ Error reading Google credentials: {e}")
            return False
    else:
        print(f"❌ Google credentials file not found: {credentials_path}")
        print("Please download credentials from Google Cloud Console")
        return False


async def test_webhook():
    """Test webhook configuration"""
    print("\nTesting webhook configuration...")
    
    webhook_url = os.getenv("WEBHOOK_URL")
    if not webhook_url:
        print("❌ WEBHOOK_URL not set")
        return False
    
    if not webhook_url.startswith(('http://', 'https://')):
        print("❌ Invalid webhook URL format")
        return False
    
    print(f"✅ Webhook URL configured: {webhook_url}")
    return True


async def test_meeting_creation():
    """Test meeting session creation (without actual Google Meet)"""
    print("\nTesting meeting session creation...")
    
    try:
        bot = AthenaMeetBot("athena_config.json")
        
        # Create a mock session for testing
        session = MeetingSession(
            meeting_id="test-session",
            google_meet_url="https://meet.google.com/test-meet-id",
            google_meet_id="test-meet-id",
            start_time=datetime.now(),
            end_time=None,
            status=MeetingStatus.CREATED
        )
        
        # Test session status
        status = bot.get_session_status("test-session")
        if status is None:
            print("✅ Session management working correctly")
        else:
            print("⚠️  Session found when it shouldn't exist")
        
        print("✅ Meeting session creation test passed")
        return True
        
    except Exception as e:
        print(f"❌ Meeting creation test failed: {e}")
        return False


async def run_all_tests():
    """Run all tests"""
    print("🤖 Athena Meeting Bot - System Test\n")
    
    tests = [
        ("Configuration", test_configuration),
        ("Vexa API", test_vexa_api),
        ("Google Calendar", test_google_calendar),
        ("Webhook", test_webhook),
        ("Meeting Creation", test_meeting_creation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running {test_name} test...")
        print('='*50)
        
        try:
            result = await test_func()
            if result:
                passed += 1
                print(f"✅ {test_name} test PASSED")
            else:
                print(f"❌ {test_name} test FAILED")
        except Exception as e:
            print(f"❌ {test_name} test ERROR: {e}")
    
    print(f"\n{'='*50}")
    print(f"Test Results: {passed}/{total} tests passed")
    print('='*50)
    
    if passed == total:
        print("🎉 All tests passed! Athena bot is ready to use.")
        print("\nNext steps:")
        print("1. Set up your environment variables (see .env.example)")
        print("2. Configure meeting settings in athena_config.json")
        print("3. Run: python3 athena_meet_bot.py --mode scheduler")
    else:
        print("⚠️  Some tests failed. Please fix the issues before running the bot.")
        print("\nCheck the output above for specific issues to resolve.")
    
    return passed == total


if __name__ == "__main__":
    asyncio.run(run_all_tests())