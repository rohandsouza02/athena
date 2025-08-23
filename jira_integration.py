#!/usr/bin/env python3
"""
JIRA Integration Module for Athena AI Scrum Master
Handles JIRA API interactions for fetching backlogs, completed tasks, and managing sprints
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import base64

import requests
from dotenv import load_dotenv
import os

load_dotenv()


class JiraIntegration:
    """JIRA API integration for fetching project data"""
    
    def __init__(self, base_url: str = None, username: str = None, api_token: str = None, project_key: str = None):
        """Initialize JIRA integration"""
        self.base_url = base_url or os.getenv("JIRA_BASE_URL")
        self.username = username or os.getenv("JIRA_USERNAME") 
        self.api_token = api_token or os.getenv("JIRA_API_TOKEN")
        self.project_key = project_key or os.getenv("JIRA_PROJECT_KEY")
        
        if not all([self.base_url, self.username, self.api_token, self.project_key]):
            raise ValueError("Missing required JIRA configuration")
        
        # Remove trailing slash
        self.base_url = self.base_url.rstrip('/')
        
        # Setup authentication
        self.auth_string = base64.b64encode(f"{self.username}:{self.api_token}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {self.auth_string}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        self.logger = logging.getLogger("JiraIntegration")
        
    def _make_request(self, endpoint: str, method: str = "GET", data: Dict = None) -> Optional[Dict]:
        """Make authenticated request to JIRA API"""
        url = f"{self.base_url}/rest/api/3{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"JIRA API error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"JIRA API request failed: {e}")
            return None
    
    def get_project_info(self) -> Optional[Dict]:
        """Get basic project information"""
        return self._make_request(f"/project/{self.project_key}")
    
    def get_backlog_issues(self, max_results: int = 50) -> List[Dict]:
        """Get backlog issues (not in active sprint)"""
        # Updated JQL to better capture backlog items
        jql = f'project = "{self.project_key}" AND status NOT IN ("Done", "Closed", "Resolved") AND sprint is EMPTY ORDER BY priority DESC, created ASC'
        
        response = self._make_request(f"/search?jql={jql}&maxResults={max_results}&fields=*all")
        if response:
            return response.get("issues", [])
        return []
    
    def get_completed_issues(self, days_back: int = 30) -> List[Dict]:
        """Get completed issues from recent sprints"""
        since_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        jql = f'project = "{self.project_key}" AND status IN ("Done", "Closed", "Resolved") AND resolved >= "{since_date}" ORDER BY resolved DESC'
        
        response = self._make_request(f"/search?jql={jql}&maxResults=100&fields=*all")
        if response:
            return response.get("issues", [])
        return []
    
    def get_active_sprint_issues(self) -> List[Dict]:
        """Get issues in active sprint"""
        # Get active sprints for the project
        board_id = self._get_board_id()
        if not board_id:
            return []
        
        sprints_response = self._make_request(f"/board/{board_id}/sprint?state=active")
        if not sprints_response or not sprints_response.get("values"):
            return []
        
        active_sprint = sprints_response["values"][0]
        sprint_id = active_sprint["id"]
        
        # Get issues in active sprint
        jql = f'project = "{self.project_key}" AND sprint = {sprint_id} ORDER BY status ASC'
        response = self._make_request(f"/search?jql={jql}&maxResults=100")
        if response:
            return response.get("issues", [])
        return []
    
    def get_incomplete_sprint_issues(self) -> List[Dict]:
        """Get incomplete issues from active sprint"""
        active_issues = self.get_active_sprint_issues()
        incomplete_issues = []
        
        for issue in active_issues:
            status = issue["fields"]["status"]["name"]
            if status.lower() not in ["done", "closed", "resolved"]:
                incomplete_issues.append(issue)
        
        return incomplete_issues
    
    def _get_board_id(self) -> Optional[int]:
        """Get the first board ID for the project"""
        response = self._make_request("/board?projectKeyOrId=" + self.project_key)
        if response and response.get("values"):
            return response["values"][0]["id"]
        return None
    
    def format_issue_for_context(self, issue: Dict) -> Dict:
        """Format JIRA issue for use in AI prompts"""
        fields = issue.get("fields", {})
        
        return {
            "key": issue.get("key"),
            "summary": fields.get("summary"),
            "description": fields.get("description", ""),
            "issue_type": fields.get("issuetype", {}).get("name"),
            "priority": fields.get("priority", {}).get("name"),
            "status": fields.get("status", {}).get("name"),
            "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
            "story_points": fields.get("customfield_10016"),  # Common story points field
            "labels": fields.get("labels", []),
            "components": [c["name"] for c in fields.get("components", [])],
            "created": fields.get("created"),
            "updated": fields.get("updated")
        }
    
    def get_project_context(self) -> Dict:
        """Get comprehensive project context for epic generation"""
        context = {
            "project_info": self.get_project_info(),
            "backlog_issues": [self.format_issue_for_context(issue) for issue in self.get_backlog_issues()],
            "completed_issues": [self.format_issue_for_context(issue) for issue in self.get_completed_issues()],
            "incomplete_sprint_issues": [self.format_issue_for_context(issue) for issue in self.get_incomplete_sprint_issues()],
            "active_sprint_issues": [self.format_issue_for_context(issue) for issue in self.get_active_sprint_issues()]
        }
        
        self.logger.info(f"Retrieved JIRA context: "
                        f"{len(context['backlog_issues'])} backlog, "
                        f"{len(context['completed_issues'])} completed, "
                        f"{len(context['incomplete_sprint_issues'])} incomplete")
        
        return context
    
    def create_issue(self, issue_data: Dict) -> Optional[Dict]:
        """Create a new JIRA issue"""
        return self._make_request("/issue", method="POST", data=issue_data)
    
    def create_story(self, summary: str, description: str, priority: str = "Medium", 
                    story_points: int = None, labels: List[str] = None) -> Optional[Dict]:
        """Create a user story in JIRA"""
        issue_data = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "text": description,
                                    "type": "text"
                                }
                            ]
                        }
                    ]
                },
                "issuetype": {"name": "Story"},
                "priority": {"name": priority}
            }
        }
        
        # Add story points if provided
        if story_points:
            issue_data["fields"]["customfield_10016"] = story_points
        
        # Add labels if provided
        if labels:
            issue_data["fields"]["labels"] = labels
        
        return self.create_issue(issue_data)