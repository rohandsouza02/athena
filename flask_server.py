#!/usr/bin/env python3
from flask import Flask, request, jsonify
import asyncio
import threading
import tempfile
import os
from standup_automation import StandupAutomation
from sprint_report_generator import SprintReportGenerator

app = Flask(__name__)

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
    app.run(host='0.0.0.0', port=5000, debug=True)