#!/usr/bin/env python3
"""
Epic Generation Module for Athena AI Scrum Master
Generates new sprint stories based on PRD, JIRA context, and completed work
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

import openai
from dotenv import load_dotenv
import os

from jira_integration import JiraIntegration

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


@dataclass
class SprintStory:
    """Represents a story for the next sprint"""
    title: str
    description: str
    acceptance_criteria: List[str]
    priority: str  # High, Medium, Low
    story_points: int
    dependencies: List[str]
    labels: List[str]
    assignee_suggestion: Optional[str] = None
    rationale: str = ""  # Why this story is important for next sprint


@dataclass
class EpicGenerationResult:
    """Result of epic generation process"""
    sprint_stories: List[SprintStory]
    total_story_points: int
    sprint_goal: str
    rationale: str
    risk_assessment: str
    recommendations: List[str]
    generated_at: datetime


class EpicGenerator:
    """AI-powered epic and story generation for next sprint"""
    
    def __init__(self, jira_integration: JiraIntegration = None):
        """Initialize epic generator"""
        self.jira = jira_integration or JiraIntegration()
        
        # Initialize OpenAI
        openai.api_key = OPENAI_API_KEY
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        self.logger = logging.getLogger("EpicGenerator")
        
        # Configuration
        self.max_sprint_stories = 10
        self.target_story_points = 40  # Typical 2-week sprint capacity
    
    def generate_epic(self, prd_content: str, additional_context: str = "") -> EpicGenerationResult:
        """Generate new epic based on PRD and JIRA context"""
        try:
            # Get JIRA context
            jira_context = self.jira.get_project_context()
            
            # Prepare context for AI
            context = self._prepare_context(prd_content, jira_context, additional_context)
            
            # Generate stories using AI
            ai_response = self._call_ai_for_epic_generation(context)
            
            # Parse and validate response
            result = self._parse_ai_response(ai_response)
            
            self.logger.info(f"Generated {len(result.sprint_stories)} stories for next sprint")
            return result
            
        except Exception as e:
            self.logger.error(f"Epic generation failed: {e}")
            raise
    
    def _prepare_context(self, prd_content: str, jira_context: Dict, additional_context: str) -> Dict:
        """Prepare comprehensive context for AI"""
        
        # Summarize JIRA data
        backlog_summary = self._summarize_issues(jira_context.get("backlog_issues", []))
        completed_summary = self._summarize_issues(jira_context.get("completed_issues", []))
        incomplete_summary = self._summarize_issues(jira_context.get("incomplete_sprint_issues", []))
        
        context = {
            "prd_content": prd_content,
            "project_info": jira_context.get("project_info", {}),
            "backlog_summary": backlog_summary,
            "completed_work_summary": completed_summary,
            "incomplete_work_summary": incomplete_summary,
            "additional_context": additional_context,
            "constraints": {
                "max_stories": self.max_sprint_stories,
                "target_story_points": self.target_story_points
            }
        }
        
        return context
    
    def _summarize_issues(self, issues: List[Dict]) -> Dict:
        """Summarize JIRA issues for context"""
        if not issues:
            return {"count": 0, "issues": []}
        
        summarized = []
        total_points = 0
        
        for issue in issues[:20]:  # Limit to prevent token overflow
            summary = {
                "key": issue.get("key"),
                "title": issue.get("summary"),
                "type": issue.get("issue_type"),
                "priority": issue.get("priority"),
                "status": issue.get("status"),
                "points": issue.get("story_points") or 0
            }
            
            if issue.get("description"):
                # Truncate long descriptions
                desc = issue["description"][:200]
                if len(issue["description"]) > 200:
                    desc += "..."
                summary["description"] = desc
            
            summarized.append(summary)
            total_points += summary["points"]
        
        return {
            "count": len(issues),
            "total_story_points": total_points,
            "issues": summarized
        }
    
    def _call_ai_for_epic_generation(self, context: Dict) -> str:
        """Call OpenAI API for epic generation"""
        
        system_prompt = """You are an expert AI Scrum Master and Product Manager. Your task is to generate a comprehensive sprint plan with user stories based on:

1. Product Requirements Document (PRD)
2. Current backlog items
3. Recently completed work
4. Incomplete work from current sprint

Your goal is to create 5-10 user stories for the next sprint that:
- Align with the PRD objectives
- Build upon completed work
- Address any incomplete items from current sprint
- Consider backlog priorities
- Stay within story point limits (typically 40 points for a 2-week sprint)

For each story, provide:
- Clear title and description
- Detailed acceptance criteria (3-5 criteria each)
- Story point estimate (1, 2, 3, 5, 8, 13)
- Priority (High/Medium/Low)
- Dependencies on other stories
- Suggested labels/tags
- Rationale for including in next sprint

Also provide:
- Overall sprint goal
- Risk assessment
- Recommendations for the team

Format your response as a JSON object with the specified structure."""

        user_prompt = f"""
PRD Content:
{context['prd_content']}

Current Backlog ({context['backlog_summary']['count']} items, {context['backlog_summary']['total_story_points']} points):
{json.dumps(context['backlog_summary']['issues'], indent=2)}

Recently Completed Work ({context['completed_work_summary']['count']} items):
{json.dumps(context['completed_work_summary']['issues'], indent=2)}

Incomplete Current Sprint Work ({context['incomplete_work_summary']['count']} items):
{json.dumps(context['incomplete_work_summary']['issues'], indent=2)}

Additional Context:
{context['additional_context']}

Constraints:
- Maximum {context['constraints']['max_stories']} stories
- Target ~{context['constraints']['target_story_points']} story points total

Please generate a comprehensive sprint plan with user stories in the following JSON format:
{{
  "sprint_goal": "Clear, concise sprint goal",
  "stories": [
    {{
      "title": "As a [user], I want [goal] so that [benefit]",
      "description": "Detailed description of the story",
      "acceptance_criteria": [
        "Given [context], when [action], then [outcome]",
        "..."
      ],
      "story_points": 5,
      "priority": "High|Medium|Low", 
      "dependencies": ["STORY-123", "Another dependency"],
      "labels": ["frontend", "api", "feature"],
      "rationale": "Why this story is important for next sprint"
    }}
  ],
  "total_story_points": 40,
  "risk_assessment": "Potential risks and mitigation strategies",
  "recommendations": ["Recommendation 1", "Recommendation 2"]
}}
"""

        try:
            response = openai.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"OpenAI API call failed: {e}")
            raise
    
    def _parse_ai_response(self, ai_response: str) -> EpicGenerationResult:
        """Parse AI response into structured result"""
        try:
            # Extract JSON from response (handle potential markdown formatting)
            json_start = ai_response.find('{')
            json_end = ai_response.rfind('}') + 1
            json_str = ai_response[json_start:json_end]
            
            data = json.loads(json_str)
            
            # Convert stories to SprintStory objects
            stories = []
            for story_data in data.get("stories", []):
                story = SprintStory(
                    title=story_data.get("title", ""),
                    description=story_data.get("description", ""),
                    acceptance_criteria=story_data.get("acceptance_criteria", []),
                    priority=story_data.get("priority", "Medium"),
                    story_points=story_data.get("story_points", 3),
                    dependencies=story_data.get("dependencies", []),
                    labels=story_data.get("labels", []),
                    rationale=story_data.get("rationale", "")
                )
                stories.append(story)
            
            # Create result
            result = EpicGenerationResult(
                sprint_stories=stories,
                total_story_points=data.get("total_story_points", sum(s.story_points for s in stories)),
                sprint_goal=data.get("sprint_goal", ""),
                rationale="Generated based on PRD and JIRA context",
                risk_assessment=data.get("risk_assessment", ""),
                recommendations=data.get("recommendations", []),
                generated_at=datetime.now()
            )
            
            return result
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse AI response as JSON: {e}")
            self.logger.error(f"AI Response: {ai_response[:500]}...")
            raise ValueError(f"Invalid AI response format: {e}")
        except Exception as e:
            self.logger.error(f"Error parsing AI response: {e}")
            raise
    
    def export_to_jira(self, result: EpicGenerationResult, create_issues: bool = False) -> List[Dict]:
        """Export generated stories to JIRA (optionally create them)"""
        exported_stories = []
        
        for story in result.sprint_stories:
            jira_story_data = {
                "summary": story.title,
                "description": self._format_description_for_jira(story),
                "priority": story.priority,
                "story_points": story.story_points,
                "labels": story.labels + ["ai-generated"]
            }
            
            if create_issues:
                created_issue = self.jira.create_story(**jira_story_data)
                if created_issue:
                    jira_story_data["jira_key"] = created_issue.get("key")
                    jira_story_data["jira_url"] = f"{self.jira.base_url}/browse/{created_issue.get('key')}"
            
            exported_stories.append(jira_story_data)
        
        return exported_stories
    
    def _format_description_for_jira(self, story: SprintStory) -> str:
        """Format story description for JIRA"""
        description = f"{story.description}\n\n"
        description += "h3. Acceptance Criteria\n"
        
        for i, criteria in enumerate(story.acceptance_criteria, 1):
            description += f"# {criteria}\n"
        
        if story.dependencies:
            description += "\nh3. Dependencies\n"
            for dep in story.dependencies:
                description += f"* {dep}\n"
        
        if story.rationale:
            description += f"\nh3. Rationale\n{story.rationale}\n"
        
        description += f"\n_Generated by AI on {datetime.now().strftime('%Y-%m-%d %H:%M')}_"
        
        return description
    
    def save_result(self, result: EpicGenerationResult, filename: str = None) -> str:
        """Save generation result to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"epic_generation_{timestamp}.json"
        
        # Convert to serializable format
        result_dict = asdict(result)
        result_dict["generated_at"] = result.generated_at.isoformat()
        
        with open(filename, 'w') as f:
            json.dump(result_dict, f, indent=2)
        
        self.logger.info(f"Epic generation result saved to {filename}")
        return filename