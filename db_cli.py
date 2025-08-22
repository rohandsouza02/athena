#!/usr/bin/env python3
"""
Database CLI tool for standup automation system.
Provides command-line interface for database operations.
"""

import argparse
import json
from datetime import datetime
from database import StandupDatabase


def main():
    parser = argparse.ArgumentParser(description='Standup Database CLI')
    parser.add_argument('--db', default='standup.db', help='Database file path')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show database statistics')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List standups')
    list_parser.add_argument('-n', '--limit', type=int, default=10, 
                           help='Number of records to show')
    list_parser.add_argument('--recent', type=int, 
                           help='Show standups from last N days')
    
    # Get command
    get_parser = subparsers.add_parser('get', help='Get standup by date or ID')
    get_parser.add_argument('identifier', help='Date (YYYY-MM-DD) or ID')
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete standup by ID')
    delete_parser.add_argument('id', type=int, help='Standup ID to delete')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add standup manually')
    add_parser.add_argument('--date', required=True, help='Date (YYYY-MM-DD)')
    add_parser.add_argument('--description', required=True, help='Standup description')
    add_parser.add_argument('--trigger', default='manual', help='Trigger event')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    db = StandupDatabase(args.db)
    
    if args.command == 'stats':
        stats = db.get_standup_stats()
        print("📊 Standup Database Statistics:")
        print(f"Total standups: {stats.get('total_standups', 0)}")
        print(f"Recent (30 days): {stats.get('recent_30_days', 0)}")
        print(f"Posted to Slack: {stats.get('slack_posted', 0)}")
        print("Trigger events:")
        for trigger, count in stats.get('trigger_events', {}).items():
            print(f"  {trigger}: {count}")
    
    elif args.command == 'list':
        if args.recent:
            standups = db.get_recent_standups(args.recent)
            print(f"📅 Standups from last {args.recent} days:")
        else:
            standups = db.get_all_standups(args.limit)
            print(f"📋 Last {args.limit} standups:")
        
        for standup in standups:
            print(f"\n{standup['date']} (ID: {standup['id']})")
            print(f"Trigger: {standup['trigger_event']}")
            print(f"Description: {standup['description'][:100]}...")
            print(f"Slack Posted: {'✅' if standup['slack_posted'] else '❌'}")
            print(f"Created: {standup['created_at']}")
    
    elif args.command == 'get':
        # Try as date first, then as ID
        try:
            # Check if it's a date format
            if '-' in args.identifier and len(args.identifier) == 10:
                standup = db.get_standup_by_date(args.identifier)
            else:
                # Assume it's an ID
                standups = db.get_all_standups(1000)  # Get all to find by ID
                standup = next((s for s in standups if s['id'] == int(args.identifier)), None)
            
            if standup:
                print(f"📄 Standup Details:")
                print(f"ID: {standup['id']}")
                print(f"Date: {standup['date']}")
                print(f"Trigger: {standup['trigger_event']}")
                print(f"Description:\n{standup['description']}")
                print(f"Slack Posted: {'✅' if standup['slack_posted'] else '❌'}")
                print(f"Created: {standup['created_at']}")
                if standup['updated_at'] != standup['created_at']:
                    print(f"Updated: {standup['updated_at']}")
            else:
                print(f"❌ No standup found for: {args.identifier}")
                
        except ValueError:
            print(f"❌ Invalid identifier: {args.identifier}")
    
    elif args.command == 'delete':
        success = db.delete_standup(args.id)
        if success:
            print(f"✅ Deleted standup ID: {args.id}")
        else:
            print(f"❌ Failed to delete standup ID: {args.id}")
    
    elif args.command == 'add':
        try:
            standup_id = db.save_standup(
                date=args.date,
                description=args.description,
                trigger_event=args.trigger
            )
            print(f"✅ Added standup with ID: {standup_id}")
        except Exception as e:
            print(f"❌ Failed to add standup: {e}")


if __name__ == "__main__":
    main()