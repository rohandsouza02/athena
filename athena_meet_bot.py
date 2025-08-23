#!/usr/bin/env python3
"""
Athena Meeting Bot - Production-grade automated standup system
Integrates with Google Calendar, Vexa API, and webhook delivery

Features:
- Automated daily standup meeting creation
- Athena bot joins meetings via Vexa API
- Real-time transcript processing
- Post-meeting webhook delivery
- Error handling and retry mechanisms
- Comprehensive logging
"""

import asyncio
import json
import logging
import os
import uuid
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import traceback

import requests
import schedule
import time
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables from .env file
load_dotenv()


class MeetingStatus(Enum):
    CREATED = "created"
    BOT_JOINING = "bot_joining"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class MeetingSession:
    meeting_id: str
    google_meet_url: str
    google_meet_id: str
    start_time: datetime
    end_time: Optional[datetime]
    status: MeetingStatus
    bot_session_id: Optional[str] = None
    transcript: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0


class AthenaMeetBot:
    """Production-grade Athena meeting bot with Vexa API integration"""
    
    def __init__(self, config_path: str = "athena_config.json"):
        """Initialize Athena bot with configuration"""
        self.config = self._load_config(config_path)
        self.logger = self._setup_logging()
        self.google_service = None
        self._active_sessions: Dict[str, MeetingSession] = {}
        self.sessions_file = "active_sessions.pkl"
        
        # Initialize Google Calendar service
        self._init_google_calendar()
        
        # Validate configuration
        self._validate_config()
        
        # Load existing sessions
        self._load_sessions()
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration with fallback to environment variables"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            config = {}
        
        # Merge with environment variables
        return {
            "vexa": {
                "api_key": config.get("vexa", {}).get("api_key") or os.getenv("VEXA_API_KEY"),
                "base_url": config.get("vexa", {}).get("base_url", "https://gateway.dev.vexa.ai"),
                "timeout": config.get("vexa", {}).get("timeout", 30)
            },
            "google": {
                "credentials_path": config.get("google", {}).get("credentials_path") or os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json"),
                "calendar_id": config.get("google", {}).get("calendar_id") or os.getenv("GOOGLE_CALENDAR_ID", "primary")
            },
            "webhook": {
                "url": config.get("webhook", {}).get("url") or os.getenv("WEBHOOK_URL"),
                "secret": config.get("webhook", {}).get("secret") or os.getenv("WEBHOOK_SECRET"),
                "timeout": config.get("webhook", {}).get("timeout", 30),
                "retry_attempts": config.get("webhook", {}).get("retry_attempts", 3)
            },
            "meeting": {
                "default_duration": config.get("meeting", {}).get("default_duration", 30),
                "standup_time": config.get("meeting", {}).get("standup_time", "09:00"),
                "constant_meeting_url": config.get("meeting", {}).get("constant_meeting_url"),
                "constant_meeting_id": config.get("meeting", {}).get("constant_meeting_id"),
                "attendees": config.get("meeting", {}).get("attendees", []),
                "timezone": config.get("meeting", {}).get("timezone", "America/New_York")
            },
            "bot": {
                "name": "Athena",
                "join_delay": config.get("bot", {}).get("join_delay", 10),
                "max_retries": config.get("bot", {}).get("max_retries", 3),
                "transcript_poll_interval": config.get("bot", {}).get("transcript_poll_interval", 30)
            },
            "logging": {
                "level": config.get("logging", {}).get("level", "INFO"),
                "file": config.get("logging", {}).get("file", "athena_bot.log"),
                "max_size": config.get("logging", {}).get("max_size", 10485760),  # 10MB
                "backup_count": config.get("logging", {}).get("backup_count", 5)
            }
        }
    
    def _setup_logging(self) -> logging.Logger:
        """Setup comprehensive logging"""
        from logging.handlers import RotatingFileHandler
        
        log_config = self.config.get("logging", {})
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        
        # Setup file handler with rotation
        file_handler = RotatingFileHandler(
            log_config.get("file", "athena_bot.log"),
            maxBytes=log_config.get("max_size", 10485760),
            backupCount=log_config.get("backup_count", 5)
        )
        file_handler.setFormatter(formatter)
        
        # Setup console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Configure logger
        logger = logging.getLogger("AthenaBot")
        logger.setLevel(getattr(logging, log_config.get("level", "INFO")))
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def _validate_config(self):
        """Validate required configuration parameters"""
        required_fields = [
            ("vexa.api_key", "Vexa API key"),
            ("webhook.url", "Webhook URL"),
        ]
        
        missing_fields = []
        for field_path, description in required_fields:
            value = self.config
            for key in field_path.split('.'):
                value = value.get(key) if isinstance(value, dict) else None
                if value is None:
                    break
            
            if not value:
                missing_fields.append(description)
        
        if missing_fields:
            raise ValueError(f"Missing required configuration: {', '.join(missing_fields)}")
    
    def _init_google_calendar(self):
        """Initialize Google Calendar API service with multiple auth methods"""
        try:
            # Try service account first (recommended for bots)
            if os.path.exists('service_account.json'):
                credentials = service_account.Credentials.from_service_account_file(
                    'service_account.json',
                    scopes=['https://www.googleapis.com/auth/calendar']
                )
                self.google_service = build('calendar', 'v3', credentials=credentials)
                self.logger.info("Google Calendar service initialized with service account")
                return
            
            # Try OAuth token file
            if os.path.exists('token.json'):
                with open('token.json', 'r') as f:
                    creds_data = json.load(f)
                    creds = Credentials.from_authorized_user_info(creds_data)
                    if creds and creds.valid:
                        self.google_service = build('calendar', 'v3', credentials=creds)
                        self.logger.info("Google Calendar service initialized with OAuth token")
                        return
            
            # Fallback to configured credentials path
            creds_path = self.config["google"]["credentials_path"]
            if os.path.exists(creds_path):
                with open(creds_path, 'r') as f:
                    creds_data = json.load(f)
                    creds = Credentials.from_authorized_user_info(creds_data)
                    self.google_service = build('calendar', 'v3', credentials=creds)
                    self.logger.info("Google Calendar service initialized with configured credentials")
            else:
                self.logger.warning("No valid Google credentials found. Calendar features disabled.")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Google Calendar service: {e}")
    
    async def _check_existing_meeting(self, start_time: datetime) -> bool:
        """Check if a meeting already exists at the given time"""
        if not self.google_service:
            return False
        
        try:
            # Search for events in the time range (need timezone info)
            time_min = start_time.isoformat() + '+05:30'  # IST timezone
            time_max = (start_time + timedelta(minutes=self.config["meeting"]["default_duration"])).isoformat() + '+05:30'
            
            events_result = self.google_service.events().list(
                calendarId=self.config["google"]["calendar_id"],
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Check if any event contains "Daily Standup" or has Google Meet link
            for event in events:
                summary = event.get('summary', '').lower()
                if 'daily standup' in summary or 'standup' in summary:
                    return True
                    
                # Check if it has a Google Meet link (hangoutLink)
                if event.get('hangoutLink'):
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to check existing meeting: {e}")
            return False
    
    def _load_sessions(self):
        """Load active sessions from disk"""
        try:
            if os.path.exists(self.sessions_file):
                with open(self.sessions_file, 'rb') as f:
                    sessions_data = pickle.load(f)
                    for session_id, session_dict in sessions_data.items():
                        # Recreate MeetingSession objects
                        session = MeetingSession(
                            meeting_id=session_dict['meeting_id'],
                            google_meet_url=session_dict['google_meet_url'],
                            google_meet_id=session_dict['google_meet_id'],
                            start_time=session_dict['start_time'],
                            end_time=session_dict.get('end_time'),
                            status=MeetingStatus(session_dict['status']),
                            bot_session_id=session_dict.get('bot_session_id')
                        )
                        self._active_sessions[session_id] = session
                self.logger.info(f"Loaded {len(self._active_sessions)} active sessions")
        except Exception as e:
            self.logger.error(f"Failed to load sessions: {e}")
    
    def _save_sessions(self):
        """Save active sessions to disk"""
        try:
            sessions_data = {}
            for session_id, session in self._active_sessions.items():
                sessions_data[session_id] = {
                    'meeting_id': session.meeting_id,
                    'google_meet_url': session.google_meet_url,
                    'google_meet_id': session.google_meet_id,
                    'start_time': session.start_time,
                    'end_time': session.end_time,
                    'status': session.status.value,
                    'bot_session_id': session.bot_session_id
                }
            
            with open(self.sessions_file, 'wb') as f:
                pickle.dump(sessions_data, f)
        except Exception as e:
            self.logger.error(f"Failed to save sessions: {e}")
    
    async def create_daily_standup(self, date: Optional[datetime] = None) -> Optional[MeetingSession]:
        """Create a daily standup meeting"""
        if date is None:
            date = datetime.now()
        
        try:
            # Parse standup time
            standup_time = self.config["meeting"]["standup_time"]
            hour, minute = map(int, standup_time.split(':'))
            
            # Create meeting datetime
            meeting_start = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            meeting_end = meeting_start + timedelta(minutes=self.config["meeting"]["default_duration"])
            
            # Check if meeting already exists
            if await self._check_existing_meeting(meeting_start):
                self.logger.info(f"Meeting already exists at {meeting_start}, skipping creation")
                print(f"⏭️  Meeting already exists at {meeting_start}")
                return None
            
            # Always create Google Calendar events with Meet links for proper calendar integration
            # This ensures meetings show up on users' calendars
            meet_info = await self._create_google_meet(meeting_start, meeting_end)
            if not meet_info:
                # Fallback to constant meeting link if calendar creation fails
                constant_url = self.config["meeting"].get("constant_meeting_url")
                constant_id = self.config["meeting"].get("constant_meeting_id")
                
                if constant_url and constant_id:
                    meet_info = {
                        "meet_url": constant_url,
                        "meet_id": constant_id
                    }
                    self.logger.warning(f"Calendar creation failed, using constant meeting link: {constant_url}")
                else:
                    self.logger.error("Failed to create calendar event and no constant meeting URL configured")
                    return None
            
            # Create session
            session = MeetingSession(
                meeting_id=str(uuid.uuid4()),
                google_meet_url=meet_info["meet_url"],
                google_meet_id=meet_info["meet_id"],
                start_time=meeting_start,
                end_time=None,
                status=MeetingStatus.CREATED
            )
            
            self._active_sessions[session.meeting_id] = session
            self._save_sessions()  # Persist session to disk
            self.logger.info(f"Created standup meeting: {session.meeting_id} at {meeting_start}")
            
            return session
            
        except Exception as e:
            self.logger.error(f"Failed to create daily standup: {e}")
            return None
    
    async def _create_google_meet(self, start_time: datetime, end_time: datetime) -> Optional[Dict]:
        """Create Google Calendar event with Meet link"""
        if not self.google_service:
            self.logger.error("Google Calendar service not available")
            
            return None
        
        try:
            event = {
                'summary': 'Daily Standup - Categories',
                'description': 'Automated daily standup meeting with Athena bot transcription',
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': self.config["meeting"]["timezone"],
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': self.config["meeting"]["timezone"],
                },
                'attendees': [
                    {'email': email} for email in self.config["meeting"]["attendees"]
                ],
                'conferenceData': {
                    'createRequest': {
                        'requestId': str(uuid.uuid4()),
                        'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                    }
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 10},
                        {'method': 'popup', 'minutes': 5},
                    ],
                },
            }
            
            created_event = self.google_service.events().insert(
                calendarId=self.config["google"]["calendar_id"],
                body=event,
                conferenceDataVersion=1
            ).execute()
            
            # Extract Google Meet details
            conference_data = created_event.get('conferenceData', {})
            meet_url = conference_data.get('entryPoints', [{}])[0].get('uri', '')
            meet_id = meet_url.split('/')[-1] if meet_url else ''
            
            self.logger.info(f"Created Google Calendar event: {created_event['id']}")
            
            return {
                "event_id": created_event['id'],
                "meet_url": meet_url,
                "meet_id": meet_id
            }
            
        except HttpError as e:
            self.logger.error(f"Google Calendar API error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to create Google Meet: {e}")
            return None
    
    async def join_meeting_with_athena(self, session: MeetingSession) -> bool:
        """Send Athena bot to join the meeting via Vexa API with proper session management"""
        try:
            session.status = MeetingStatus.BOT_JOINING
            
            # First, check if bot is already active in this meeting
            if self._verify_bot_active(session):
                self.logger.info(f"Bot already active in meeting {session.meeting_id}")
                session.status = MeetingStatus.IN_PROGRESS
                return True
            
            # If there's an existing bot session that's not active, clean it up
            if session.bot_session_id:
                self.logger.info(f"Cleaning up inactive bot session: {session.bot_session_id}")
                await self._delete_bot(session)
                session.bot_session_id = None
                await asyncio.sleep(2)  # Wait for cleanup
            
            # Wait for join delay
            await asyncio.sleep(self.config["bot"]["join_delay"])
            
            # Create bot via Vexa API using the correct authentication method
            api_key = self.config["vexa"]["api_key"]
            
            payload = {
                "platform": "google_meet",
                "meeting_url": session.google_meet_url,
                "native_meeting_id": session.google_meet_id,
                "webhook_url": self.config["webhook"]["url"],
                "name": self.config["bot"]["name"],
                "wait_for_host": False,  # Don't wait for host, join immediately
                "auto_leave_on_empty": False,  # Don't auto-leave, stay persistent
                "wait_for_admission": True,  # Wait for manual admission
                "admission_timeout": 600,  # Wait up to 10 minutes for admission
                "persistent": True,  # Stay in waiting room until admitted
                "retry_on_disconnect": True  # Retry if disconnected
            }
            
            headers = {
                'X-API-Key': api_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{self.config['vexa']['base_url']}/bots",
                headers=headers,
                json=payload,
                timeout=self.config["vexa"]["timeout"]
            )
            
            if response.status_code in [200, 201]:
                bot_data = response.json()
                session.bot_session_id = bot_data.get("id", bot_data.get("bot_id"))
                
                self.logger.info(f"Bot created and waiting for admission: {session.meeting_id} with bot_id: {session.bot_session_id}")
                
                # Start monitoring admission immediately (don't block)
                asyncio.create_task(self._monitor_bot_admission(session))
                
                # Mark as joining and let the monitoring handle the rest
                session.status = MeetingStatus.BOT_JOINING
                self.logger.info(f"🔄 Bot created, monitoring admission status...")
                
                return True  # Return success immediately, monitor in background
            elif response.status_code == 409:
                # Bot already exists, try to get existing bot info
                self.logger.warning(f"Bot already exists for meeting {session.google_meet_id}, attempting to verify")
                if self._verify_bot_active(session):
                    session.status = MeetingStatus.IN_PROGRESS
                    return True
                else:
                    raise Exception(f"Bot exists but not active: {response.text}")
            else:
                raise Exception(f"Vexa API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            session.status = MeetingStatus.FAILED
            session.error_message = str(e)
            self.logger.error(f"Failed to join meeting {session.meeting_id}: {e}")
            return False
    
    async def _monitor_transcript(self, session: MeetingSession):
        """Monitor and retrieve transcript from Vexa API"""
        poll_interval = self.config["bot"]["transcript_poll_interval"]
        
        while session.status == MeetingStatus.IN_PROGRESS:
            try:
                # Check if meeting has ended (simple time-based check)
                if datetime.now() > session.start_time + timedelta(hours=2):  # Max 2 hour meeting
                    break
                
                # Poll for transcript
                headers = {'X-API-Key': self.config["vexa"]["api_key"]}
                
                response = requests.get(
                    f"{self.config['vexa']['base_url']}/v1/transcripts/google_meet/{session.google_meet_id}",
                    headers=headers,
                    timeout=self.config["vexa"]["timeout"]
                )
                
                if response.status_code == 200:
                    transcript_data = response.json()
                    if transcript_data and transcript_data.get("transcript"):
                        session.transcript = transcript_data["transcript"]
                        self.logger.info(f"Retrieved transcript for meeting: {session.meeting_id}")
                
                await asyncio.sleep(poll_interval)
                
            except Exception as e:
                self.logger.error(f"Error monitoring transcript for {session.meeting_id}: {e}")
                await asyncio.sleep(poll_interval)
        
        # Meeting ended, finalize transcript
        await self._finalize_meeting(session)
    
    async def _finalize_meeting(self, session: MeetingSession):
        """Finalize meeting and deliver transcript via webhook"""
        try:
            session.end_time = datetime.now()
            session.status = MeetingStatus.COMPLETED
            
            # Get final transcript
            if not session.transcript:
                await self._get_final_transcript(session)
            
            # Deliver via webhook
            await self._deliver_transcript_webhook(session)
            
            self.logger.info(f"Meeting finalized: {session.meeting_id}")
            
        except Exception as e:
            session.status = MeetingStatus.FAILED
            session.error_message = str(e)
            self.logger.error(f"Failed to finalize meeting {session.meeting_id}: {e}")
    
    async def _get_final_transcript(self, session: MeetingSession):
        """Get final complete transcript from Vexa API"""
        try:
            headers = {'X-API-Key': self.config["vexa"]["api_key"]}
            
            response = requests.get(
                f"{self.config['vexa']['base_url']}/v1/transcripts/google_meet/{session.google_meet_id}",
                headers=headers,
                timeout=self.config["vexa"]["timeout"]
            )
            
            if response.status_code == 200:
                transcript_data = response.json()
                session.transcript = transcript_data.get("transcript", "No transcript available")
            else:
                session.transcript = f"Error retrieving transcript: {response.status_code}"
                
        except Exception as e:
            session.transcript = f"Error retrieving transcript: {str(e)}"
            self.logger.error(f"Failed to get final transcript for {session.meeting_id}: {e}")
    
    async def _deliver_transcript_webhook(self, session: MeetingSession):
        """Deliver transcript to configured webhook with retries"""
        webhook_config = self.config["webhook"]
        max_retries = webhook_config["retry_attempts"]
        
        payload = {
            "meeting_id": session.meeting_id,
            "google_meet_url": session.google_meet_url,
            "start_time": session.start_time.isoformat(),
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "transcript": session.transcript,
            "bot_name": self.config["bot"]["name"],
            "status": session.status.value,
            "timestamp": datetime.now().isoformat()
        }
        
        headers = {'Content-Type': 'application/json'}
        if webhook_config.get("secret"):
            headers['X-Webhook-Secret'] = webhook_config["secret"]
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    webhook_config["url"],
                    headers=headers,
                    json=payload,
                    timeout=webhook_config["timeout"]
                )
                
                if response.status_code == 200:
                    self.logger.info(f"Transcript delivered successfully for meeting: {session.meeting_id}")
                    return
                else:
                    raise Exception(f"Webhook responded with status: {response.status_code}")
                    
            except Exception as e:
                self.logger.warning(f"Webhook delivery attempt {attempt + 1} failed for {session.meeting_id}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    self.logger.error(f"All webhook delivery attempts failed for {session.meeting_id}")
    
    def schedule_daily_standups(self):
        """Schedule daily standup meetings"""
        standup_time = self.config["meeting"]["standup_time"]
        
        def run_daily_standup():
            # Synchronous workflow to avoid asyncio conflicts
            self._daily_standup_workflow_sync()
        
        schedule.every().day.at(standup_time).do(run_daily_standup)
        
        self.logger.info(f"Scheduled daily standups at {standup_time} (every day)")
    
    def _daily_standup_workflow_sync(self):
        """Synchronous workflow for daily standup - directly join constant meeting"""
        try:
            # Get constant meeting info
            constant_url = self.config["meeting"].get("constant_meeting_url")
            constant_id = self.config["meeting"].get("constant_meeting_id")
            
            if not constant_url or not constant_id:
                self.logger.error("No constant meeting URL configured")
                return
                
            self.logger.info(f"Time trigger: joining constant meeting {constant_url}")
            
            # Direct API call to join meeting
            api_key = self.config["vexa"]["api_key"]
            webhook_url = self.config["webhook"]["url"]
            
            payload = {
                "platform": "google_meet",
                "meeting_url": constant_url,
                "native_meeting_id": constant_id,
                "webhook_url": webhook_url,
                "name": self.config["bot"]["name"]
            }
            
            response = requests.post(
                f"{self.config['vexa']['base_url']}/bots",
                headers={'X-API-Key': api_key, 'Content-Type': 'application/json'},
                json=payload,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                bot_data = response.json()
                self.logger.info(f"✅ Bot successfully joined meeting: {bot_data.get('id')}")
                self.logger.info(f"Meeting URL: {constant_url}")
            else:
                self.logger.error(f"Failed to join meeting: {response.status_code} - {response.text}")
                
        except Exception as e:
            self.logger.error(f"Failed to join standup meeting: {e}")
    
    async def _daily_standup_workflow(self):
        """Complete workflow for daily standup"""
        try:
            # Create meeting
            session = await self.create_daily_standup()
            if not session:
                self.logger.error("Failed to create daily standup meeting")
                return
            
            # Schedule bot to join meeting
            asyncio.create_task(self._schedule_bot_join(session))
            
        except Exception as e:
            self.logger.error(f"Daily standup workflow failed: {e}")
    
    async def create_bulk_meetings(self, days: int = 7):
        """Create meetings for next N days"""
        created_meetings = []
        
        for i in range(days):
            date = datetime.now() + timedelta(days=i)
            try:
                session = await self.create_daily_standup(date)
                if session:
                    created_meetings.append(session)
                    self.logger.info(f"Created meeting {i+1}/{days}: {session.google_meet_url}")
                    print(f"✅ Day {i+1}: {session.google_meet_url} (Bot joins at {session.start_time})")
                    # Schedule bot to join at meeting start time
                    asyncio.create_task(self._schedule_bot_join(session))
                else:
                    print(f"❌ Day {i+1}: Failed to create meeting")
            except Exception as e:
                self.logger.error(f"Failed to create meeting for day {i+1}: {e}")
                print(f"❌ Day {i+1}: Error - {e}")
        
        print(f"\n🎉 Created {len(created_meetings)} meetings for next {days} days")
        return created_meetings
    
    async def delete_all_standup_meetings(self):
        """Delete all standup meetings from calendar"""
        if not self.google_service:
            print("❌ Google Calendar service not available")
            return
        
        try:
            # Get events for next 30 days
            now = datetime.now()
            time_min = now.isoformat() + '+05:30'  # IST timezone
            time_max = (now + timedelta(days=30)).isoformat() + '+05:30'
            
            events_result = self.google_service.events().list(
                calendarId=self.config["google"]["calendar_id"],
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            deleted_count = 0
            
            print("🗑️  Searching for standup meetings to delete...")
            
            for event in events:
                summary = event.get('summary', '').lower()
                # Delete events that contain "standup" in title or have Google Meet links
                if 'standup' in summary or event.get('hangoutLink'):
                    try:
                        self.google_service.events().delete(
                            calendarId=self.config["google"]["calendar_id"],
                            eventId=event['id']
                        ).execute()
                        
                        deleted_count += 1
                        event_time = event.get('start', {}).get('dateTime', 'Unknown time')
                        print(f"🗑️  Deleted: {event.get('summary', 'Untitled')} at {event_time}")
                        
                    except Exception as e:
                        print(f"❌ Failed to delete event: {event.get('summary', 'Untitled')} - {e}")
            
            print(f"\n✅ Deleted {deleted_count} standup meetings")
            
        except Exception as e:
            print(f"❌ Failed to delete meetings: {e}")
            self.logger.error(f"Failed to delete meetings: {e}")
    
    async def _schedule_bot_join(self, session: MeetingSession):
        """Schedule bot to join meeting at start time"""
        now = datetime.now()
        if session.start_time > now:
            wait_seconds = (session.start_time - now).total_seconds()
            await asyncio.sleep(wait_seconds)
        
        await self.join_meeting_with_athena(session)
    
    def get_session_status(self, meeting_id: str) -> Optional[Dict]:
        """Get status of a specific meeting session"""
        session = self._active_sessions.get(meeting_id)
        if not session:
            return None
        
        return {
            "meeting_id": session.meeting_id,
            "google_meet_url": session.google_meet_url,
            "start_time": session.start_time.isoformat(),
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "status": session.status.value,
            "has_transcript": bool(session.transcript),
            "error_message": session.error_message,
            "retry_count": session.retry_count
        }
    
    def run_scheduler(self):
        """Run the meeting scheduler with session monitoring"""
        self.logger.info("Starting Athena meeting scheduler...")
        
        # Get target time
        standup_time = self.config["meeting"]["standup_time"]
        target_hour, target_minute = map(int, standup_time.split(':'))
        
        self.logger.info(f"Monitoring for standup at {standup_time}")
        
        meeting_created = False
        
        while True:
            try:
                now = datetime.now()
                current_hour = now.hour
                current_minute = now.minute
                
                # Check if it's time for the meeting
                if (current_hour == target_hour and current_minute == target_minute and not meeting_created):
                    self.logger.info(f"Time trigger activated: {now.strftime('%H:%M:%S')}")
                    self._daily_standup_workflow_sync()
                    meeting_created = True
                
                # Reset flag for next day
                elif current_hour != target_hour or current_minute != target_minute:
                    meeting_created = False
                
                # Check for pending joins
                self._check_pending_joins()
                
                time.sleep(5)  # Check every 5 seconds for accuracy
                
            except KeyboardInterrupt:
                self.logger.info("Scheduler stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Scheduler error: {e}")
                time.sleep(10)
    
    def _check_pending_joins(self):
        """Check for sessions that need bot joining with fault tolerance"""
        now = datetime.now()
        
        for session_id, session in list(self._active_sessions.items()):
            # Process sessions that should be joined (at or after start time, within 10 minutes)
            if (session.status == MeetingStatus.CREATED and 
                session.start_time <= now and
                (now - session.start_time).total_seconds() < 600):  # Extended to 10 minutes
                
                # Check if bot is already active in meeting
                if self._verify_bot_active(session):
                    session.status = MeetingStatus.IN_PROGRESS
                    self._save_sessions()
                    self.logger.info(f"Bot verified active in meeting: {session_id}")
                    continue
                
                # Join immediately when it's time - don't wait for users
                self.logger.info(f"Meeting start time reached, joining immediately: {session_id}")
                self.logger.info(f"Meeting URL: {session.google_meet_url}")
                
                try:
                    # Use async join with proper session management
                    asyncio.create_task(self._join_with_retry(session))
                        
                except Exception as e:
                    self.logger.error(f"Failed to schedule join for meeting {session_id}: {e}")
            
            # Clean up old sessions (older than 2 hours)
            elif (session.start_time < now - timedelta(hours=2)):
                self.logger.info(f"Cleaning up old session: {session_id}")
                if session.bot_session_id:
                    try:
                        asyncio.create_task(self._delete_bot(session))
                    except Exception as e:
                        self.logger.debug(f"Error cleaning up bot: {e}")
                del self._active_sessions[session_id]
                self._save_sessions()
    
    def _join_meeting_sync(self, session: MeetingSession):
        """Synchronous meeting join with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Delete any existing bot first
                self._delete_bot_sync(session)
                time.sleep(2)
                
                # Join with fresh bot
                bot_data = self._create_bot_sync(session)
                if bot_data and bot_data.get("status") == "active":
                    session.bot_session_id = bot_data["id"]
                    session.status = MeetingStatus.IN_PROGRESS
                    self._save_sessions()
                    self.logger.info(f"Successfully joined meeting: {session.meeting_id}")
                    return
                    
            except Exception as e:
                self.logger.warning(f"Join attempt {attempt + 1} failed: {e}")
                time.sleep(5)
        
        self.logger.error(f"Failed to join meeting after {max_retries} attempts: {session.meeting_id}")
    
    def _create_bot_sync(self, session: MeetingSession) -> dict:
        """Create bot synchronously"""
        api_key = self.config["vexa"]["api_key"]
        webhook_url = self.config["webhook"]["url"]
        
        payload = {
            "platform": "google_meet",
            "meeting_url": session.google_meet_url,
            "native_meeting_id": session.google_meet_id,
            "webhook_url": webhook_url,
            "name": self.config["bot"]["name"],
            "wait_for_host": False,
            "auto_leave_on_empty": True
        }
        
        response = requests.post(
            f"{self.config['vexa']['base_url']}/bots",
            headers={'X-API-Key': api_key, 'Content-Type': 'application/json'},
            json=payload,
            timeout=30
        )
        
        if response.status_code in [200, 201]:  # Both 200 and 201 are success
            return response.json()
        else:
            raise Exception(f"API error: {response.status_code} - {response.text}")
    
    def _delete_bot_sync(self, session: MeetingSession):
        """Delete bot synchronously"""
        try:
            api_key = self.config["vexa"]["api_key"]
            response = requests.delete(
                f"{self.config['vexa']['base_url']}/bots/google_meet/{session.google_meet_id}",
                headers={'X-API-Key': api_key},
                timeout=10
            )
            if response.status_code in [200, 404]:  # 404 means already deleted
                self.logger.info(f"Bot deleted from meeting {session.meeting_id}")
        except Exception as e:
            self.logger.warning(f"Failed to delete bot: {e}")
    
    def _verify_bot_active(self, session: MeetingSession) -> bool:
        """Verify if bot is actually active in meeting"""
        try:
            api_key = self.config["vexa"]["api_key"]
            headers = {'X-API-Key': api_key}
            
            # Check bot status via API - try different endpoints
            endpoints = [
                f"/bots/google_meet/{session.google_meet_id}",
                f"/bots/{session.google_meet_id}",
                "/bots"
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.get(
                        f"{self.config['vexa']['base_url']}{endpoint}",
                        headers=headers,
                        timeout=5
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Handle different response formats
                        bots = data if isinstance(data, list) else [data]
                        
                        for bot_data in bots:
                            # Check if this bot matches our meeting
                            if (bot_data.get("native_meeting_id") == session.google_meet_id or
                                bot_data.get("meeting_id") == session.google_meet_id):
                                
                                if bot_data.get("status") in ["active", "in_meeting", "connected"]:
                                    session.bot_session_id = bot_data.get("id", bot_data.get("bot_id"))
                                    self.logger.debug(f"Found active bot: {session.bot_session_id}")
                                    return True
                        
                        # If we got a successful response from /bots endpoint, we found all bots
                        if endpoint == "/bots":
                            break
                            
                except requests.RequestException:
                    continue
            
        except Exception as e:
            self.logger.debug(f"Bot verification failed: {e}")
        
        return False
    
    async def _monitor_bot_admission(self, session: MeetingSession):
        """Continuously monitor bot admission status and handle reconnection"""
        start_time = datetime.now()
        check_interval = 5  # Check every 5 seconds
        max_monitoring_time = 600  # Monitor for up to 10 minutes
        reconnect_attempts = 0
        max_reconnect_attempts = 5
        
        self.logger.info(f"🔄 Starting persistent admission monitoring...")
        
        while (datetime.now() - start_time).total_seconds() < max_monitoring_time:
            try:
                # Check if bot is active
                if self._verify_bot_active(session):
                    session.status = MeetingStatus.IN_PROGRESS
                    self.logger.info(f"✅ Bot successfully admitted and active!")
                    
                    # Start transcript monitoring
                    asyncio.create_task(self._monitor_transcript(session))
                    return
                
                # Check detailed bot status
                api_key = self.config["vexa"]["api_key"]
                headers = {'X-API-Key': api_key}
                
                response = requests.get(
                    f"{self.config['vexa']['base_url']}/bots/{session.bot_session_id}",
                    headers=headers,
                    timeout=5
                )
                
                if response.status_code == 200:
                    bot_data = response.json()
                    status = bot_data.get("status", "").lower()
                    
                    if status in ["active", "in_meeting", "connected", "admitted"]:
                        session.status = MeetingStatus.IN_PROGRESS
                        self.logger.info(f"✅ Bot admitted with status: {status}")
                        asyncio.create_task(self._monitor_transcript(session))
                        return
                    elif status in ["waiting_for_admission", "pending", "waiting"]:
                        elapsed = int((datetime.now() - start_time).total_seconds())
                        self.logger.info(f"⏳ Bot waiting for admission... ({elapsed}s elapsed)")
                    elif status in ["failed", "error", "disconnected", "left"]:
                        self.logger.warning(f"⚠️ Bot disconnected with status: {status}")
                        
                        # Try to reconnect if we haven't exceeded max attempts
                        if reconnect_attempts < max_reconnect_attempts:
                            reconnect_attempts += 1
                            self.logger.info(f"🔄 Attempting reconnection {reconnect_attempts}/{max_reconnect_attempts}")
                            
                            # Delete old bot and create new one
                            await self._delete_bot(session)
                            await asyncio.sleep(3)
                            
                            # Recreate the bot
                            success = await self.join_meeting_with_athena(session)
                            if success:
                                return  # New monitoring will start
                        else:
                            self.logger.error(f"❌ Max reconnection attempts exceeded")
                            session.status = MeetingStatus.FAILED
                            return
                
            except Exception as e:
                self.logger.debug(f"Error in admission monitoring: {e}")
            
            await asyncio.sleep(check_interval)
        
        self.logger.warning(f"⏰ Bot admission monitoring timeout after {max_monitoring_time}s")
        session.status = MeetingStatus.FAILED
    
    async def _join_with_retry(self, session: MeetingSession, max_retries: int = 5):
        """Join meeting with retry logic and fault tolerance"""
        for attempt in range(max_retries):
            try:
                # If bot appears to be in meeting, verify it's actually active
                if self._verify_bot_active(session):
                    self.logger.info(f"Bot already active in meeting {session.meeting_id}")
                    session.status = MeetingStatus.IN_PROGRESS
                    self._save_sessions()
                    return True
                
                # If previous bot exists but not active, delete it first
                if session.bot_session_id:
                    await self._delete_bot(session)
                    session.bot_session_id = None
                
                # Attempt to join
                success = await self.join_meeting_with_athena(session)
                
                if success:
                    # Double-check bot is active within 10 seconds
                    for check in range(10):
                        await asyncio.sleep(1)
                        if self._verify_bot_active(session):
                            self.logger.info(f"Bot successfully active in meeting {session.meeting_id}")
                            return True
                    
                    self.logger.warning(f"Bot joined but not verified as active: {session.meeting_id}")
                else:
                    self.logger.warning(f"Join attempt {attempt + 1} failed for {session.meeting_id}")
                
            except Exception as e:
                self.logger.error(f"Join retry {attempt + 1} failed: {e}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(2)  # Wait before retry
        
        self.logger.error(f"Failed to join meeting after {max_retries} attempts: {session.meeting_id}")
        return False
    
    async def _delete_bot(self, session: MeetingSession):
        """Delete existing bot from meeting"""
        try:
            api_key = self.config["vexa"]["api_key"]
            headers = {'X-API-Key': api_key}
            
            response = requests.delete(
                f"{self.config['vexa']['base_url']}/bots/google_meet/{session.google_meet_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 202, 404]:  # 404 means already deleted
                self.logger.info(f"Previous bot deleted from meeting {session.meeting_id}")
            
        except Exception as e:
            self.logger.debug(f"Bot deletion failed (may not exist): {e}")


# CLI and utility functions
async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Athena Meeting Bot')
    parser.add_argument('--config', default='athena_config.json', help='Configuration file path')
    parser.add_argument('--mode', choices=['scheduler', 'test', 'create', 'bulk', 'join', 'delete-all', 'status'], default='scheduler',
                       help='Operation mode')
    parser.add_argument('--meeting-url', help='Google Meet URL for test/join mode')
    
    args = parser.parse_args()
    
    # Initialize bot
    bot = AthenaMeetBot(args.config)
    
    if args.mode == 'scheduler':
        # Run scheduled mode
        bot.schedule_daily_standups()
        bot.run_scheduler()
    
    elif args.mode == 'create':
        # Create a test meeting and schedule bot to join at start time
        session = await bot.create_daily_standup()
        if session:
            print(f"Created meeting: {session.google_meet_url}")
            print(f"Bot will join at: {session.start_time}")
            # Schedule bot to join at meeting start time
            asyncio.create_task(bot._schedule_bot_join(session))
            # Keep running to wait for the scheduled join
            await asyncio.sleep(3600)  # Wait up to 1 hour
    
    elif args.mode == 'bulk':
        # Create meetings for next 7 days
        print("🚀 Creating meetings for next 7 days...")
        await bot.create_bulk_meetings(7)
    
    elif args.mode == 'delete-all':
        # Delete all standup meetings
        print("⚠️  This will delete ALL standup meetings from your calendar!")
        confirm = input("Are you sure? (yes/no): ")
        if confirm.lower() == 'yes':
            await bot.delete_all_standup_meetings()
        else:
            print("❌ Cancelled")
    
    elif args.mode == 'test':
        # Test mode with existing meeting URL
        if not args.meeting_url:
            print("--meeting-url required for test mode")
            return
        
        meet_id = args.meeting_url.split('/')[-1]
        session = MeetingSession(
            meeting_id=str(uuid.uuid4()),
            google_meet_url=args.meeting_url,
            google_meet_id=meet_id,
            start_time=datetime.now(),
            end_time=None,
            status=MeetingStatus.CREATED
        )
        
        await bot.join_meeting_with_athena(session)
    
    elif args.mode == 'status':
        # Show active sessions and their status
        print("📊 ACTIVE SESSIONS:")
        print("=" * 50)
        
        if not bot._active_sessions:
            print("No active sessions found")
        else:
            for session_id, session in bot._active_sessions.items():
                print(f"Session ID: {session_id}")
                print(f"Meeting URL: {session.google_meet_url}")
                print(f"Start Time: {session.start_time}")
                print(f"Status: {session.status.value}")
                print(f"Bot Joined: {'Yes' if session.bot_session_id else 'No'}")
                
                # Check if it's time to join
                if session.start_time <= datetime.now() and not session.bot_session_id:
                    print("🚨 READY TO JOIN!")
                    answer = input("Join now? (y/n): ")
                    if answer.lower() == 'y':
                        await bot.join_meeting_with_athena(session)
                
                print("-" * 30)


if __name__ == "__main__":
    asyncio.run(main())