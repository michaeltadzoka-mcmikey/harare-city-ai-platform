"""
Script to automatically detect and create knowledge gaps
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dashboard.utils.knowledge_gap_detector import gap_detector
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Run knowledge gap detection"""
    print("=" * 60)
    print("KNOWLEDGE GAP AUTO-DETECTION")
    print("=" * 60)
    
    print("\nAnalyzing conversations from last 7 days...")
    
    # Detect gaps
    gaps = gap_detector.analyze_conversations(days=7)
    
    print(f"\nFound {len(gaps)} potential knowledge gaps")
    
    if gaps:
        print("\nTop 5 knowledge gaps:")
        for i, gap in enumerate(gaps[:5], 1):
            print(f"\n{i}. {gap['question']}")
            print(f"   Frequency: {gap['frequency']}")
            print(f"   Priority: {gap['priority_score']}")
            print(f"   Department: {gap['department']}")
        
        # Create knowledge gap records
        print("\nCreating knowledge gap records...")
        created = gap_detector.create_knowledge_gaps(gaps)
        print(f"✓ Created {created} new knowledge gap records")
    
    print("\n" + "=" * 60)
    print("✓ Detection complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()