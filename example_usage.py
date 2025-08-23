#!/usr/bin/env python3
"""
Example usage of the Sprint Report Generator
"""

from sprint_report_generator import SprintReportGenerator
import json

def main():
    """Example of how to use the sprint report generator."""
    
    print("🚀 Sprint Report Generator - Example Usage")
    print("=" * 50)
    
    # Initialize the generator
    generator = SprintReportGenerator()
    
    # You can also provide mock data for testing without JIRA
    mock_sprint_data = {
        "sprint_id": "DEMO-1",
        "sprint_name": "Sprint #1 - Feature Development",
        "sprint_goal": "Implement user authentication and product catalog",
        "start_date": "2024-01-01",
        "end_date": "2024-01-14",
        "planned_story_points": 50,
        "completed_story_points": 45,
        "team_members": ["Mayank", "Parikshit", "Rashi", "Rohan"]
    }
    
    print(f"📊 Generating report for: {mock_sprint_data['sprint_name']}")
    print(f"📅 Duration: {mock_sprint_data['start_date']} to {mock_sprint_data['end_date']}")
    print(f"👥 Team: {', '.join(mock_sprint_data['team_members'])}")
    
    # For actual JIRA integration, uncomment and configure:
    # sprint_id = "123"  # Your actual JIRA sprint ID
    # board_id = "456"   # Your actual JIRA board ID
    # output_path = generator.generate_report(sprint_id, board_id)
    
    # For demo purposes with mock data:
    print("\n🔧 To use with real JIRA data:")
    print("1. Update config.json with your JIRA credentials")
    print("2. Replace sprint_id and board_id with actual values")
    print("3. Run: python sprint_report_generator.py")
    
    print("\n📝 Configuration required in config.json:")
    print(json.dumps({
        "jira": {
            "jira_url": "https://your-domain.atlassian.net",
            "username": "your-email@example.com",
            "api_token": "your-jira-api-token",
            "project_key": "PROJ",
            "board_id": "1"
        }
    }, indent=2))

if __name__ == "__main__":
    main()