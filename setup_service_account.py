#!/usr/bin/env python3
"""
Setup Google Calendar with Service Account (easier for testing)
"""

import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

def main():
    print("🔧 Setting up Service Account for Google Calendar...")
    
    # Check if service account credentials exist
    if not os.path.exists('service_account.json'):
        print("❌ service_account.json not found!")
        print("\nTo create service account:")
        print("1. Go to Google Cloud Console → IAM & Admin → Service Accounts")
        print("2. Create Service Account")
        print("3. Download JSON key as 'service_account.json'")
        print("4. Share your calendar with the service account email")
        return
    
    try:
        # Load service account credentials
        credentials = service_account.Credentials.from_service_account_file(
            'service_account.json',
            scopes=['https://www.googleapis.com/auth/calendar']
        )
        
        # Test the connection
        service = build('calendar', 'v3', credentials=credentials)
        calendar_list = service.calendarList().list().execute()
        
        print("✅ Service Account authentication successful!")
        print(f"Found {len(calendar_list.get('items', []))} calendars")
        
        # Update bot to use service account
        print("\n📝 Update your athena_meet_bot.py to use service account...")
        
    except Exception as e:
        print(f"❌ Service Account setup failed: {e}")
        print("\nMake sure to:")
        print("1. Share your calendar with service account email")
        print("2. Enable Google Calendar API")

if __name__ == '__main__':
    import os
    main()