#!/usr/bin/env python3
"""
Transcript Processor - Convert Vexa API segments into a single readable transcript
"""

import json
import argparse
from datetime import datetime
from typing import Dict, List, Any
import os


def process_transcript(json_data: Dict[str, Any]) -> str:
    """
    Convert segments from Vexa API output into a single readable transcript
    
    Args:
        json_data: The JSON data containing segments
    
    Returns:
        Formatted transcript as a string
    """
    
    # Extract meeting metadata
    start_time = json_data.get('start_time', 'Unknown')
    
    # Initialize transcript
    transcript_lines = []
    transcript_lines.append(f"Meeting Date/Time: {start_time}")
    transcript_lines.append("")
    
    # Process segments
    segments = json_data.get('segments', [])
    
    # Sort segments by start time to ensure chronological order
    sorted_segments = sorted(segments, key=lambda x: x.get('start', 0))
    
    # Collect all text parts
    all_text_parts = []
    
    for segment in sorted_segments:
        text = segment.get('text', '').strip()
        
        # Skip empty text segments
        if not text:
            continue
            
        all_text_parts.append(text)
    
    # Combine all text and clean it
    if all_text_parts:
        combined_text = ' '.join(all_text_parts)
        cleaned_text = clean_text(combined_text)
        transcript_lines.append(cleaned_text)
    
    return '\n'.join(transcript_lines)


def clean_text(text: str) -> str:
    """
    Clean up transcript text by removing duplicates and formatting
    
    Args:
        text: Raw combined text
        
    Returns:
        Cleaned text
    """
    # Split into sentences and remove near-duplicates
    sentences = text.split('.')
    cleaned_sentences = []
    
    for sentence in sentences:
        sentence = sentence.strip()
        if sentence and sentence not in cleaned_sentences:
            # Check for similar sentences (simple approach)
            is_duplicate = False
            for existing in cleaned_sentences:
                if len(sentence) > 10 and sentence in existing:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                cleaned_sentences.append(sentence)
    
    return '. '.join(cleaned_sentences).strip()


def format_timestamp(seconds: float) -> str:
    """
    Format timestamp from seconds to MM:SS format
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted timestamp string
    """
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def main():
    parser = argparse.ArgumentParser(description='Convert Vexa API segments to readable transcript')
    parser.add_argument('input_file', help='Input JSON file with segments')
    parser.add_argument('-o', '--output', help='Output file (default: transcript.txt)')
    parser.add_argument('--format', choices=['txt', 'md'], default='txt', help='Output format')
    
    args = parser.parse_args()
    
    # Read input file
    if not os.path.exists(args.input_file):
        print(f"❌ Input file not found: {args.input_file}")
        return
    
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading JSON file: {e}")
        return
    
    # Process transcript
    transcript = process_transcript(json_data)
    
    # Determine output file
    if args.output:
        output_file = args.output
    else:
        base_name = os.path.splitext(args.input_file)[0]
        extension = 'md' if args.format == 'md' else 'txt'
        output_file = f"{base_name}_transcript.{extension}"
    
    # Convert to markdown if requested
    if args.format == 'md':
        transcript = convert_to_markdown(transcript)
    
    # Write output
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(transcript)
        print(f"✅ Transcript saved to: {output_file}")
        
        # Print preview
        print(f"\n📖 TRANSCRIPT PREVIEW:")
        print("-" * 40)
        lines = transcript.split('\n')
        for line in lines[:20]:  # Show first 20 lines
            print(line)
        if len(lines) > 20:
            print(f"... ({len(lines) - 20} more lines)")
            
    except Exception as e:
        print(f"❌ Error writing output file: {e}")


def convert_to_markdown(transcript: str) -> str:
    """
    Convert transcript to markdown format
    
    Args:
        transcript: Plain text transcript
        
    Returns:
        Markdown formatted transcript
    """
    lines = transcript.split('\n')
    md_lines = []
    
    for line in lines:
        if line.startswith('='):
            continue  # Skip separator lines
        elif 'MEETING TRANSCRIPT' in line:
            md_lines.append(f"# {line}")
        elif 'Meeting ID:' in line or 'Platform:' in line or 'Start Time:' in line:
            md_lines.append(f"**{line}**")
        elif line.startswith('[') and ']:' in line:
            # Speaker lines
            parts = line.split(']: ', 1)
            if len(parts) == 2:
                timestamp = parts[0] + ']'
                speaker_text = parts[1]
                speaker_name = speaker_text.split(':', 1)[0] if ':' in speaker_text else 'Speaker'
                text = speaker_text.split(':', 1)[1].strip() if ':' in speaker_text else speaker_text
                md_lines.append(f"**{timestamp} {speaker_name}:** {text}")
            else:
                md_lines.append(line)
        elif 'END OF TRANSCRIPT' in line:
            md_lines.append(f"## {line}")
        else:
            md_lines.append(line)
    
    return '\n'.join(md_lines)


if __name__ == '__main__':
    main()