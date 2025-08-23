#!/usr/bin/env python3
"""
Standup Summarizer API
Single API endpoint to summarize all standup JSON files using ChatGPT.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from flask import Flask, jsonify
from openai import OpenAI


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class StandupSummarizer:
    """Handles summarization of standup records using ChatGPT."""
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize the summarizer with configuration."""
        self.config = self.load_config(config_path)
        self.standups_dir = Path("/Users/mayankmanjeara/Desktop/hackathon/athena/standups")
        
    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file {config_path} not found")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing config file: {e}")
            return {}
    
    def get_all_standup_files(self) -> List[Path]:
        """Get all JSON files from the standups directory."""
        if not self.standups_dir.exists():
            logger.warning(f"Standups directory {self.standups_dir} does not exist")
            return []
        # Todo: Update txt to json
        json_files = list(self.standups_dir.glob("*.json"))
        logger.info(f"Found {len(json_files)} standup files")
        return json_files
    
    def read_standup_data(self) -> List[Dict[str, Any]]:
        """Read all standup JSON files and return their contents."""
        standup_files = self.get_all_standup_files()
        standup_data = []
        
        for file_path in standup_files:
            try:
                with open(file_path, 'r') as f:
                    try:
                        data = json.load(f)
                    except:
                        data = f.read()
                    standup_data.append(data)
                    logger.info(f"Successfully read {file_path.name}")
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing {file_path.name}: {e}")
            except Exception as e:
                logger.error(f"Error reading {file_path.name}: {e}")
        
        return standup_data
    
    def generate_summary_with_llm(self, standup_data: List[Dict[str, Any]]) -> str:
        """Use ChatGPT to generate a summary of all standup data."""
        if not standup_data:
            return "No standup data available for summarization."
        
        # Prepare the prompt for ChatGPT
        prompt = self._create_summary_prompt(standup_data)
        try:
            openai_config = self.config.get("openai_config", {})
            api_key = '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'
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=openai_config.get("model", "gpt-4"),
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a helpful assistant that summarizes team standup updates."
                    },
                    {"role": "user", "content": prompt}
                ],
                # max_tokens=openai_config.get("max_tokens", 1000),
                temperature=openai_config.get("temperature", 0.1)
            )
            
            return response.choices[0].message.content.strip()
            
        except ImportError:
            logger.error("OpenAI library not installed")
            return "Error: OpenAI library not installed"
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return f"Error generating summary: {str(e)}"
    
    def _create_summary_prompt(self, standup_data: List[Dict[str, Any]]) -> str:
        """Create a prompt for ChatGPT to summarize standup data."""
        prompt = """Please analyze and summarize the following team standup updates. 
        Provide a comprehensive summary that includes:
        1. Key accomplishments and progress made
        2. Common themes or patterns across updates
        3. Important blockers or challenges mentioned
        4. Overall team productivity insights
        5. Action items or follow-ups needed
        
        Here are the standup updates:
        
        """
        
        for i, standup in enumerate(standup_data, 1):
            timestamp = standup.get('timestamp', 'Unknown time')
            trigger_event = standup.get('trigger_event', 'Unknown trigger')
            update_content = standup.get('standup_update', 'No content')
            
            prompt += f"""
            Update #{i}:
            Timestamp: {timestamp}
            Trigger Event: {trigger_event}
            Content: {update_content}
            
            ---
            """
        
        prompt += "\nPlease provide a well-structured summary based on the above data."
        return prompt

# Initialize the summarizer
summarizer = StandupSummarizer()

# @app.route('/summarize', methods=['POST'])
def summarize_standups():
    """Single API endpoint to summarize all standup records."""
    try:
        logger.info("Received request to summarize standups")
        
        # Read all standup data
        standup_data = summarizer.read_standup_data()
        
        # if not standup_data:
        #     return jsonify({
        #         "error": "No standup data found",
        #         "summary": "No standup records available for summarization."
        #     }), 404
        
        # Generate summary using ChatGPT
        summary = summarizer.generate_summary_with_llm(standup_data)
        
        response_data = {
            "summary": summary,
            "total_standups": len(standup_data),
            "generated_at": datetime.now().isoformat()
        }
        
        logger.info(f"Successfully generated summary for {len(standup_data)} standups")
        # f = open('summarised.txt', 'w'):

        return False
        # return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error in summarize endpoint: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500

if __name__ == "__main__":
    # logger.info("Starting Standup Summarizer API")
    # app.run(host="0.0.0.0", port=5000, debug=False)
    summarizer = StandupSummarizer()
    summarize_standups()
