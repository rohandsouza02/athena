# Epic Generation Feature - Athena AI Scrum Master

## Overview

The Epic Generation feature is a core component of Athena that automatically generates sprint user stories based on:

- **PRD (Product Requirements Document)**: Provides context about product goals and requirements
- **JIRA Integration**: Fetches current backlog, completed tasks, and incomplete work
- **AI Processing**: Uses OpenAI GPT-4 to analyze context and generate relevant stories
- **Smart Output**: Creates up to 10 user stories with acceptance criteria, story points, and priorities

## Key Features

✅ **JIRA Integration**: Connects to your JIRA project to fetch real context  
✅ **AI-Powered Generation**: Uses GPT-4 to create intelligent user stories  
✅ **Story Point Estimation**: Automatically estimates story points (1, 2, 3, 5, 8, 13)  
✅ **Dependency Tracking**: Identifies dependencies between stories  
✅ **Risk Assessment**: Provides risk analysis and recommendations  
✅ **Export to JIRA**: Can create stories directly in your JIRA project  
✅ **Structured Output**: Saves results in JSON format for further processing  

## Setup and Configuration

### 1. Environment Variables

Create a `.env` file with your JIRA credentials:

```bash
# JIRA Configuration
JIRA_BASE_URL=https://your-domain.atlassian.net/
JIRA_USERNAME=your-email@domain.com
JIRA_API_TOKEN=your-jira-api-token
JIRA_PROJECT_KEY=YOUR_PROJECT_KEY

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key

# Optional
LOG_LEVEL=INFO
```

### 2. JIRA API Token Setup

1. Go to [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click "Create API token"
3. Give it a label and copy the generated token
4. Use this token in your `.env` file

### 3. Install Dependencies

```bash
poetry install
# or
pip install openai python-dotenv requests
```

## Usage

### Command Line Interface

The easiest way to generate epics is using the CLI:

```bash
# Basic usage with PRD file
poetry run python3 epic_cli.py sample_prd.md

# With additional context
poetry run python3 epic_cli.py sample_prd.md --context "Focus on MVP features for Q1 release"

# With verbose logging
poetry run python3 epic_cli.py sample_prd.md --verbose
```

### Python API

You can also use the epic generator programmatically:

```python
from epic_generator import EpicGenerator
from jira_integration import JiraIntegration

# Initialize components
jira = JiraIntegration()
generator = EpicGenerator(jira)

# Load your PRD content
with open('your_prd.md', 'r') as f:
    prd_content = f.read()

# Generate epic
result = generator.generate_epic(
    prd_content=prd_content,
    additional_context="Any additional context"
)

# Access results
print(f"Generated {len(result.sprint_stories)} stories")
print(f"Sprint goal: {result.sprint_goal}")

# Save results
filename = generator.save_result(result)

# Export to JIRA (optional)
exported = generator.export_to_jira(result, create_issues=True)
```

## Output Structure

The epic generator creates structured output with the following components:

### Sprint Stories
Each story includes:
- **Title**: User story format ("As a [user], I want [goal] so that [benefit]")
- **Description**: Detailed story description
- **Acceptance Criteria**: 3-5 testable criteria in Given/When/Then format
- **Story Points**: Fibonacci estimation (1, 2, 3, 5, 8, 13)
- **Priority**: High, Medium, or Low
- **Dependencies**: References to other stories or JIRA tickets
- **Labels**: Categorization tags (e.g., "frontend", "api", "security")
- **Rationale**: Explanation of why this story is important

### Sprint Summary
- **Sprint Goal**: Clear, concise objective for the sprint
- **Total Story Points**: Sum of all story estimates (typically ~40 for 2-week sprints)
- **Risk Assessment**: Potential risks and mitigation strategies
- **Recommendations**: Actionable advice for the team

## Example Output

```json
{
  "sprint_goal": "Complete core platform features and improve user experience",
  "stories": [
    {
      "title": "As a product owner, I want automated story generation so that sprint planning is faster",
      "description": "Implement AI-powered story generation...",
      "acceptance_criteria": [
        "Given a PRD and project context, when I request story generation, then the system creates 5-10 relevant user stories",
        "Given generated stories, when I review them, then each story has clear acceptance criteria and story points"
      ],
      "story_points": 8,
      "priority": "High",
      "dependencies": ["SCRUM-101"],
      "labels": ["ai", "automation", "planning"],
      "rationale": "This addresses the core requirement for automated sprint planning from the PRD"
    }
  ],
  "total_story_points": 16,
  "risk_assessment": "Low risk - builds on existing JIRA integration...",
  "recommendations": [
    "Review generated stories with product owner before sprint commitment",
    "Start with smaller story point estimates for AI-generated work"
  ]
}
```

## JIRA Integration Details

### Supported JIRA Operations

- **Fetch Backlog**: Gets unassigned issues not in active sprints
- **Fetch Completed Work**: Retrieves recently completed issues (last 30 days)
- **Fetch Active Sprint**: Gets current sprint issues and their status
- **Create Stories**: Can create new user stories in JIRA
- **Story Points**: Handles custom field for story point estimation

### JIRA Query Examples

The integration uses JQL (JIRA Query Language) to fetch relevant data:

```sql
-- Backlog Issues
project = "SCRUM" AND status NOT IN ("Done", "Closed", "Resolved") AND sprint is EMPTY

-- Recently Completed
project = "SCRUM" AND status IN ("Done", "Closed", "Resolved") AND resolved >= "2024-07-24"

-- Active Sprint Issues
project = "SCRUM" AND sprint = 123
```

## Configuration Options

### Epic Generator Settings

```python
generator = EpicGenerator(jira_integration)
generator.max_sprint_stories = 10        # Maximum stories per sprint
generator.target_story_points = 40       # Target total story points
```

### AI Model Configuration

The generator uses GPT-4 with the following settings:
- **Temperature**: 0.7 (balanced creativity and consistency)
- **Max Tokens**: 4000 (sufficient for detailed stories)
- **Model**: gpt-4 (for best reasoning and structure)

## Testing

### Run the Test Suite

```bash
# Run comprehensive test with real JIRA data
poetry run python3 test_epic_generation.py

# The test will:
# 1. Connect to JIRA and fetch project data
# 2. Generate epic using AI (or mock data if OpenAI key missing)
# 3. Display formatted results
# 4. Test JIRA export functionality
```

### Mock Data Testing

If JIRA or OpenAI are not available, the test automatically falls back to mock data to demonstrate the functionality.

## Troubleshooting

### Common Issues

1. **JIRA Connection Failed**
   - Check your JIRA credentials in `.env`
   - Verify JIRA_BASE_URL format (should end with `/`)
   - Ensure API token has proper permissions

2. **OpenAI API Error**
   - Verify OPENAI_API_KEY is set correctly
   - Check API quota and billing status
   - Ensure you have access to GPT-4 model

3. **No Backlog Issues Found**
   - Check JIRA_PROJECT_KEY is correct
   - Verify project has issues in backlog
   - Review JQL queries in logs for debugging

### Debug Mode

Enable verbose logging for detailed troubleshooting:

```bash
poetry run python3 epic_cli.py sample_prd.md --verbose
```

## Best Practices

### PRD Writing Tips

For best results, structure your PRD with:
- Clear objectives and success criteria
- Prioritized feature lists
- User personas and use cases
- Technical constraints and requirements
- Current sprint goals

### Review Process

1. **Generate Stories**: Use the tool to create initial stories
2. **Review with Team**: Discuss generated stories in planning meeting
3. **Refine Estimates**: Adjust story points based on team capacity
4. **Validate Dependencies**: Ensure dependency chains are logical
5. **Export to JIRA**: Create final stories in your project management tool

### Sprint Planning Integration

1. Run epic generation before sprint planning meeting
2. Share generated stories with team for pre-review
3. Use as starting point for planning discussion
4. Refine and adjust based on team input
5. Commit to final sprint backlog

## API Reference

### EpicGenerator Class

```python
class EpicGenerator:
    def __init__(self, jira_integration: JiraIntegration = None)
    def generate_epic(self, prd_content: str, additional_context: str = "") -> EpicGenerationResult
    def export_to_jira(self, result: EpicGenerationResult, create_issues: bool = False) -> List[Dict]
    def save_result(self, result: EpicGenerationResult, filename: str = None) -> str
```

### JiraIntegration Class

```python
class JiraIntegration:
    def __init__(self, base_url: str = None, username: str = None, api_token: str = None, project_key: str = None)
    def get_project_context(self) -> Dict
    def get_backlog_issues(self, max_results: int = 50) -> List[Dict]
    def get_completed_issues(self, days_back: int = 30) -> List[Dict]
    def create_story(self, summary: str, description: str, priority: str = "Medium", story_points: int = None, labels: List[str] = None) -> Optional[Dict]
```

## Contributing

To extend the epic generation feature:

1. **Custom AI Prompts**: Modify `_call_ai_for_epic_generation()` in `epic_generator.py`
2. **Additional JIRA Fields**: Extend `format_issue_for_context()` in `jira_integration.py`
3. **New Output Formats**: Add export functions to `EpicGenerator` class
4. **Enhanced CLI**: Extend `epic_cli.py` with new command-line options

## License

This feature is part of the Athena AI Scrum Master platform. Please refer to the main project license. 