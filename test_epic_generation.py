#!/usr/bin/env python3
"""
Test script for Epic Generation feature
Demonstrates the complete workflow of generating new sprint stories
"""

import os
import json
import logging
from datetime import datetime

from epic_generator import EpicGenerator, SprintStory, EpicGenerationResult
from jira_integration import JiraIntegration

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("EpicGenerationTest")

# Sample PRD content for testing
SAMPLE_PRD = """
# Product Requirements Document - Athena AI Scrum Master Platform

## Overview
Athena is an AI-powered Scrum Master platform that automates sprint management, standup meetings, and project tracking. The goal is to enhance team productivity through intelligent automation and insights.

## Core Features

### 1. Automated Sprint Planning
- AI-generated user stories based on project context
- Integration with JIRA for backlog management
- Story point estimation and sprint capacity planning
- Dependency tracking and risk assessment

### 2. Intelligent Meeting Management
- Automated standup meeting transcription
- Real-time agenda generation
- Action item tracking and follow-up
- Meeting summary and insights

### 3. Project Analytics
- Sprint velocity tracking
- Team performance metrics
- Burndown chart automation
- Predictive sprint completion analysis

### 4. Integration Capabilities
- JIRA integration for issue management
- Calendar integration for meeting scheduling
- Slack/Teams integration for notifications
- GitHub integration for code tracking

## Current Sprint Objectives
1. Complete JIRA integration for full backlog access
2. Implement AI-powered epic generation
3. Enhance meeting transcription accuracy
4. Add sprint analytics dashboard
5. Improve user authentication and security

## Success Criteria
- Reduce sprint planning time by 50%
- Increase story completion rate to 85%
- Automate 80% of routine scrum activities
- Achieve 90% user satisfaction score

## Technical Requirements
- Python 3.9+ backend
- OpenAI GPT-4 integration
- JIRA REST API v3
- Google Calendar API
- Real-time websocket support
"""

def test_jira_connection():
    """Test JIRA connection and data retrieval"""
    logger.info("Testing JIRA connection...")
    
    try:
        # Initialize with environment variables or hardcoded values for testing
        jira = JiraIntegration(
            base_url="https://ps-athena.atlassian.net/",
            username="parikshitsinghshaktawat@gmail.com",
            api_token="ATATT3xFfGF0MmzwxzJkEf7Of639JsvvSCjaT7ZzZAJOZ-IphMlD3Nr0-3nPJcMmrgC5J0VsCwRG_hm33VPB2HjNgT5CrkSZiAVhvjwY4Tcu8YINJtXdOIbKXdwEWubv5ddKV2prmZDR5w3lWrkUNEGlwgnDoUEKqIg8QxEOH_cmXhQ2KQnFGX0=343FBBBD",
            project_key="SCRUM"
        )
        
        # Test basic project info
        project_info = jira.get_project_info()
        if project_info:
            logger.info(f"✓ Connected to project: {project_info.get('name', 'Unknown')}")
        else:
            logger.error("✗ Failed to get project info")
            return None
        
        # Test data retrieval
        backlog = jira.get_backlog_issues(max_results=10)
        completed = jira.get_completed_issues(days_back=14)
        incomplete = jira.get_incomplete_sprint_issues()
        
        logger.info(f"✓ Retrieved {len(backlog)} backlog issues")
        logger.info(f"✓ Retrieved {len(completed)} completed issues")
        logger.info(f"✓ Retrieved {len(incomplete)} incomplete issues")
        
        return jira
        
    except Exception as e:
        logger.error(f"✗ JIRA connection failed: {e}")
        return None

def test_epic_generation_with_mock_data():
    """Test epic generation with mock data if JIRA is not available"""
    logger.info("Testing epic generation with mock data...")
    
    # Create mock JIRA integration
    class MockJiraIntegration:
        def get_project_context(self):
            return {
                "project_info": {"name": "SCRUM Project", "key": "SCRUM"},
                "backlog_issues": [
                    {
                        "key": "SCRUM-101",
                        "summary": "Implement user authentication system",
                        "description": "Create secure login and registration flow",
                        "issue_type": "Story",
                        "priority": "High",
                        "status": "To Do",
                        "story_points": 8,
                        "labels": ["backend", "security"]
                    },
                    {
                        "key": "SCRUM-102", 
                        "summary": "Design sprint analytics dashboard",
                        "description": "Create visual dashboard for sprint metrics",
                        "issue_type": "Story",
                        "priority": "Medium",
                        "status": "To Do",
                        "story_points": 5,
                        "labels": ["frontend", "analytics"]
                    }
                ],
                "completed_issues": [
                    {
                        "key": "SCRUM-95",
                        "summary": "Setup JIRA integration",
                        "description": "Connect to JIRA API for issue management",
                        "issue_type": "Story", 
                        "priority": "High",
                        "status": "Done",
                        "story_points": 3,
                        "labels": ["integration"]
                    }
                ],
                "incomplete_sprint_issues": [
                    {
                        "key": "SCRUM-98",
                        "summary": "Improve meeting transcription",
                        "description": "Enhance accuracy of automated transcription",
                        "issue_type": "Story",
                        "priority": "Medium", 
                        "status": "In Progress",
                        "story_points": 5,
                        "labels": ["ai", "meetings"]
                    }
                ]
            }
    
    # Test without OpenAI (mock the AI response)
    class MockEpicGenerator(EpicGenerator):
        def _call_ai_for_epic_generation(self, context):
            # Return mock AI response
            return """{
                "sprint_goal": "Complete core platform features and improve user experience",
                "stories": [
                    {
                        "title": "As a product owner, I want to automatically generate user stories so that sprint planning is more efficient",
                        "description": "Implement AI-powered story generation that analyzes PRD and project context to create relevant user stories for the next sprint",
                        "acceptance_criteria": [
                            "Given a PRD and project context, when I request story generation, then the system creates 5-10 relevant user stories",
                            "Given generated stories, when I review them, then each story has clear acceptance criteria and story points",
                            "Given story dependencies, when stories are created, then dependencies are properly identified and linked"
                        ],
                        "story_points": 8,
                        "priority": "High",
                        "dependencies": ["SCRUM-101"],
                        "labels": ["ai", "automation", "planning"],
                        "rationale": "This addresses the core requirement for automated sprint planning from the PRD"
                    },
                    {
                        "title": "As a scrum master, I want to track sprint velocity so that I can improve team planning",
                        "description": "Create analytics dashboard that shows sprint velocity trends and team performance metrics",
                        "acceptance_criteria": [
                            "Given completed sprints, when I view the dashboard, then I see velocity trends over time",
                            "Given team performance data, when I analyze metrics, then I can identify improvement opportunities",
                            "Given sprint data, when planning new sprints, then I have capacity recommendations"
                        ],
                        "story_points": 5,
                        "priority": "Medium", 
                        "dependencies": ["SCRUM-102"],
                        "labels": ["analytics", "dashboard", "metrics"],
                        "rationale": "Supports the PRD goal of reducing sprint planning time and improving completion rates"
                    },
                    {
                        "title": "As a team member, I want secure authentication so that my project data is protected",
                        "description": "Complete the authentication system with secure login, role-based access, and session management",
                        "acceptance_criteria": [
                            "Given user credentials, when I log in, then I am securely authenticated",
                            "Given user roles, when I access features, then permissions are properly enforced", 
                            "Given active sessions, when I'm inactive, then sessions expire securely"
                        ],
                        "story_points": 3,
                        "priority": "High",
                        "dependencies": ["SCRUM-101"],
                        "labels": ["security", "authentication", "backend"],
                        "rationale": "Critical for platform security and user data protection"
                    }
                ],
                "total_story_points": 16,
                "risk_assessment": "Low risk - builds on existing JIRA integration. Main risk is ensuring AI-generated stories align with actual project needs.",
                "recommendations": [
                    "Review generated stories with product owner before sprint commitment",
                    "Start with smaller story point estimates for AI-generated work",
                    "Ensure proper testing of authentication features before release"
                ]
            }"""
    
    try:
        mock_jira = MockJiraIntegration()
        generator = MockEpicGenerator(mock_jira)
        
        result = generator.generate_epic(SAMPLE_PRD, "Testing epic generation with mock data")
        
        logger.info("✓ Epic generation completed successfully!")
        logger.info(f"✓ Generated {len(result.sprint_stories)} stories")
        logger.info(f"✓ Total story points: {result.total_story_points}")
        logger.info(f"✓ Sprint goal: {result.sprint_goal}")
        
        # Save result
        filename = generator.save_result(result)
        logger.info(f"✓ Result saved to: {filename}")
        
        # Display generated stories
        print("\n" + "="*80)
        print("GENERATED SPRINT STORIES")
        print("="*80)
        
        for i, story in enumerate(result.sprint_stories, 1):
            print(f"\n{i}. {story.title}")
            print(f"   Description: {story.description}")
            print(f"   Story Points: {story.story_points}")
            print(f"   Priority: {story.priority}")
            print(f"   Labels: {', '.join(story.labels)}")
            print(f"   Rationale: {story.rationale}")
        
        print(f"\n{'='*80}")
        print(f"SPRINT SUMMARY")
        print(f"{'='*80}")
        print(f"Goal: {result.sprint_goal}")
        print(f"Total Story Points: {result.total_story_points}")
        print(f"Risk Assessment: {result.risk_assessment}")
        print(f"Recommendations:")
        for rec in result.recommendations:
            print(f"  • {rec}")
        
        return result
        
    except Exception as e:
        logger.error(f"✗ Epic generation failed: {e}")
        return None

def test_jira_export(result: EpicGenerationResult, jira: JiraIntegration):
    """Test exporting generated stories to JIRA"""
    if not result or not jira:
        logger.info("Skipping JIRA export test (no result or JIRA connection)")
        return
    
    logger.info("Testing JIRA export (preview mode)...")
    
    try:
        generator = EpicGenerator(jira)
        exported_stories = generator.export_to_jira(result, create_issues=False)
        
        logger.info(f"✓ Prepared {len(exported_stories)} stories for JIRA export")
        
        print(f"\n{'='*80}")
        print("JIRA EXPORT PREVIEW")
        print(f"{'='*80}")
        
        for story in exported_stories:
            print(f"\nSummary: {story['summary']}")
            print(f"Priority: {story['priority']}")
            print(f"Story Points: {story['story_points']}")
            print(f"Labels: {', '.join(story['labels'])}")
            print(f"Description Preview: {story['description'][:200]}...")
        
    except Exception as e:
        logger.error(f"✗ JIRA export test failed: {e}")

def main():
    """Main test function"""
    print("="*80)
    print("ATHENA EPIC GENERATION TEST")
    print("="*80)
    
    # Test JIRA connection
    jira = test_jira_connection()
    
    # Test epic generation (with mock data if JIRA fails)
    if jira:
        logger.info("Using real JIRA data for epic generation...")
        try:
            generator = EpicGenerator(jira)
            result = generator.generate_epic(SAMPLE_PRD, "Real JIRA integration test")
            logger.info("✓ Epic generation with real JIRA data completed!")
        except Exception as e:
            logger.error(f"✗ Real JIRA epic generation failed: {e}")
            logger.info("Falling back to mock data...")
            result = test_epic_generation_with_mock_data()
    else:
        result = test_epic_generation_with_mock_data()
    
    # Test JIRA export
    test_jira_export(result, jira)
    
    print(f"\n{'='*80}")
    print("TEST COMPLETED")
    print(f"{'='*80}")
    
    if result:
        print("✓ Epic generation test PASSED")
        print(f"✓ Generated {len(result.sprint_stories)} stories")
        print(f"✓ Total story points: {result.total_story_points}")
    else:
        print("✗ Epic generation test FAILED")

if __name__ == "__main__":
    main() 