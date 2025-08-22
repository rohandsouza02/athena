#!/usr/bin/env python3
"""
Database module for standup automation system.
Handles SQLite database operations for storing standup records.
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class StandupDatabase:
    def __init__(self, db_path: str = "standup.db"):
        """Initialize database connection and create tables if needed."""
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database and create tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create standups table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS standups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        description TEXT NOT NULL,
                        trigger_event TEXT,
                        transcript_path TEXT,
                        teams_context TEXT,
                        previous_summaries TEXT,
                        raw_transcript TEXT,
                        slack_posted BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create index on date for faster queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_standups_date 
                    ON standups(date)
                """)
                
                conn.commit()
                logger.info(f"Database initialized at {self.db_path}")
                
        except sqlite3.Error as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def save_standup(self, date: str, description: str, 
                    trigger_event: str = None, transcript_path: str = None,
                    teams_context: str = None, previous_summaries: str = None,
                    raw_transcript: str = None, slack_posted: bool = False) -> int:
        """Save a standup record to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO standups (
                        date, description, trigger_event, transcript_path,
                        teams_context, previous_summaries, raw_transcript,
                        slack_posted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date, description, trigger_event, transcript_path,
                    teams_context, previous_summaries, raw_transcript,
                    slack_posted
                ))
                
                standup_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"Saved standup record with ID: {standup_id}")
                return standup_id
                
        except sqlite3.Error as e:
            logger.error(f"Error saving standup: {e}")
            raise
    
    def get_standup_by_date(self, date: str) -> Optional[Dict]:
        """Get standup record for a specific date."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM standups 
                    WHERE date = ? 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """, (date,))
                
                row = cursor.fetchone()
                return dict(row) if row else None
                
        except sqlite3.Error as e:
            logger.error(f"Error getting standup by date: {e}")
            return None
    
    def get_recent_standups(self, days: int = 5) -> List[Dict]:
        """Get standup records from the last N days."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM standups 
                    WHERE date >= date('now', '-{} days')
                    ORDER BY date DESC
                """.format(days))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except sqlite3.Error as e:
            logger.error(f"Error getting recent standups: {e}")
            return []
    
    def get_all_standups(self, limit: int = 100) -> List[Dict]:
        """Get all standup records with optional limit."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM standups 
                    ORDER BY date DESC 
                    LIMIT ?
                """, (limit,))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except sqlite3.Error as e:
            logger.error(f"Error getting all standups: {e}")
            return []
    
    def update_standup(self, standup_id: int, **kwargs) -> bool:
        """Update a standup record."""
        if not kwargs:
            return False
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build dynamic UPDATE query
                set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
                values = list(kwargs.values())
                values.append(standup_id)
                
                cursor.execute(f"""
                    UPDATE standups 
                    SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, values)
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Updated standup record ID: {standup_id}")
                    return True
                else:
                    logger.warning(f"No standup record found with ID: {standup_id}")
                    return False
                
        except sqlite3.Error as e:
            logger.error(f"Error updating standup: {e}")
            return False
    
    def delete_standup(self, standup_id: int) -> bool:
        """Delete a standup record."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("DELETE FROM standups WHERE id = ?", (standup_id,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Deleted standup record ID: {standup_id}")
                    return True
                else:
                    logger.warning(f"No standup record found with ID: {standup_id}")
                    return False
                
        except sqlite3.Error as e:
            logger.error(f"Error deleting standup: {e}")
            return False
    
    def get_standup_stats(self) -> Dict:
        """Get basic statistics about standups."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total count
                cursor.execute("SELECT COUNT(*) FROM standups")
                total_count = cursor.fetchone()[0]
                
                # Count by trigger event
                cursor.execute("""
                    SELECT trigger_event, COUNT(*) 
                    FROM standups 
                    GROUP BY trigger_event
                """)
                trigger_counts = dict(cursor.fetchall())
                
                # Recent activity (last 30 days)
                cursor.execute("""
                    SELECT COUNT(*) FROM standups 
                    WHERE date >= date('now', '-30 days')
                """)
                recent_count = cursor.fetchone()[0]
                
                # Slack posted count
                cursor.execute("""
                    SELECT COUNT(*) FROM standups 
                    WHERE slack_posted = TRUE
                """)
                slack_posted_count = cursor.fetchone()[0]
                
                return {
                    "total_standups": total_count,
                    "recent_30_days": recent_count,
                    "slack_posted": slack_posted_count,
                    "trigger_events": trigger_counts
                }
                
        except sqlite3.Error as e:
            logger.error(f"Error getting standup stats: {e}")
            return {}
    
    def close(self):
        """Close database connection (not needed with context managers)."""
        pass