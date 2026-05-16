#!/usr/bin/env python3
"""
Validation script for Harare Chatbot RASA upgrade
Checks all configurations before training
"""

import os
import sys
import yaml
from pathlib import Path

def check_file_exists(filepath, description):
    """Check if a file exists."""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description} NOT FOUND: {filepath}")
        return False

def validate_yaml_file(filepath):
    """Validate YAML syntax."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            yaml.safe_load(f)
        return True
    except Exception as e:
        print(f"❌ YAML Error in {filepath}: {e}")
        return False

def main():
    print("=" * 60)
    print("HARARE CHATBOT - RASA UPGRADE VALIDATION")
    print("=" * 60)
    print()
    
    all_valid = True
    
    # Check required files
    print("1. Checking Required Files...")
    print("-" * 60)
    
    required_files = {
        "domain.yml": "Domain Configuration",
        "config.yml": "Pipeline Configuration",
        "endpoints.yml": "Endpoints Configuration",
        "credentials.yml": "Credentials Configuration",
        "data/nlu.yml": "NLU Training Data",
        "data/rules.yml": "Rules",
        "data/stories.yml": "Stories",
        "actions/actions.py": "Main Actions",
        "actions/__init__.py": "Actions Package Init",
        "actions/forms/report_issue_form.py": "Report Form",
        "actions/forms/__init__.py": "Forms Package Init",
        "actions/ticket_system.py": "Ticket System Actions"
    }
    
    for filepath, description in required_files.items():
        if not check_file_exists(filepath, description):
            all_valid = False
    
    print()
    
    # Validate YAML files
    print("2. Validating YAML Syntax...")
    print("-" * 60)
    
    yaml_files = [
        "domain.yml",
        "config.yml",
        "endpoints.yml",
        "credentials.yml",
        "data/nlu.yml",
        "data/rules.yml",
        "data/stories.yml"
    ]
    
    for filepath in yaml_files:
        if os.path.exists(filepath):
            if validate_yaml_file(filepath):
                print(f"✅ Valid YAML: {filepath}")
            else:
                all_valid = False
        else:
            print(f"⚠️  Skipped (not found): {filepath}")
    
    print()
    
    # Check domain structure
    print("3. Checking Domain Structure...")
    print("-" * 60)
    
    try:
        with open("domain.yml", 'r', encoding='utf-8') as f:
            domain = yaml.safe_load(f)
        
        # Check required keys
        required_keys = ["intents", "slots", "responses", "actions", "forms"]
        for key in required_keys:
            if key in domain:
                count = len(domain[key]) if isinstance(domain[key], (list, dict)) else 1
                print(f"✅ {key}: {count} items")
            else:
                print(f"❌ Missing: {key}")
                all_valid = False
        
        # Check specific items
        if "forms" in domain and "report_issue_form" in domain["forms"]:
            print("✅ report_issue_form defined")
        else:
            print("❌ report_issue_form NOT defined")
            all_valid = False
        
        if "actions" in domain:
            expected_actions = [
                "validate_report_issue_form",
                "action_submit_report",
                "action_check_ticket_status",
                "action_reset_form",
                "action_save_form_progress",
                "action_recover_session"
            ]
            for action in expected_actions:
                if action in domain["actions"]:
                    print(f"✅ Action defined: {action}")
                else:
                    print(f"⚠️  Action not in domain: {action}")
        
    except Exception as e:
        print(f"❌ Error checking domain: {e}")
        all_valid = False
    
    print()
    
    # Check NLU data
    print("4. Checking NLU Training Data...")
    print("-" * 60)
    
    try:
        with open("data/nlu.yml", 'r', encoding='utf-8') as f:
            nlu = yaml.safe_load(f)
        
        if "nlu" in nlu:
            intents = {}
            for item in nlu["nlu"]:
                if "intent" in item:
                    intent_name = item["intent"]
                    examples = item.get("examples", "")
                    example_count = len([line for line in examples.split('\n') if line.strip() and line.strip().startswith('-')])
                    intents[intent_name] = example_count
            
            print(f"Total intents: {len(intents)}")
            for intent_name, count in intents.items():
                if count >= 5:
                    print(f"✅ {intent_name}: {count} examples")
                else:
                    print(f"⚠️  {intent_name}: {count} examples (recommend ≥5)")
        else:
            print("❌ No NLU data found")
            all_valid = False
    
    except Exception as e:
        print(f"❌ Error checking NLU: {e}")
        all_valid = False
    
    print()
    
    # Check stories
    print("5. Checking Stories...")
    print("-" * 60)
    
    try:
        with open("data/stories.yml", 'r', encoding='utf-8') as f:
            stories = yaml.safe_load(f)
        
        if "stories" in stories:
            print(f"✅ Total stories: {len(stories['stories'])}")
            for story in stories["stories"]:
                story_name = story.get("story", "unnamed")
                steps = story.get("steps", [])
                print(f"  • {story_name}: {len(steps)} steps")
        else:
            print("❌ No stories found")
            all_valid = False
    
    except Exception as e:
        print(f"❌ Error checking stories: {e}")
        all_valid = False
    
    print()
    
    # Check rules
    print("6. Checking Rules...")
    print("-" * 60)
    
    try:
        with open("data/rules.yml", 'r', encoding='utf-8') as f:
            rules = yaml.safe_load(f)
        
        if "rules" in rules:
            print(f"✅ Total rules: {len(rules['rules'])}")
            for rule in rules["rules"]:
                rule_name = rule.get("rule", "unnamed")
                print(f"  • {rule_name}")
        else:
            print("❌ No rules found")
            all_valid = False
    
    except Exception as e:
        print(f"❌ Error checking rules: {e}")
        all_valid = False
    
    print()
    print("=" * 60)
    
    if all_valid:
        print("✅ ALL VALIDATIONS PASSED!")
        print()
        print("Next steps:")
        print("1. Run: rasa data validate")
        print("2. Run: rasa train")
        print("3. Run: rasa run actions (in separate terminal)")
        print("4. Run: rasa shell")
        return 0
    else:
        print("❌ VALIDATION FAILED - Please fix errors above")
        return 1

if __name__ == "__main__":
    sys.exit(main())