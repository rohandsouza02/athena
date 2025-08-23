#!/usr/bin/env python3
"""
Minimal Webhook Server for Vexa Transcript Processing
Receives webhook -> Fetches transcript -> Cleans -> Outputs
"""

import requests
import time
from datetime import datetime
from flask import Flask, request, jsonify
from transcript_processor import process_transcript

app = Flask(__name__)

# Vexa API Configuration
VEXA_API_KEY = "Hp1CVO4z4NOmzsj22rEQmop4w72GnzN9kXCRoNws"
VEXA_BASE_URL = "https://gateway.dev.vexa.ai"

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

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "service": "Minimal Vexa Webhook Server",
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
        print(f"📨 VEXA WEBHOOK RECEIVED")
        print(f"{'='*80}")
        print(f"Meeting ID: {meeting_id}")
        print(f"Status: {status}")
        print(f"Start Time: {start_time}")
        print(f"{'='*80}")
        
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
            
            return jsonify({
                "status": "success",
                "message": "Transcript processed successfully",
                "meeting_id": meeting_id,
                "output_file": filename,
                "unix_timestamp": unix_timestamp,
                "processed_at": datetime.now().isoformat()
            })
            
        except Exception as e:
            print(f"❌ Error processing transcript: {e}")
            return jsonify({"error": f"Failed to process transcript: {str(e)}"}), 500
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({"error": f"Webhook processing failed: {str(e)}"}), 500

if __name__ == '__main__':
    print("🤖 Minimal Vexa Webhook Server Starting...")
    print(f"Health check: http://localhost:8080/")
    print(f"Webhook endpoint: http://localhost:8080/transcript")
    print(f"Vexa API: {VEXA_BASE_URL}")
    print("\n🔄 Workflow:")
    print("1. Receive Vexa webhook with meeting ID")
    print("2. Fetch full transcript from Vexa API")
    print("3. Clean and process transcript")
    print("4. Output cleaned transcript with date")
    print("\nStarting server on 0.0.0.0:8080")
    
    app.run(host='0.0.0.0', port=8080, debug=False) 