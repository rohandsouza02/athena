#!/usr/bin/env python3
"""
Vexa Webhook Server with Transcript Processing
Complete solution for receiving Vexa webhooks and processing transcripts

Usage:
    python vexa_webhook_server.py

Features:
- Receives Vexa webhooks with meeting IDs
- Fetches transcripts from Vexa API
- Cleans and processes transcripts
- Saves to Unix timestamp files
- Retry logic for incomplete meetings

Requirements:
    pip install flask requests
"""

import requests
import time
from datetime import datetime
from typing import Dict, Any
from flask import Flask, request, jsonify

app = Flask(__name__)

# Vexa API Configuration
VEXA_API_KEY = "Hp1CVO4z4NOmzsj22rEQmop4w72GnzN9kXCRoNws"
VEXA_BASE_URL = "https://gateway.dev.vexa.ai"

# Standup Server Configuration
STANDUP_SERVER_URL = "http://localhost:3000/standup"  # Change this to your server URL


def process_transcript(json_data: Dict[str, Any]) -> str:
    """
    Convert segments from Vexa API output into a single readable transcript
    
    Args:
        json_data: The JSON data containing segments
    
    Returns:
        Formatted transcript as a string
    """
    
    # Extract meeting metadata
    start_time = json_data.get('start_time', 'Unknown')
    
    # Initialize transcript
    transcript_lines = []
    transcript_lines.append(f"Meeting Date/Time: {start_time}")
    transcript_lines.append("")
    
    # Process segments
    segments = json_data.get('segments', [])
    
    # Sort segments by start time to ensure chronological order
    sorted_segments = sorted(segments, key=lambda x: x.get('start', 0))
    
    # Collect all text parts
    all_text_parts = []
    
    for segment in sorted_segments:
        text = segment.get('text', '').strip()
        
        # Skip empty text segments
        if not text:
            continue
            
        all_text_parts.append(text)
    
    # Combine all text and clean it
    if all_text_parts:
        combined_text = ' '.join(all_text_parts)
        cleaned_text = clean_text(combined_text)
        transcript_lines.append(cleaned_text)
    
    return '\n'.join(transcript_lines)


def clean_text(text: str) -> str:
    """
    Clean up transcript text by removing duplicates and formatting
    
    Args:
        text: Raw combined text
        
    Returns:
        Cleaned text
    """
    # Split into sentences and remove near-duplicates
    sentences = text.split('.')
    cleaned_sentences = []
    
    for sentence in sentences:
        sentence = sentence.strip()
        if sentence and sentence not in cleaned_sentences:
            # Check for similar sentences (simple approach)
            is_duplicate = False
            for existing in cleaned_sentences:
                if len(sentence) > 10 and sentence in existing:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                cleaned_sentences.append(sentence)
    
    return '. '.join(cleaned_sentences).strip()


def fetch_transcript_from_vexa(meeting_id: str) -> dict:
    """Fetch transcript from Vexa API using meeting ID"""
    try:
        headers = {'X-API-Key': VEXA_API_KEY}
        url = f"{VEXA_BASE_URL}/transcripts/google_meet/{meeting_id}"
        
        print(f"🔍 Fetching transcript from: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ API Error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error fetching transcript: {e}")
        return None


def send_to_standup_server(transcript: str, meeting_id: str) -> bool:
    """Send cleaned transcript to standup server"""
    try:
        payload = {"transcript": transcript}
        headers = {"Content-Type": "application/json"}
        
        print(f"📤 Sending transcript to standup server: {STANDUP_SERVER_URL}")
        response = requests.post(
            STANDUP_SERVER_URL,
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Successfully sent transcript to standup server")
            return True
        else:
            print(f"❌ Standup server error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending to standup server: {e}")
        return False


@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "service": "Vexa Webhook Server",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/transcript', methods=['POST'])
def receive_webhook():
    """Receive Vexa webhook and process transcript"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Extract meeting ID from Vexa webhook
        meeting_id = data.get('native_meeting_id')
        status = data.get('status')
        start_time = data.get('start_time')
        
        print(f"\n{'='*80}")
        print("📨 VEXA WEBHOOK RECEIVED")
        print("="*80)
        print(f"Meeting ID: {meeting_id}")
        print(f"Status: {status}")
        print(f"Start Time: {start_time}")
        print("="*80)
        
        if not meeting_id:
            print("❌ No meeting ID found in webhook")
            return jsonify({"error": "No meeting ID provided"}), 400
        
        if status != 'completed':
            print(f"⏳ Meeting not completed yet (status: {status}), retrying...")
            
            # Retry up to 3 times with 10-second delays
            for attempt in range(3):
                print(f"🔄 Retry attempt {attempt + 1}/3 - waiting 10 seconds...")
                time.sleep(10)
                
                # Re-fetch the webhook data to check status
                transcript_data = fetch_transcript_from_vexa(meeting_id)
                if transcript_data and transcript_data.get('status') == 'completed':
                    print(f"✅ Meeting completed on attempt {attempt + 1}")
                    status = 'completed'
                    break
                else:
                    print(f"❌ Attempt {attempt + 1} failed - status still not completed")
            
            if status != 'completed':
                print("❌ All retry attempts failed - meeting still not completed")
                return jsonify({
                    "status": "failed", 
                    "message": "Meeting not completed after retries"
                })
        
        # Fetch transcript from Vexa API
        print(f"📥 Fetching transcript for meeting: {meeting_id}")
        transcript_data = fetch_transcript_from_vexa(meeting_id)
        
        if not transcript_data:
            print("❌ Failed to fetch transcript from Vexa API")
            return jsonify({"error": "Failed to fetch transcript"}), 500
        
        # Process and clean transcript
        print("🧹 Processing and cleaning transcript...")
        try:
            cleaned_transcript = process_transcript(transcript_data)
            
            print(f"\n{'='*80}")
            print("✅ CLEANED TRANSCRIPT OUTPUT")
            print("="*80)
            print(f"Meeting ID: {meeting_id}")
            print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*80)
            print(cleaned_transcript)
            print("="*80 + "\n")
            
            # Save just the transcript string to file with Unix timestamp
            unix_timestamp = int(time.time())
            filename = f"{unix_timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(cleaned_transcript)
            
            print(f"💾 Transcript saved to: {filename}")
            
            # Send transcript to standup server
            standup_success = send_to_standup_server(cleaned_transcript, meeting_id)
            
            return jsonify({
                "status": "success",
                "message": "Transcript processed successfully",
                "meeting_id": meeting_id,
                "output_file": filename,
                "unix_timestamp": unix_timestamp,
                "standup_sent": standup_success,
                "processed_at": datetime.now().isoformat()
            })
            
        except Exception as e:
            print(f"❌ Error processing transcript: {e}")
            return jsonify({"error": f"Failed to process transcript: {str(e)}"}), 500
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({"error": f"Webhook processing failed: {str(e)}"}), 500


if __name__ == '__main__':
    print("🤖 Vexa Webhook Server Starting...")
    print(f"Health check: http://localhost:8080/")
    print(f"Webhook endpoint: http://localhost:8080/transcript")
    print(f"Vexa API: {VEXA_BASE_URL}")
    print("\n🔄 Workflow:")
    print("1. Receive Vexa webhook with meeting ID")
    print("2. Fetch full transcript from Vexa API")
    print("3. Clean and process transcript")
    print("4. Output cleaned transcript with Unix timestamp filename")
    print("\n📋 Features:")
    print("- Retry logic: 3 attempts with 10-second delays")
    print("- Output format: {unix_timestamp}.txt with clean transcript")
    print("- API Key configured for Vexa gateway")
    print("\nStarting server on 0.0.0.0:8080")
    
    app.run(host='0.0.0.0', port=8080, debug=False) 