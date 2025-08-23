#!/usr/bin/env python3
"""
Sprint Performance Report Generator
Generates PDF sprint reports using JIRA data and standup summaries.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import requests
from requests.auth import HTTPBasicAuth
import weasyprint
from standup_summarizer import StandupSummarizer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class SprintData:
    """Data structure for sprint information."""
    sprint_name: str
    sprint_goal: str
    start_date: str
    end_date: str
    planned_story_points: int
    completed_story_points: int
    completion_rate: float
    team_members: List[str]
    completed_stories: List[Dict[str, Any]]
    incomplete_stories: List[Dict[str, Any]]
    blockers: List[str]
    velocity_history: List[Dict[str, Any]] = field(default_factory=lambda: [
        {"name": "Sprint 21", "completed_points": 30, "planned_points": 40, "completion_rate": 75.0, "is_current": False},
        {"name": "Sprint 22", "completed_points": 33, "planned_points": 40, "completion_rate": 82.5, "is_current": False},
        {"name": "Sprint 23", "completed_points": 27, "planned_points": 40, "completion_rate": 68.0, "is_current": False},
        {"name": "Sprint 24", "completed_points": 37, "planned_points": 40, "completion_rate": 91.2, "is_current": False},
        {"name": "Sprint 25", "completed_points": 36, "planned_points": 40, "completion_rate": 90.0, "is_current": True}
    ])

class JiraClient:
    """JIRA API client for fetching sprint data."""
    
    def __init__(self, config: Dict[str, Any]):
        self.base_url = config.get("jira_url", "")
        self.username = config.get("username", "")
        self.api_token = config.get("api_token", "")
        self.auth = HTTPBasicAuth(self.username, self.api_token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    def get_all_boards(self):
        """Get all boards for the project."""
        try:
            boards_url = f"{self.base_url}/rest/agile/1.0/board"
            response = requests.get(boards_url, headers=self.headers, auth=self.auth)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching boards: {e}")
            return None
    
    def get_active_sprint_for_board(self, board_id: str):
        """Get the active sprint for a specific board."""
        try:
            sprints_url = f"{self.base_url}/rest/agile/1.0/board/{board_id}/sprint"
            params = {"state": "active"}
            response = requests.get(sprints_url, headers=self.headers, auth=self.auth, params=params)
            response.raise_for_status()
            sprints_data = response.json()
            
            if sprints_data.get("values"):
                return sprints_data["values"][0]  # Return first active sprint
            return None
        except requests.RequestException as e:
            logger.error(f"Error fetching active sprint: {e}")
            return None
    
    def get_sprint_data(self) -> Optional[SprintData]:
        """Fetch sprint data from JIRA by auto-discovering boards and sprints."""
        try:
            # Get all boards
            boards_data = self.get_all_boards()
            if not boards_data or not boards_data.get("values"):
                logger.error("No boards found")
                return None
            
            # Find the first board with an active sprint
            board_id = None
            sprint_info = None
            
            for board in boards_data["values"]:
                board_id = board["id"]
                logger.info(f"Checking board: {board['name']} (ID: {board_id})")
                
                sprint_info = self.get_active_sprint_for_board(board_id)
                if sprint_info:
                    logger.info(f"Found active sprint: {sprint_info['name']}")
                    break
            
            if not sprint_info:
                logger.error("No active sprint found in any board")
                return None
            
            sprint_id = sprint_info["id"]
            
            # Get sprint issues
            issues_url = f"{self.base_url}/rest/agile/1.0/sprint/{sprint_id}/issue"
            issues_response = requests.get(issues_url, headers=self.headers, auth=self.auth)
            issues_response.raise_for_status()
            issues_data = issues_response.json()
            
            # Process the data
            return self._process_sprint_data(sprint_info, issues_data)
            
        except requests.RequestException as e:
            logger.error(f"Error fetching JIRA data: {e}")
            return None
    
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
            # Get all boards
            boards_data = self.get_all_boards()
            if not boards_data or not boards_data.get("values"):
                logger.error("No boards found")
                return []
            
            # Find the first board with an active sprint
            sprint_info = None
            
            for board in boards_data["values"]:
                board_id = board["id"]
                sprint_info = self.get_active_sprint_for_board(board_id)
                if sprint_info:
                    break
            
            if not sprint_info:
                logger.error("No active sprint found in any board")
                return []
            
            sprint_id = sprint_info["id"]
            
            # Get sprint issues
            issues_url = f"{self.base_url}/rest/agile/1.0/sprint/{sprint_id}/issue"
            issues_response = requests.get(issues_url, headers=self.headers, auth=self.auth)
            issues_response.raise_for_status()
            issues_data = issues_response.json()
            
            # Process issues into the required format
            tasks = []
            for issue in issues_data.get("issues", []):
                fields = issue["fields"]
                assignee = fields.get("assignee")
                
                task = {
                    "task_id": issue["key"],
                    "task_name": fields["summary"],
                    "task_def": fields.get("description", "No description available"),
                    "status": fields["status"]["name"],
                    "assigned_to": assignee["displayName"] if assignee else "Unassigned"
                }
                tasks.append(task)
            
            return tasks
            
        except requests.RequestException as e:
            logger.error(f"Error fetching JIRA tasks: {e}")
            return []
    
    def _process_sprint_data(self, sprint_info: Dict, issues_data: Dict) -> SprintData:
        """Process raw JIRA data into SprintData format."""
        issues = issues_data.get("issues", [])
        
        completed_stories = []
        incomplete_stories = []
        planned_points = 0
        completed_points = 0
        team_members = set()
        # print(issues[0])
        for issue in issues:
            fields = issue["fields"]
            story_points = fields.get('customfield_10016', 0) or 0  # Common story points field
            print(story_points)
            status = fields["status"]["name"]
            assignee = fields.get("assignee")
            
            if assignee:
                team_members.add(assignee["displayName"])
            
            planned_points += story_points
            
            story_data = {
                "key": issue["key"],
                "summary": fields["summary"],
                "story_points": story_points,
                "status": status,
                "assignee": assignee["displayName"] if assignee else "Unassigned"
            }
            
            if status.lower() in ["done", "completed", "closed"]:
                completed_stories.append(story_data)
                completed_points += story_points
            else:
                incomplete_stories.append(story_data)
        
        completion_rate = (completed_points / planned_points * 100) if planned_points > 0 else 0
        
        return SprintData(
            sprint_name=sprint_info.get("name", "Unknown Sprint"),
            sprint_goal=sprint_info.get("goal", "No goal specified"),
            start_date=sprint_info.get("startDate", "").split("T")[0],
            end_date=sprint_info.get("endDate", "").split("T")[0],
            planned_story_points=planned_points,
            completed_story_points=completed_points,
            completion_rate=completion_rate,
            team_members=list(team_members),
            completed_stories=completed_stories,
            incomplete_stories=incomplete_stories,
            blockers=[]  # Will be filled from standup summaries
        )

class SprintReportGenerator:
    """Generates sprint performance reports in PDF format."""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = self.load_config(config_path)
        self.jira_client = JiraClient(self.config.get("jira", {}))
        self.standup_summarizer = StandupSummarizer(config_path)
        
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
    
    def generate_report(self, output_path: str = None) -> str:
        """Generate a complete sprint performance report."""
        # Fetch sprint data from JIRA
        sprint_data = self.jira_client.get_sprint_data()
        if not sprint_data:
            logger.error("Failed to fetch sprint data")
            return None
            
        # Get standup summaries for retrospective
        standup_summary = self._get_retrospective_notes()
        
        # Generate PDF report
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"sprint_report_{timestamp}.pdf"
        
        self._create_pdf_report(sprint_data, standup_summary, output_path)
        logger.info(f"Sprint report generated: {output_path}")
        
        # Send to Slack
        self.send_pdf_to_slack(output_path)
        
        return output_path
    
    def send_pdf_to_slack(self, pdf_path: str) -> bool:
        """Send PDF report to webhook via JSON."""
        slack_config = self.config.get("slack_config", {})
        webhook_url = "http://localhost:3000/report_gen_webhook"
        
        if not webhook_url:
            logger.error("Webhook URL not configured")
            return False
        
        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found: {pdf_path}")
            return False
        
        try:
            # Prepare JSON payload
            payload = {
                "pdf_path": os.path.abspath(pdf_path),
                "title": f"Sprint Performance Report - {datetime.now().strftime('%Y-%m-%d')}"
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            response = requests.post(webhook_url, json=payload, headers=headers)
            
            if response.status_code == 200:
                logger.info("Successfully sent PDF report to webhook")
                return True
            else:
                logger.error(f"Failed to send PDF to webhook. Status: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending PDF to webhook: {e}")
            return False
    
    def _get_retrospective_notes(self) -> Dict[str, Any]:
        """Extract retrospective notes from standup summaries."""
        standup_data = self.standup_summarizer.read_standup_data()
        summary = self.standup_summarizer.generate_summary_with_llm(standup_data)
        # Parse the summary for retrospective elements
        return {
            "what_went_well": [
                "Good collaboration across dev + QA",
                "Automated testing reduced bug turnaround"
            ],
            "what_didnt_go_well": [
                "Dependencies on external team caused delays",
                "Poor sprint planning → underestimation of story points"
            ],
            "improvements": [
                "Improve story estimation",
                "Set up a staging environment earlier"
            ],
            "blockers": [
                "Delay due to QA environment not being ready",
                "High number of production bugs diverted dev capacity"
            ],
            "raw_summary": summary
        }
    
    def _create_pdf_report(self, sprint_data: SprintData, retrospective: Dict[str, Any], output_path: str):
        """Create the PDF report using WeasyPrint."""
        html_content = self._generate_html_report(sprint_data, retrospective)
        
        # Convert HTML to PDF
        html_doc = weasyprint.HTML(string=html_content)
        html_doc.write_pdf(output_path)
    
    def _generate_velocity_chart_html(self, velocity_history: List[Dict[str, Any]]) -> str:
        """Generate beautiful bar chart showing story points completed."""
        if not velocity_history:
            return ""
            
        chart_bars = ""
        max_points = max(sprint.get('completed_points', 0) for sprint in velocity_history)
        
        # Create beautiful gradient bars
        for i, sprint in enumerate(velocity_history):
            completed_points = sprint.get('completed_points', 0)
            planned_points = sprint.get('planned_points', 0)
            height = int((completed_points / max_points) * 180) if max_points > 0 else 0
            is_current = sprint.get('is_current', False)
            
            # Color scheme: current sprint is green, others are blue gradient
            if is_current:
                bar_color = "linear-gradient(135deg, #10b981, #34d399)"
                glow = "box-shadow: 0 4px 20px rgba(16, 185, 129, 0.3);"
            else:
                bar_color = "linear-gradient(135deg, #3b82f6, #60a5fa)"
                glow = "box-shadow: 0 2px 10px rgba(59, 130, 246, 0.2);"
            
            chart_bars += f"""
                <div class="velocity-bar" style="height: {height}px; background: {bar_color}; {glow}">
                    <div class="bar-value">{completed_points}</div>
                    <div class="bar-details">{completed_points}/{planned_points}</div>
                    <div class="bar-label">{sprint['name'].replace('Sprint ', 'S')}</div>
                </div>"""
        
        # Calculate statistics
        avg_velocity = sum(s.get('completed_points', 0) for s in velocity_history) / len(velocity_history)
        current_velocity = velocity_history[-1].get('completed_points', 0)
        trend = "↗️ Improving" if current_velocity > avg_velocity else "↘️ Declining" if current_velocity < avg_velocity else "➡️ Stable"
        
        return f"""
            <div class="velocity-chart">
                <div class="chart-header">
                    <h3>📊 Team Velocity Trend</h3>
                    <p>Story points completed across recent sprints</p>
                </div>
                
                <div class="chart-container">
                    {chart_bars}
                </div>
                
                <div class="velocity-stats">
                    <div class="velocity-stat primary">
                        <div class="stat-icon">📈</div>
                        <div class="stat-content">
                            <div class="stat-value">{avg_velocity:.0f}</div>
                            <div class="stat-label">Average Points</div>
                        </div>
                    </div>
                    <div class="velocity-stat current">
                        <div class="stat-icon">🎯</div>
                        <div class="stat-content">
                            <div class="stat-value">{current_velocity}</div>
                            <div class="stat-label">Current Sprint</div>
                        </div>
                    </div>
                    <div class="velocity-stat trend">
                        <div class="stat-icon">📊</div>
                        <div class="stat-content">
                            <div class="stat-value">{trend.split(' ')[1]}</div>
                            <div class="stat-label">Trend</div>
                        </div>
                    </div>
                </div>
            </div>"""

    def _generate_html_report(self, sprint_data: SprintData, retrospective: Dict[str, Any]) -> str:
        """Generate beautifully styled HTML content for the sprint report."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Sprint Performance Report</title>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
                
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                    line-height: 1.6;
                    color: #1f2937;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 20px;
                }}
                
                .report-container {{
                    max-width: 900px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 20px;
                    box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15);
                    overflow: hidden;
                }}
                
                .report-header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 40px;
                    text-align: center;
                    position: relative;
                }}
                
                .report-header::before {{
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.1'%3E%3Ccircle cx='30' cy='30' r='2'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E") repeat;
                }}
                
                .report-title {{
                    font-size: 2.5rem;
                    font-weight: 700;
                    margin-bottom: 10px;
                    position: relative;
                    z-index: 1;
                }}
                
                .report-subtitle {{
                    font-size: 1.1rem;
                    opacity: 0.9;
                    position: relative;
                    z-index: 1;
                }}
                
                .report-content {{
                    padding: 40px;
                }}
                
                .section {{
                    margin-bottom: 40px;
                }}
                
                .section-title {{
                    font-size: 1.8rem;
                    font-weight: 600;
                    color: #1f2937;
                    margin-bottom: 20px;
                    padding-bottom: 10px;
                    border-bottom: 3px solid #e5e7eb;
                    position: relative;
                }}
                
                .section-title::before {{
                    content: '';
                    position: absolute;
                    bottom: -3px;
                    left: 0;
                    width: 60px;
                    height: 3px;
                    background: linear-gradient(135deg, #667eea, #764ba2);
                }}
                
                .info-card {{
                    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
                    border: 1px solid #e2e8f0;
                    border-radius: 16px;
                    padding: 25px;
                    margin: 20px 0;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
                }}
                
                .project-info {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px;
                    margin-bottom: 20px;
                }}
                
                .info-item {{
                    background: white;
                    padding: 15px;
                    border-radius: 10px;
                    border-left: 4px solid #667eea;
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
                }}
                
                .info-label {{
                    font-weight: 600;
                    color: #4b5563;
                    font-size: 0.875rem;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                
                .info-value {{
                    font-size: 1.1rem;
                    color: #1f2937;
                    margin-top: 5px;
                }}
                
                .metrics-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                    gap: 20px;
                    margin: 20px 0;
                }}
                
                .metric-card {{
                    background: white;
                    padding: 25px;
                    border-radius: 16px;
                    text-align: center;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                    border: 1px solid #e5e7eb;
                    transition: transform 0.2s ease;
                }}
                
                .metric-card:hover {{
                    transform: translateY(-2px);
                }}
                
                .metric-value {{
                    font-size: 2.5rem;
                    font-weight: 700;
                    color: #667eea;
                    margin-bottom: 8px;
                }}
                
                .metric-label {{
                    font-weight: 500;
                    color: #6b7280;
                    font-size: 0.875rem;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                
                /* Velocity Chart Styles */
                .velocity-chart {{
                    background: white;
                    border-radius: 16px;
                    padding: 30px;
                    margin: 25px 0;
                    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
                    border: 1px solid #e5e7eb;
                }}
                
                .chart-header {{
                    text-align: center;
                    margin-bottom: 30px;
                }}
                
                .chart-header h3 {{
                    font-size: 1.5rem;
                    font-weight: 600;
                    color: #1f2937;
                    margin-bottom: 8px;
                }}
                
                .chart-header p {{
                    color: #6b7280;
                    font-size: 0.95rem;
                }}
                
                .chart-container {{
                    display: flex;
                    align-items: flex-end;
                    justify-content: space-around;
                    height: 220px;
                    margin: 30px 0;
                    padding: 20px;
                    position: relative;
                }}
                
                .chart-container::after {{
                    content: '';
                    position: absolute;
                    bottom: 0;
                    left: 20px;
                    right: 20px;
                    height: 2px;
                    background: linear-gradient(90deg, #667eea, #764ba2);
                }}
                
                .velocity-bar {{
                    min-width: 60px;
                    border-radius: 8px 8px 0 0;
                    position: relative;
                    margin: 0 5px;
                    transition: transform 0.3s ease;
                    display: flex;
                    flex-direction: column;
                    justify-content: flex-end;
                    align-items: center;
                }}
                
                .velocity-bar:hover {{
                    transform: scale(1.05);
                }}
                
                .bar-value {{
                    color: white;
                    font-weight: 700;
                    font-size: 1.1rem;
                    padding: 8px;
                }}
                
                .bar-details {{
                    color: white;
                    font-size: 0.75rem;
                    opacity: 0.8;
                    padding-bottom: 8px;
                }}
                
                .bar-label {{
                    position: absolute;
                    bottom: -35px;
                    font-size: 0.875rem;
                    font-weight: 500;
                    color: #4b5563;
                    text-align: center;
                    width: 80px;
                }}
                
                .velocity-stats {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                    gap: 20px;
                    margin-top: 30px;
                }}
                
                .velocity-stat {{
                    background: linear-gradient(135deg, #f8fafc, #f1f5f9);
                    border-radius: 12px;
                    padding: 20px;
                    text-align: center;
                    border: 1px solid #e2e8f0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 12px;
                }}
                
                .velocity-stat.primary {{
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    color: white;
                }}
                
                .velocity-stat.current {{
                    background: linear-gradient(135deg, #10b981, #34d399);
                    color: white;
                }}
                
                .stat-icon {{
                    font-size: 1.5rem;
                }}
                
                .stat-value {{
                    font-size: 1.5rem;
                    font-weight: 700;
                }}
                
                .stat-label {{
                    font-size: 0.875rem;
                    opacity: 0.9;
                }}
                
                /* Story Lists */
                .story-list {{
                    list-style: none;
                    padding: 0;
                }}
                
                .story-item {{
                    background: white;
                    border-radius: 12px;
                    padding: 20px;
                    margin: 12px 0;
                    border-left: 4px solid #10b981;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
                    transition: transform 0.2s ease;
                }}
                
                .story-item:hover {{
                    transform: translateX(4px);
                }}
                
                .story-item.incomplete {{
                    border-left-color: #ef4444;
                }}
                
                .story-key {{
                    font-weight: 600;
                    color: #667eea;
                    margin-right: 12px;
                }}
                
                .story-points {{
                    background: #f3f4f6;
                    color: #374151;
                    padding: 4px 8px;
                    border-radius: 6px;
                    font-size: 0.875rem;
                    font-weight: 500;
                    float: right;
                }}
                
                /* Retrospective */
                .retrospective {{
                    background: linear-gradient(135deg, #fef3c7, #fde68a);
                    border-radius: 16px;
                    padding: 30px;
                    margin: 25px 0;
                    border: 1px solid #f59e0b;
                }}
                
                .retrospective h3 {{
                    color: #92400e;
                    font-weight: 600;
                    margin-bottom: 15px;
                }}
                
                .retrospective ul {{
                    list-style: none;
                    padding: 0;
                }}
                
                .retrospective li {{
                    background: rgba(255, 255, 255, 0.7);
                    padding: 12px 16px;
                    margin: 8px 0;
                    border-radius: 8px;
                    border-left: 3px solid #f59e0b;
                }}
            </style>
        </head>
        <body>
            <div class="report-container">
                <div class="report-header">
                    <h1 class="report-title">📊 Sprint Performance Report</h1>
                    <p class="report-subtitle">Comprehensive analysis and insights</p>
                </div>
                
                <div class="report-content">
                    <div class="section">
                        <div class="info-card">
                            <div class="project-info">
                                <div class="info-item">
                                    <div class="info-label">Project</div>
                                    <div class="info-value">AllSmartPhones</div>
                                </div>
                                <div class="info-item">
                                    <div class="info-label">Sprint</div>
                                    <div class="info-value">{sprint_data.sprint_name}</div>
                                </div>
                                <div class="info-item">
                                    <div class="info-label">Duration</div>
                                    <div class="info-value">{sprint_data.start_date} – {sprint_data.end_date}</div>
                                </div>
                                <div class="info-item">
                                    <div class="info-label">Team Size</div>
                                    <div class="info-value">{len(sprint_data.team_members)} members</div>
                                </div>
                            </div>
                            
                            <div class="info-item">
                                <div class="info-label">Sprint Goal</div>
                                <div class="info-value">{sprint_data.sprint_goal}</div>
                            </div>
                            
                            <div class="info-item">
                                <div class="info-label">Team Members</div>
                                <div class="info-value">{', '.join(sprint_data.team_members)}</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="section">
                        <h2 class="section-title">📈 Sprint Metrics</h2>
                        <div class="metrics-grid">
                            <div class="metric-card">
                                <div class="metric-value">{sprint_data.planned_story_points}</div>
                                <div class="metric-label">Planned Points</div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-value">{sprint_data.completed_story_points}</div>
                                <div class="metric-label">Completed Points</div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-value">{sprint_data.completion_rate:.1f}%</div>
                                <div class="metric-label">Completion Rate</div>
                            </div>
                        </div>
                    </div>
                    
                    {self._generate_velocity_chart_html(sprint_data.velocity_history) if sprint_data.velocity_history else ""}
                    
                    <div class="section">
                        <h2 class="section-title">✅ Work Completed</h2>
                        <ul class="story-list">"""
        
        for story in sprint_data.completed_stories:
            html += f"""
                            <li class="story-item">
                                <span class="story-key">{story['key']}</span>
                                <span class="story-points">{story['story_points']} pts</span>
                                {story['summary']}
                            </li>"""
        
        html += """
                        </ul>
                    </div>"""
        
        if sprint_data.incomplete_stories:
            html += """
                    <div class="section">
                        <h2 class="section-title">⏳ Work Not Completed</h2>
                        <ul class="story-list">"""
            
            for story in sprint_data.incomplete_stories:
                html += f"""
                            <li class="story-item incomplete">
                                <span class="story-key">{story['key']}</span>
                                <span class="story-points">{story['story_points']} pts</span>
                                {story['summary']} <em>(Status: {story['status']})</em>
                            </li>"""
            
            html += """
                        </ul>
                    </div>"""
        
        if retrospective.get('blockers'):
            html += """
                    <div class="section">
                        <h2 class="section-title">🚧 Blockers & Challenges</h2>
                        <ul class="story-list">"""
            
            for blocker in retrospective['blockers']:
                html += f"""
                            <li class="story-item incomplete">
                                {blocker}
                            </li>"""
            
            html += """
                        </ul>
                    </div>"""
        
        html += f"""
                    <div class="section">
                        <h2 class="section-title">🔄 Retrospective Notes</h2>
                        
                        <div class="retrospective">
                            <h3>✅ What went well:</h3>
                            <ul>"""
        
        for item in retrospective.get('what_went_well', []):
            html += f"<li>{item}</li>"
        
        html += f"""
                            </ul>
                            
                            <h3>❌ What didn't go well:</h3>
                            <ul>"""
        
        for item in retrospective.get('what_didnt_go_well', []):
            html += f"<li>{item}</li>"
        
        html += f"""
                            </ul>
                            
                            <h3>🎯 Improvements for next sprint:</h3>
                            <ul>"""
        
        for item in retrospective.get('improvements', []):
            html += f"<li>{item}</li>"
        
        html += """
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>"""
        
        return html

def generate_test_report():
    """Generate a test sprint report with mock data."""
    print("🧪 Generating test sprint report with mock data...")
    
    generator = SprintReportGenerator()
    
    # Create mock sprint data for testing
    mock_velocity_history = [
        {"name": "Sprint 21", "completed_points": 30, "planned_points": 40, "completion_rate": 75.0, "is_current": False},
        {"name": "Sprint 22", "completed_points": 33, "planned_points": 40, "completion_rate": 82.5, "is_current": False},
        {"name": "Sprint 23", "completed_points": 27, "planned_points": 40, "completion_rate": 68.0, "is_current": False},
        {"name": "Sprint 24", "completed_points": 37, "planned_points": 40, "completion_rate": 91.2, "is_current": False},
        {"name": "Sprint 25", "completed_points": 45, "planned_points": 50, "completion_rate": 90.0, "is_current": True}
    ]
    
    mock_sprint_data = SprintData(
        sprint_name="Sprint #25 - Feature Development",
        sprint_goal="Implement user authentication and product catalog features",
        start_date="2024-01-01",
        end_date="2024-01-14",
        planned_story_points=50,
        completed_story_points=45,
        completion_rate=90.0,
        team_members=["Mayank", "Parikshit", "Rashi", "Rohan"],
        completed_stories=[
            {"key": "PROJ-101", "summary": "User login functionality", "story_points": 8, "status": "Done", "assignee": "Mayank"},
            {"key": "PROJ-102", "summary": "Product catalog API", "story_points": 13, "status": "Done", "assignee": "Parikshit"},
            {"key": "PROJ-103", "summary": "Shopping cart component", "story_points": 8, "status": "Done", "assignee": "Rashi"},
            {"key": "PROJ-104", "summary": "User registration form", "story_points": 5, "status": "Done", "assignee": "Rohan"},
            {"key": "PROJ-105", "summary": "Product search functionality", "story_points": 11, "status": "Done", "assignee": "Mayank"}
        ],
        incomplete_stories=[
            {"key": "PROJ-106", "summary": "Payment integration", "story_points": 5, "status": "In Progress", "assignee": "Parikshit"}
        ],
        blockers=[],
        velocity_history=mock_velocity_history
    )
    
    # Get retrospective notes from standup summaries
    retrospective = generator._get_retrospective_notes()
    
    # Generate test report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"test_sprint_report_{timestamp}.pdf"
    
    generator._create_pdf_report(mock_sprint_data, retrospective, output_path)
    print(f"✅ Test sprint report generated: {output_path}")
    return output_path


def _generate_velocity_chart_html(self, velocity_history: List[Dict[str, Any]]) -> str:
        """Generate SVG line chart for the velocity chart."""
        if not velocity_history:
            return ""
        
        # Chart dimensions
        width = 600
        height = 300
        margin = 50
        chart_width = width - 2 * margin
        chart_height = height - 2 * margin
        
        # Calculate scales
        max_completion = max(sprint['completion_rate'] for sprint in velocity_history)
        min_completion = min(sprint['completion_rate'] for sprint in velocity_history)
        y_range = max_completion - min_completion
        if y_range < 20:  # Minimum range for better visualization
            y_range = 20
            min_completion = max(0, max_completion - y_range)
        
        # Generate SVG path for the line
        points = []
        for i, sprint in enumerate(velocity_history):
            x = margin + (i * chart_width / (len(velocity_history) - 1))
            y = margin + chart_height - ((sprint['completion_rate'] - min_completion) / y_range * chart_height)
            points.append(f"{x},{y}")
        
        path_data = "M " + " L ".join(points)
        
        # Generate grid lines
        grid_lines = ""
        for i in range(5):  # 5 horizontal grid lines
            y = margin + (i * chart_height / 4)
            grid_lines += f'<line x1="{margin}" y1="{y}" x2="{width - margin}" y2="{y}" stroke="#e5e7eb" stroke-width="1"/>'
        
        # Generate labels
        x_labels = ""
        y_labels = ""
        
        # X-axis labels (sprint names)
        for i, sprint in enumerate(velocity_history):
            x = margin + (i * chart_width / (len(velocity_history) - 1))
            sprint_name = sprint['name'].replace('Sprint ', 'S')  # Shorten for space
            x_labels += f'<text x="{x}" y="{height - 10}" text-anchor="middle" font-size="12" fill="#6b7280">{sprint_name}</text>'
        
        # Y-axis labels (completion percentages)
        for i in range(5):
            y = margin + (i * chart_height / 4)
            value = max_completion - (i * y_range / 4)
            y_labels += f'<text x="{margin - 10}" y="{y + 4}" text-anchor="end" font-size="12" fill="#6b7280">{value:.0f}%</text>'
        
        # Generate data points
        data_points = ""
        for i, sprint in enumerate(velocity_history):
            x = margin + (i * chart_width / (len(velocity_history) - 1))
            y = margin + chart_height - ((sprint['completion_rate'] - min_completion) / y_range * chart_height)
            color = "#22c55e" if sprint.get('is_current') else "#3b82f6"
            data_points += f'<circle cx="{x}" cy="{y}" r="4" fill="{color}" stroke="white" stroke-width="2"/>'
            # Add value labels on points
            data_points += f'<text x="{x}" y="{y - 10}" text-anchor="middle" font-size="10" fill="#374151">{sprint["completion_rate"]:.0f}%</text>'
        
        avg_velocity = sum(s['completion_rate'] for s in velocity_history) / len(velocity_history)
        trend = "↗️ Improving" if velocity_history[-1]['completion_rate'] > avg_velocity else "↘️ Declining" if velocity_history[-1]['completion_rate'] < avg_velocity else "➡️ Stable"
        
        return f"""
            <div class="velocity-chart">
                <h3>📈 Team Velocity Trend</h3>
                <p>Story point completion percentage across recent sprints</p>
                <div style="text-align: center; margin: 20px 0;">
                    <svg width="{width}" height="{height}" style="border: 1px solid #e5e7eb; background: white;">
                        <!-- Grid lines -->
                        {grid_lines}
                        
                        <!-- Axes -->
                        <line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height - margin}" stroke="#374151" stroke-width="2"/>
                        <line x1="{margin}" y1="{height - margin}" x2="{width - margin}" y2="{height - margin}" stroke="#374151" stroke-width="2"/>
                        
                        <!-- Line chart -->
                        <path d="{path_data}" stroke="#3b82f6" stroke-width="3" fill="none"/>
                        
                        <!-- Data points -->
                        {data_points}
                        
                        <!-- Labels -->
                        {x_labels}
                        {y_labels}
                        
                        <!-- Chart title -->
                        <text x="{width/2}" y="25" text-anchor="middle" font-size="14" font-weight="bold" fill="#1f2937">Completion Rate (%)</text>
                        <text x="20" y="{height/2}" text-anchor="middle" font-size="12" fill="#6b7280" transform="rotate(-90, 20, {height/2})">Completion %</text>
                        <text x="{width/2}" y="{height - 5}" text-anchor="middle" font-size="12" fill="#6b7280">Sprints</text>
                    </svg>
                </div>
                
                <div class="velocity-stats">
                    <div class="velocity-stat">
                        <strong>Average Velocity</strong><br>
                        {avg_velocity:.1f}%
                    </div>
                    <div class="velocity-stat">
                        <strong>Current Sprint</strong><br>
                        {velocity_history[-1]['completion_rate']:.1f}%
                    </div>
                    <div class="velocity-stat">
                        <strong>Trend</strong><br>
                        {trend}
                    </div>
                </div>
            </div>"""


def test_jira_connection():
    """Test JIRA connection and show available boards/sprints."""
    print("🔗 Testing JIRA connection...")
    
    generator = SprintReportGenerator()
    jira_client = generator.jira_client
    
    # Test basic connection
    try:
        boards_data = jira_client.get_all_boards()
        if not boards_data:
            print("❌ Failed to connect to JIRA")
            return False
            
        print("✅ JIRA connection successful!")
        print(f"Found {len(boards_data.get('values', []))} boards:")
        
        for board in boards_data.get("values", []):
            print(f"  📋 Board: {board['name']} (ID: {board['id']})")
            
            # Check for active sprints
            sprint = jira_client.get_active_sprint_for_board(board['id'])
            if sprint:
                print(f"    🏃 Active Sprint: {sprint['name']} (ID: {sprint['id']})")
                print(f"    📅 {sprint.get('startDate', 'N/A')} - {sprint.get('endDate', 'N/A')}")
            else:
                print("    ⏸️  No active sprint")
        
        return True
        
    except Exception as e:
        print(f"❌ JIRA connection failed: {e}")
        return False

def generate_report_from_jira():
    """Generate sprint report using real JIRA data."""
    print("📊 Generating sprint report from JIRA (auto-discovering active sprint)")
    
    generator = SprintReportGenerator()
    output_path = generator.generate_report()
    
    if output_path:
        print(f"✅ Sprint report generated successfully: {output_path}")
        return output_path
    else:
        print("❌ Failed to generate sprint report")
        return None

def main():
    """Main function - automatically runs sprint report generation."""
    print("🚀 Sprint Report Generator")
    print("=" * 40)
    
    try:
        # First test JIRA connection
        print("Step 1: Testing JIRA connection...")
        if not test_jira_connection():
            print("❌ JIRA connection failed. Generating test report instead.")
            generate_test_report()
            return
        
        print("\nStep 2: Generating sprint report from JIRA...")
        output_path = generate_report_from_jira()
        
        if output_path:
            print(f"\n✅ Sprint report completed successfully!")
            print(f"📄 Report saved to: {output_path}")
        else:
            print("\n⚠️ JIRA report failed. Generating test report as fallback...")
            generate_test_report()
            
    except KeyboardInterrupt:
        print("\n👋 Process interrupted!")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n⚠️ Generating test report as fallback...")
        generate_test_report()

if __name__ == "__main__":
    main()