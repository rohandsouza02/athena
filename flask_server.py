#!/usr/bin/env python3
from flask import Flask, request, jsonify
import threading
import tempfile
import time
import requests
from datetime import datetime
from typing import Dict, Any
import os
from standup_automation import StandupAutomation
from sprint_report_generator import SprintReportGenerator

app = Flask(__name__)

# Vexa API Configuration
VEXA_API_KEY = "Hp1CVO4z4NOmzsj22rEQmop4w72GnzN9kXCRoNws"
VEXA_BASE_URL = "https://gateway.dev.vexa.ai"


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


def fetch_transcript_from_vexa(meeting_id: str):
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


def run_standup_automation_async(transcript_content):
    """Run standup automation in a separate thread"""
    try:
        # Create a temporary file for the transcript
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            temp_file.write(transcript_content)
            temp_file_path = temp_file.name
        
        # Initialize and run automation
        automation = StandupAutomation(config_path='config.json')
        success = automation.run_automation(transcript_path=temp_file_path)
        
        # Clean up temp file
        os.unlink(temp_file_path)
        
        if success:
            print("✅ Standup automation completed successfully")
        else:
            print("❌ Standup automation failed")
            
    except Exception as e:
        print(f"Error in async standup automation: {e}")


def run_sprint_report_async():
    """Run sprint report generation in a separate thread"""
    try:
        generator = SprintReportGenerator(config_path='config.json')
        output_path = generator.generate_report()
        
        if output_path:
            print(f"✅ Sprint report generated successfully: {output_path}")
        else:
            print("❌ Sprint report generation failed")
            
    except Exception as e:
        print(f"Error in async sprint report generation: {e}")


@app.route('/standup', methods=['POST'])
def process_standup():
    try:
        # Get transcript from request body
        data = request.get_json()
        
        if not data or 'transcript' not in data:
            return jsonify({'error': 'Missing transcript in request body'}), 400
        
        transcript = data['transcript']
        
        if not transcript.strip():
            return jsonify({'error': 'Empty transcript provided'}), 400
        
        # Start standup automation in background thread
        thread = threading.Thread(
            target=run_standup_automation_async, 
            args=(transcript,),
            daemon=True
        )
        thread.start()
        
        # Return 200 immediately
        return jsonify({
            'status': 'success',
            'message': 'Standup automation started successfully'
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/transcript', methods=['POST'])
def receive_vexa_webhook():
    """Receive Vexa webhook, process transcript, and trigger standup automation"""
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
            
            # Save transcript to file with Unix timestamp
            unix_timestamp = int(time.time())
            filename = f"{unix_timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(cleaned_transcript)
            
            print(f"💾 Transcript saved to: {filename}")
            
            # Call standup automation directly with cleaned transcript
            print("🚀 Starting standup automation...")
            thread = threading.Thread(
                target=run_standup_automation_async,
                args=(cleaned_transcript,),
                daemon=True
            )
            thread.start()
            
            return jsonify({
                "status": "success",
                "message": "Transcript processed and standup automation started",
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


@app.route('/sprint-report', methods=['POST'])
def process_sprint_report():
    try:
        # Get request data
        data = request.get_json()
        
        if not data or 'sprint_comp' not in data:
            return jsonify({'error': 'Missing sprint_comp in request body'}), 400
        
        sprint_comp = data['sprint_comp']
        
        if not sprint_comp:
            return jsonify({'error': 'sprint_comp must be True'}), 400
        
        # Start sprint report generation in background thread
        thread = threading.Thread(
            target=run_sprint_report_async,
            daemon=True
        )
        thread.start()
        
        # Return 200 immediately
        return jsonify({
            'status': 'success',
            'message': 'Sprint report generation started successfully'
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200


if __name__ == '__main__':