#!/usr/bin/env python3
"""
Simple webhook server for testing Athena bot transcript delivery
"""

import json
import hmac
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify
import os

app = Flask(__name__)


def verify_webhook_signature(payload: bytes, signature: str,
                             secret: str) -> bool:
    """Verify webhook signature for security"""
    if not secret or not signature:
        return True  # Skip verification if not configured
    
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    # Handle both "sha256=..." and plain hex formats
    if signature.startswith('sha256='):
        signature = signature[7:]
    
    return hmac.compare_digest(expected_signature, signature)


@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "service": "Athena Webhook Server",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/transcript', methods=['POST'])
def receive_transcript():
    """Receive transcript from Athena bot"""
    try:
        # LOG ALL RAW DATA FIRST
        print(f"\n{'='*80}")
        print("🔍 RAW WEBHOOK DATA RECEIVED")
        print("="*80)
        print(f"Method: {request.method}")
        print(f"URL: {request.url}")
        print(f"Remote Address: {request.remote_addr}")
        print(f"Content Type: {request.content_type}")
        print(f"Content Length: {request.content_length}")
        print("="*80)
        print("HEADERS:")
        print("="*80)
        for header_name, header_value in request.headers:
            print(f"{header_name}: {header_value}")
        print(f"{'='*80}")
        
        # Get raw payload for signature verification AND logging
        payload = request.get_data()
        
        print("RAW PAYLOAD (bytes):")
        print(f"{'='*80}")
        print(f"Length: {len(payload)} bytes")
        print("Raw bytes (first 1000 chars):")
        print(payload[:1000])
        print(f"{'='*80}")
        print("Raw payload as string:")
        try:
            payload_str = payload.decode('utf-8')
            print(payload_str)
        except UnicodeDecodeError as e:
            print(f"Could not decode as UTF-8: {e}")
            print("Hex dump of first 200 bytes:")
            print(payload[:200].hex())
        print(f"{'='*80}\n")
        
        signature = request.headers.get('X-Webhook-Signature', '')
        secret = os.getenv('WEBHOOK_SECRET', '')
        
        # Verify signature if configured
        if not verify_webhook_signature(payload, signature, secret):
            print("❌ Webhook signature verification failed")
            return jsonify({"error": "Invalid signature"}), 401
        
        # Parse JSON data
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Extract transcript information - handle both Athena bot and Vexa webhook formats
        if 'meeting_id' in data:
            # Athena bot format (with transcript)
            meeting_id = data.get('meeting_id', 'unknown')
            meeting_url = data.get('google_meet_url', 'unknown')
            start_time = data.get('start_time', 'unknown')
            end_time = data.get('end_time', 'unknown')
            transcript = data.get('transcript', '')
            bot_name = data.get('bot_name', 'Athena')
            status = data.get('status', 'unknown')
            timestamp = data.get('timestamp', datetime.now().isoformat())
            webhook_source = "Athena Bot"
        else:
            # Vexa API format (meeting status only)
            meeting_id = data.get('native_meeting_id', 'unknown')
            meeting_url = data.get('constructed_meeting_url', 'unknown')
            start_time = data.get('start_time', 'unknown')
            end_time = data.get('end_time', 'unknown')
            transcript = data.get('transcript', '')  # Usually empty in Vexa webhooks
            bot_name = 'Vexa Service'
            status = data.get('status', 'unknown')
            timestamp = data.get('updated_at', datetime.now().isoformat())
            webhook_source = "Vexa API"
        
        # Log received transcript
        print(f"\n{'='*60}")
        print(f"📝 WEBHOOK RECEIVED from {webhook_source}")
        print(f"Bot/Service: {bot_name}")
        print(f"{'='*60}")
        print(f"Meeting ID: {meeting_id}")
        print(f"Meeting URL: {meeting_url}")
        print(f"Start Time: {start_time}")
        print(f"End Time: {end_time}")
        print(f"Status: {status}")
        print(f"Received: {timestamp}")
        print(f"{'='*60}")
        print("TRANSCRIPT CONTENT:")
        print(f"{'='*60}")
        if transcript:
            print(transcript)
        else:
            print("⚠️  NO TRANSCRIPT CONTENT FOUND!")
            print(f"This appears to be a {webhook_source} status notification.")
            if webhook_source == "Vexa API":
                print("💡 Your Athena bot should fetch the transcript and send it separately.")
        print(f"{'='*60}\n")
        
        # Save transcript to file
        filename = f"transcript_{meeting_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            # Create transcripts directory if it doesn't exist
            os.makedirs('transcripts', exist_ok=True)
            
            # Save full data to file
            with open(f'transcripts/{filename}', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Transcript saved to: transcripts/{filename}")
            
        except Exception as e:
            print(f"⚠️  Failed to save transcript: {e}")
        
        # TODO: Add your custom processing here
        # Examples:
        # - Send to Slack
        # - Store in database  
        # - Process with AI for summary
        # - Send email notification
        
        return jsonify({
            "status": "success",
            "message": "Transcript received successfully",
            "meeting_id": meeting_id,
            "processed_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@app.route('/test', methods=['POST'])
def test_webhook():
    """Test endpoint for webhook functionality"""
    try:
        # LOG ALL RAW DATA FOR TEST ENDPOINT TOO
        print(f"\n{'='*80}")
        print("🧪 RAW TEST WEBHOOK DATA")
        print("="*80)
        print(f"Method: {request.method}")
        print(f"URL: {request.url}")
        print(f"Content Type: {request.content_type}")
        print("="*80)
        print("HEADERS:")
        for header_name, header_value in request.headers:
            print(f"{header_name}: {header_value}")
        print("="*80)
        
        # Raw payload
        payload = request.get_data()
        print(f"Raw payload ({len(payload)} bytes):")
        try:
            print(payload.decode('utf-8'))
        except UnicodeDecodeError:
            print("Non-UTF8 data:", payload.hex())
        print("="*80)
        
        data = request.get_json()
        print(f"Parsed JSON: {json.dumps(data, indent=2)}")
        print("="*80)
        
        return jsonify({
            "status": "success",
            "message": "Test webhook received",
            "echo": data
        })
        
    except Exception as e:
        return jsonify({
            "error": "Test failed",
            "message": str(e)
        }), 500


if __name__ == '__main__':
    print("🤖 Athena Webhook Server Starting...")
    print(f"Health check: http://localhost:8080/")
    print(f"Transcript endpoint: http://localhost:8080/transcript")
    print(f"Test endpoint: http://localhost:8080/test")
    
    # Get configuration from environment
    host = os.getenv('WEBHOOK_HOST', '0.0.0.0')
    port = int(os.getenv('WEBHOOK_PORT', '8080'))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    if os.getenv('WEBHOOK_SECRET'):
        print("🔐 Webhook signature verification enabled")
    else:
        print("⚠️  Webhook signature verification disabled (set WEBHOOK_SECRET to enable)")
    
    print(f"\nStarting server on {host}:{port}")
    
    app.run(
        host=host,
        port=port,
        debug=debug
    )