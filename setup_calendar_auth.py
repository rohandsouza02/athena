#!/usr/bin/env python3
"""
Setup script to authenticate with Google Calendar API
This will create the token file needed by the Athena bot
"""

import json
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Scopes needed for Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']

def main():
    creds = None
    
    # Check if token.json already exists
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no (valid) credentials available, run the OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Load client secrets
            if not os.path.exists('credentials.json'):
                print("❌ credentials.json not found!")
                print("Download OAuth2 credentials from Google Cloud Console")
                return
            
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
        print("✅ Token saved to token.json")
    
    # Test the credentials
    try:
        service = build('calendar', 'v3', credentials=creds)
        calendar_list = service.calendarList().list().execute()
        print("✅ Google Calendar API access successful!")
        print(f"Found {len(calendar_list.get('items', []))} calendars")
        
        # Update config to use token.json
        if os.path.exists('athena_config.json'):
            with open('athena_config.json', 'r') as f:
                config = json.load(f)
            config['google']['credentials_path'] = 'token.json'
            with open('athena_config.json', 'w') as f:
                json.dump(config, f, indent=2)
            print("✅ Updated athena_config.json to use token.json")
        
    except Exception as e:
        print(f"❌ Failed to access Google Calendar: {e}")

if __name__ == '__main__':
    main()