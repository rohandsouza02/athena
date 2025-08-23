#! /usr/bin/env python3
"""
Standup Automation Script

This script processes meeting transcripts, retrieves Teams context and previous task summaries,
generates standup updates using LLM, and posts them to Slack.

Usage:
    python standup_automation.py --transcript <transcript_file> --trigger <event_type>
"""

TEST_TASKS = [
        {
            "task_id": "PROJ-101",
            "task_name": "User Dashboard Redesign",
            "task_def": "Redesign the user dashboard with new wireframes, implement responsive layout using design system components, add data visualization components and user profile section",
            "status": "In Progress",
            "assigned_to": "Alex"
        },
        {
            "task_id": "PROJ-102", 
            "task_name": "Authentication API Development",
            "task_def": "Implement user authentication system including database schema, registration and login endpoints, user profile management, password reset functionality with email integration, input validation and rate limiting",
            "status": "In Progress", 
            "assigned_to": "Jordan"
        },
        {
            "task_id": "PROJ-103",
            "task_name": "API Testing Framework Setup",
            "task_def": "Set up automated testing framework for API endpoints, write comprehensive test cases for authentication features, perform regression testing and end-to-end testing of frontend integration",
            "status": "In Progress",
            "assigned_to": "Sam"
        },
        {
            "task_id": "PROJ-104",
            "task_name": "CI/CD Pipeline Configuration", 
            "task_def": "Configure CI/CD pipeline for new microservice, set up Docker containers, staging and production environments, implement automated testing integration, optimize build processes and deploy monitoring dashboard",
            "status": "In Progress",
            "assigned_to": "Taylor"
        },
        {
            "task_id": "PROJ-105",
            "task_name": "Frontend API Integration",
            "task_def": "Integrate frontend dashboard with real API endpoints, remove mock data connections, implement proper form validation and error handling for user interactions",
            "status": "Almost Complete",
            "assigned_to": "Alex"
        },
        {
            "task_id": "PROJ-106",
            "task_name": "Production Environment Setup",
            "task_def": "Configure production AWS environment access, set up email service credentials for password reset functionality, deploy monitoring and logging systems",
            "status": "In Progress",
            "assigned_to": "Taylor"
        },
        {
            "task_id": "PROJ-107",
            "task_name": "Mobile UI Bug Fixes",
            "task_def": "Fix validation message display issues on mobile devices, ensure responsive design works correctly across all screen sizes",
            "status": "To Do",
            "assigned_to": "Alex"
        },
        {
            "task_id": "PROJ-108",
            "task_name": "API Documentation Update",
            "task_def": "Improve and update API documentation for authentication endpoints, provide clear specifications for frontend integration",
            "status": "In Progress",
            "assigned_to": "Jordan"
        }
    ]


SYSTEM_PROMPT = """
# Standup Analysis Prompt

## Task
Update JIRA ticket status and summaries from standup transcript.

## Input
- Standup transcript
- JIRA tickets list with current status
- Previous summaries

## Output Format
```json
{
  "Person A": {
    "PROJ-101": {
      "status": "To Do/In Progress/Done",
      "summary": "Updated progress with context from previous days"
    }
  },
  "blockers": {
    "Person A": {
      "PROJ-102": "Waiting on final design assets from the product team for the landing page development."
    }
}
Instructions
Match standup updates to JIRA ticket IDs
Update status: "To Do", "In Progress", "Done". Strictly adhere to these status.
Write summaries combining previous context + today's updates
If new work is related to existing ticket, add it to that ticket's summary
Default to "In Progress" if unclear. 
In case a new ticket which is currently in "To Do" and will be started today move it to "In Progress"
If there is any blocker, mention that with the person involved
Write the summary in directive form, describing what the person should do next rather than what has been done. Use a formal tone. Example: instead of saying ‘Partial progress has been made; inconsistencies are being clarified with the growth team’, write ‘Clarify inconsistencies in the copy with the growth team and complete the page
"""
import argparse
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
from pathlib import Path
import requests

# Debug: Check if env vars are loaded
print(f"API Key loaded: {bool(os.getenv('OPENAI_API_KEY'))}")
print(f"Webhook URL loaded: {bool(os.getenv('SLACK_WEBHOOK_URL'))}")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


import json
import re

def clean_json_string(json_string):
    """
    Remove markdown code block formatting from JSON string
    """
    # Remove ```json at the beginning
    cleaned = re.sub(r'^```json\s*\n?', '', json_string.strip())
    
    # Remove ``` at the end
    cleaned = re.sub(r'\n?```\s*$', '', cleaned)
    
    # Remove escaped newlines if present
    cleaned = cleaned.replace('\\n', '\n')
    
    return cleaned.strip()


class StandupAutomation:
    def __init__(self, config_path: str = "config.json"):
        """Initialize the standup automation system."""
        self.config = self.load_config(config_path)
        
    def load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file {config_path} not found")
            return self.get_default_config()
    
    def get_default_config(self) -> Dict:
        """Return default configuration."""
        return {
            "teams_context_doc": "teams_context.md",
            "task_summaries_dir": "task_summaries",
            "llm_config": {
                "model": "gpt-4o-mini",
                "api_key": os.getenv("OPENAI_API_KEY"),
                "max_tokens": 500
            },
            "slack_config": {
                "webhook_url": os.getenv("SLACK_WEBHOOK_URL"),
                "channel": "#standups",
                "bot_name": "StandupBot"
            }
        }
    
    def read_transcript(self, transcript_path: str) -> str:
        """Read and return the meeting transcript."""
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Transcript file {transcript_path} not found")
            return ""
    
    def get_teams_context(self) -> str:
        """Retrieve Teams context from documentation."""
        context_doc = self.config.get("teams_context_doc", "teams_context.md")
        try:
            with open(context_doc, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Teams context doc {context_doc} not found")
            return "No Teams context available"
    
    def get_jira_tasks(self) -> List[Dict[str, str]]:
        """
        Gets tasks from JIRA current sprint.
        Returns a list of dict {
            task_id: 
            task_name:
            task_def:
            status:
            assigned_to:
        }
        """
        try:
            from sprint_report_generator import JiraClient
            jira_client = JiraClient(self.config.get("jira", {}))
            a =  jira_client.get_jira_tasks()
            print(a)
            return a
        except Exception as e:
            logger.error(f"Failed to fetch JIRA tasks: {e}")
            logger.info("Falling back to test data")
            return TEST_TASKS
    
    def get_previous_summaries(self, days: int = 5) -> List[Dict]:
        """Get task summaries from the previous N days."""
        summaries = []
        summaries_dir = Path(self.config.get("task_summaries_dir", "/Users/mayankmanjeara/Desktop/hackathon/athena/standups"))
        summaries_dir = Path("/Users/mayankmanjeara/Desktop/hackathon/athena/standups")
        if not summaries_dir.exists():
            logger.warning(f"Task summaries directory {summaries_dir} not found")
            return []
        
        # for i in range(1, days + 1):
        #     date = datetime.now() - timedelta(days=i)
        #     summary_file = summaries_dir / f"{date.strftime('%Y-%m-%d')}_summary.json"
        for summary_file in summaries_dir.iterdir():
            if summary_file.exists():
                try:
                    with open(summary_file, 'r') as f:
                        summary_data = f.read()
                        summaries.append({
                            # "date": date.strftime('%Y-%m-%d'),
                            "summary": summary_data
                        })
                except Exception as e:
                    logger.warning(f"Error reading summary file {summary_file}: {e}")
        
        return summaries
    
    def generate_standup_with_llm(self, transcript: str, teams_context: str, 
                                  previous_summaries: List[Dict], current_tasks: List[Dict]) -> str:
        """Generate standup update using LLM."""
        print('a')
        prompt = self.build_llm_prompt(transcript, teams_context, previous_summaries, current_tasks=current_tasks)
        print(10)
        # TODO: Implement actual LLM call based on your preferred provider
        # This is a placeholder implementation
        llm_config = self.config.get("llm_config", {})
        print(11)
        try:
            # Placeholder for LLM integration
            # Replace with actual implementation (OpenAI, Anthropic, etc.)
            standup_update = self._call_llm(prompt, llm_config)
            return standup_update
        except Exception as e:
            logger.error(f"Error generating standup with LLM: {e}")
            return "Error generating standup update"
    
    def build_llm_prompt(self, transcript: str, teams_context: str, 
                         previous_summaries: List[Dict], current_tasks: List[Dict]) -> str:
        """Build the prompt for the LLM."""
        prompt = f"""
        Based on the following information, generate a concise standup update:

        MEETING TRANSCRIPT:
        {transcript}

        
        TEAMS CONTEXT:
        {teams_context}

        
        CURRENT TASKS:
        {current_tasks}

        
        PREVIOUS DAYS SUMMARIES:
        """
        
        for summary in previous_summaries:
            prompt += f"{json.dumps(summary['summary'], indent=2)}\n----------\n"
        
        prompt += """
        
        Please generate a standup update in the following format:
        - What was accomplished yesterday
        - What will be worked on today
        - Any blockers or issues
        
        Keep it concise and professional.
        """
        
        return prompt
    
    def _call_llm(self, prompt: str, llm_config: Dict) -> str:
        """Make the actual LLM API call."""
        try:
            from openai import OpenAI
            api_key = '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'
            if not api_key:
                logger.error("OpenAI API key not configured")
                return "Error: OpenAI API key not configured"
            
            client = OpenAI(api_key=api_key)
            # f = open('prompt.txt', 'w')
            # f.write(f'{SYSTEM_PROMPT} \n\n\n\ {prompt}')

            response = client.chat.completions.create(
                model=llm_config.get("model", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                # max_tokens=llm_config.get("max_tokens", 500),
                temperature=llm_config.get("temperature", 1.0)
            )

            return response.choices[0].message.content.strip()
            
        except ImportError:
            logger.error("OpenAI library not installed")
            return "Error: OpenAI library not installed"
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return f"Error generating standup: {str(e)}"
    
    def send_to_slack(self, current_tasks: List[Dict], standup_update: str) -> bool:
        """Send task updates to Slack via webhook."""
        slack_config = self.config.get("slack_config", {})
        webhook_url = "localhost:3000"

        # Parse standup_update to extract task updates
        task_updates = []
        try:
            import json
            parsed_update = json.loads(clean_json_string(standup_update))
            
            # Extract blockers information
            blockers_info = parsed_update.get("blockers", {})
            
            for person, tasks in parsed_update.items():
                if person == "blockers":
                    continue
                    
                for task_id, task_info in tasks.items():
                    # Find the current task details
                    current_task = next((t for t in current_tasks if t.get("task_id") == task_id), None)
                    
                    if current_task:
                        # Get previous status from current_tasks (assuming this is the previous state)
                        prev_status = current_task.get("status", "Unknown")
                        current_status = task_info.get("status", prev_status)
                        
                        # Check if this person has blockers for this task
                        blocker_reason = None
                        if person in blockers_info and task_id in blockers_info[person]:
                            blocker_reason = blockers_info[person][task_id]
                        
                        task_update = {
                            "assignee": current_task.get("assigned_to", person),
                            "task_id": task_id,
                            "task_name": current_task.get("task_name", "Unknown Task"),
                            "task_description": current_task.get("task_def", "No description"),
                            "task_update": task_info.get("summary", "No update provided"),
                            "prev_status": prev_status,
                            "current_status": current_status,
                            "blocker": blocker_reason
                        }
                        task_updates.append(task_update)
                        
        except json.JSONDecodeError:
            logger.error("Failed to parse standup update JSON")
            return False
        f = open('udpates.txt', 'w')
        f.write(str(task_updates))
        # Construct webhook URL with /task_update endpoint
        if not webhook_url.endswith('/'):
            webhook_url += '/'
        webhook_url ="http://localhost:3000/task-update"
        
        if not webhook_url:
            logger.error("Slack webhook URL not configured")
            return False

        try:
            import requests
            response = requests.post(webhook_url, json=task_updates, headers={'Content-Type': 'application/json'})

            if response.status_code == 200:
                logger.info("Successfully sent task updates to Slack")
                return True
            else:
                logger.error(f"Failed to send to Slack. Status: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error sending to Slack: {e}")
            return False
    
    def handle_trigger_event(self, event_type: str, transcript_path: str) -> bool:
        """Handle different trigger events."""
        logger.info(f"Processing trigger event: {event_type}")
        
        # Event-specific logic can be added here
        event_handlers = {
            "standup_meeting": self.process_standup_meeting,
            "daily_summary": self.process_daily_summary,
            "manual_trigger": self.process_manual_trigger
        }
        
        handler = event_handlers.get(event_type, self.process_default)
        return handler(transcript_path)
    
    def process_standup_meeting(self, transcript_path: str) -> bool:
        """Process standup meeting trigger."""
        logger.info("Processing standup meeting trigger")
        return self.run_automation(transcript_path, "standup_meeting")
    
    def process_daily_summary(self, transcript_path: str) -> bool:
        """Process daily summary trigger."""
        logger.info("Processing daily summary trigger")
        return self.run_automation(transcript_path, "daily_summary")
    
    def process_manual_trigger(self, transcript_path: str) -> bool:
        """Process manual trigger."""
        logger.info("Processing manual trigger")
        return self.run_automation(transcript_path, "manual_trigger")
    
    def process_default(self, transcript_path: str) -> bool:
        """Process default/unknown trigger."""
        logger.info("Processing unknown trigger type")
        return self.run_automation(transcript_path, "unknown")
    
    def run_automation(self, transcript_path: str, trigger_event: str='Standup') -> bool:
        """Run the complete automation pipeline."""
        try:
            # Read transcript
            transcript = self.read_transcript(transcript_path)
            if not transcript:
                logger.error("No transcript content found")
                return False
            print(1)
            # Get Teams context
            teams_context = self.get_teams_context()

            # Get Current Tasks
            current_tasks = self.get_jira_tasks()
            # Get previous summaries
            previous_summaries = self.get_previous_summaries()
            # Generate standup with LLM
            standup_update = self.generate_standup_with_llm(
                transcript, teams_context, previous_summaries, current_tasks
            )
            # Send to Slack
            logger.info("Standup automation completed successfully")
            # Optionally save the generated standup for future reference
            self.save_standup_record(standup_update, trigger_event)
            success = self.send_to_slack(current_tasks, standup_update)
            
            return success
            
        except Exception as e:
            logger.error(f"Error in automation pipeline: {e}")
            return False
    
    def save_standup_record(self, standup_update: str, trigger_event: str):
        """Save the standup record for future reference."""
        records_dir = Path("/Users/mayankmanjeara/Desktop/hackathon/athena/standups")
        records_dir.mkdir(exist_ok=True)

        record = {
            "timestamp": datetime.now().isoformat(),
            "trigger_event": trigger_event,
            "standup_update": standup_update
        }   
        filename = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_standup.json"
        record_path = records_dir / filename
        
        try:
            with open(record_path, 'w') as f:
                json.dump(record, f, indent=2)
            logger.info(f"Standup record saved to {record_path}")
        except Exception as e:
            logger.warning(f"Could not save standup record: {e}")


def main():
    transcript_path ='24.txt'
    automation = StandupAutomation(config_path='config.json')
    success = automation.run_automation(transcript_path=transcript_path)
    # success = automation.handle_trigger_event(args.trigger, args.transcript)
    
    if success:
        print("✅ Standup automation completed successfully")
        exit(0)
    else:
        print("❌ Standup automation failed")
        exit(1)



if __name__ == "__main__":
    main()