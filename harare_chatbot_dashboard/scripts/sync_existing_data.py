"""
Script to sync existing data from external systems
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dashboard.utils.data_sync import data_sync
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Run data sync"""
    print("=" * 60)
    print("HARARE MUNICIPAL CHATBOT - DATA SYNC")
    print("=" * 60)
    
    print("\nStarting data synchronization...")
    
    # Run sync
    results = data_sync.sync_all()
    
    print("\n" + "=" * 60)
    print("SYNC RESULTS")
    print("=" * 60)
    
    print(f"\nStatus: {results.get('status', 'unknown')}")
    print(f"Timestamp: {results.get('timestamp')}")
    
    if results.get("conversations"):
        conv_results = results["conversations"]
        print(f"\nConversations:")
        print(f"  - Synced: {conv_results.get('synced', 0)}")
        if "error" in conv_results:
            print(f"  - Error: {conv_results['error']}")
    
    if results.get("documents"):
        doc_results = results["documents"]
        print(f"\nDocuments:")
        print(f"  - Synced: {doc_results.get('synced', 0)}")
        if "error" in doc_results:
            print(f"  - Error: {doc_results['error']}")
    
    # Check pending ingestion
    print("\nChecking for pending document ingestion...")
    pending = data_sync.check_pending_ingestion()
    print(f"Documents needing ingestion: {pending.get('pending_count', 0)}")
    
    print("\n" + "=" * 60)
    print("✓ Sync complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()