#!/usr/bin/env python3
"""
Epic Generation CLI for Athena AI Scrum Master
Simple command-line interface for generating sprint epics
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from epic_generator import EpicGenerator
from jira_integration import JiraIntegration


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def load_prd_from_file(file_path: str) -> str:
    """Load PRD content from file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: PRD file not found: {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading PRD file: {e}")
        sys.exit(1)


def initialize_jira() -> JiraIntegration:
    """Initialize JIRA integration with credentials"""
    try:
        jira = JiraIntegration()
        # Test connection
        project_info = jira.get_project_info()
        if not project_info:
            raise Exception("Failed to connect to JIRA project")
        
        print(f"✓ Connected to JIRA project: {project_info.get('name')}")
        return jira
        
    except Exception as e:
        print(f"Error connecting to JIRA: {e}")
        print("Please check your JIRA credentials in environment variables:")
        print("- JIRA_BASE_URL")
        print("- JIRA_USERNAME") 
        print("- JIRA_API_TOKEN")
        print("- JIRA_PROJECT_KEY")
        sys.exit(1)


def generate_epic(prd_content: str, jira: JiraIntegration, 
                 additional_context: str = "") -> None:
    """Generate epic and display results"""
    try:
        print("🤖 Generating epic with AI...")
        
        generator = EpicGenerator(jira)
        result = generator.generate_epic(prd_content, additional_context)
        
        print("✅ Epic generation completed!")
        print(f"📊 Generated {len(result.sprint_stories)} stories")
        print(f"🎯 Total story points: {result.total_story_points}")
        
        # Display results
        display_epic_results(result)
        
        # Save results
        filename = generator.save_result(result)
        print(f"💾 Results saved to: {filename}")
        
        # Ask if user wants to export to JIRA
        if input("\n🔄 Export stories to JIRA? (y/N): ").lower() == 'y':
            export_to_jira(generator, result)
        
    except Exception as e:
        print(f"❌ Epic generation failed: {e}")
        sys.exit(1)


def display_epic_results(result) -> None:
    """Display epic generation results in a formatted way"""
    print("\n" + "="*80)
    print("🎯 SPRINT GOAL")
    print("="*80)
    print(result.sprint_goal)
    
    print("\n" + "="*80)
    print("📋 GENERATED STORIES")
    print("="*80)
    
    for i, story in enumerate(result.sprint_stories, 1):
        print(f"\n{i}. {story.title}")
        print(f"   📝 Description: {story.description}")
        print(f"   🔢 Story Points: {story.story_points}")
        print(f"   ⚡ Priority: {story.priority}")
        print(f"   🏷️  Labels: {', '.join(story.labels)}")
        
        if story.dependencies:
            print(f"   🔗 Dependencies: {', '.join(story.dependencies)}")
        
        print(f"   💡 Rationale: {story.rationale}")
        
        print("   ✅ Acceptance Criteria:")
        for j, criteria in enumerate(story.acceptance_criteria, 1):
            print(f"      {j}. {criteria}")
    
    print(f"\n{'='*80}")
    print("📊 SPRINT SUMMARY")
    print(f"{'='*80}")
    print(f"Total Stories: {len(result.sprint_stories)}")
    print(f"Total Story Points: {result.total_story_points}")
    print(f"Risk Assessment: {result.risk_assessment}")
    
    print("\n🎯 Recommendations:")
    for rec in result.recommendations:
        print(f"  • {rec}")


def export_to_jira(generator: EpicGenerator, result) -> None:
    """Export generated stories to JIRA"""
    try:
        print("🔄 Exporting stories to JIRA...")
        
        exported_stories = generator.export_to_jira(result, create_issues=True)
        
        print(f"✅ Successfully exported {len(exported_stories)} stories to JIRA!")
        
        for story in exported_stories:
            if 'jira_key' in story:
                print(f"  📝 {story['jira_key']}: {story['summary']}")
                if 'jira_url' in story:
                    print(f"     🔗 {story['jira_url']}")
        
    except Exception as e:
        print(f"❌ JIRA export failed: {e}")


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="Generate sprint epics using AI and JIRA integration"
    )
    
    parser.add_argument(
        'prd_file',
        help='Path to PRD (Product Requirements Document) file'
    )
    
    parser.add_argument(
        '--context', '-c',
        help='Additional context for epic generation',
        default=""
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    print("🚀 Athena Epic Generator")
    print("="*50)
    
    # Load PRD
    print(f"📖 Loading PRD from: {args.prd_file}")
    prd_content = load_prd_from_file(args.prd_file)
    print(f"✅ Loaded PRD ({len(prd_content)} characters)")
    
    # Initialize JIRA
    print("🔌 Connecting to JIRA...")
    jira = initialize_jira()
    
    # Generate epic
    generate_epic(prd_content, jira, args.context)
    
    print("\n🎉 Epic generation completed successfully!")


if __name__ == "__main__":
    main() 