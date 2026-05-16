"""
Test script for Harare Chatbot RASA implementation
Run this to verify your setup is correct
"""

import os
import sys
import yaml
import json
from pathlib import Path

def test_file_structure():
    """Verify all required files exist"""
    print("🔍 Checking file structure...")
    
    required_files = [
        "domain.yml",
        "config.yml",
        "endpoints.yml",
        "credentials.yml",
        "data/nlu.yml",
        "data/rules.yml",
        "data/stories.yml",
        "actions/actions.py",
        "actions/__init__.py"
    ]
    
    all_exist = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} - MISSING!")
            all_exist = False
    
    return all_exist

def test_yaml_syntax():
    """Verify YAML files are valid"""
    print("\n🔍 Checking YAML syntax...")
    
    yaml_files = [
        "domain.yml",
        "config.yml",
        "endpoints.yml",
        "credentials.yml",
        "data/nlu.yml",
        "data/rules.yml",
        "data/stories.yml"
    ]
    
    all_valid = True
    for file_path in yaml_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)
            print(f"  ✅ {file_path} - Valid YAML")
        except Exception as e:
            print(f"  ❌ {file_path} - ERROR: {e}")
            all_valid = False
    
    return all_valid

def test_domain_structure():
    """Verify domain.yml has all required components"""
    print("\n🔍 Checking domain.yml structure...")
    
    with open("domain.yml", 'r', encoding='utf-8') as f:
        domain = yaml.safe_load(f)
    
    checks = {
        "intents": len(domain.get("intents", [])) > 0,
        "entities": len(domain.get("entities", [])) > 0,
        "slots": len(domain.get("slots", {})) > 0,
        "responses": len(domain.get("responses", {})) > 0,
        "actions": len(domain.get("actions", [])) > 0,
        "forms": len(domain.get("forms", {})) > 0
    }
    
    all_valid = True
    for component, valid in checks.items():
        if valid:
            print(f"  ✅ {component}: Found")
        else:
            print(f"  ❌ {component}: Missing or empty")
            all_valid = False
    
    # Check specific required slots
    required_slots = [
        "report_confirm_proceed",
        "report_location",
        "report_description",
        "report_urgency"
    ]
    
    print("\n  Required slots:")
    for slot in required_slots:
        if slot in domain.get("slots", {}):
            print(f"    ✅ {slot}")
        else:
            print(f"    ❌ {slot} - MISSING!")
            all_valid = False
    
    return all_valid

def test_nlu_training_data():
    """Verify NLU training data is sufficient"""
    print("\n🔍 Checking NLU training data...")
    
    with open("data/nlu.yml", 'r', encoding='utf-8') as f:
        nlu_data = yaml.safe_load(f)
    
    intents = {}
    for item in nlu_data.get("nlu", []):
        intent = item.get("intent")
        examples = item.get("examples", "")
        count = len([line for line in examples.split('\n') if line.strip() and line.strip().startswith('-')])
        intents[intent] = count
    
    all_sufficient = True
    for intent, count in intents.items():
        if count >= 5:
            print(f"  ✅ {intent}: {count} examples")
        else:
            print(f"  ⚠️ {intent}: {count} examples (recommend 5+)")
            all_sufficient = False
    
    return all_sufficient

def test_actions_syntax():
    """Verify actions.py has no syntax errors"""
    print("\n🔍 Checking actions.py syntax...")
    
    try:
        with open("actions/actions.py", 'r', encoding='utf-8') as f:
            code = f.read()
        
        compile(code, "actions/actions.py", "exec")
        print("  ✅ actions.py - No syntax errors")
        return True
    except SyntaxError as e:
        print(f"  ❌ actions.py - SYNTAX ERROR: {e}")
        return False

def test_form_configuration():
    """Verify form is properly configured"""
    print("\n🔍 Checking form configuration...")
    
    with open("domain.yml", 'r', encoding='utf-8') as f:
        domain = yaml.safe_load(f)
    
    forms = domain.get("forms", {})
    if "report_issue_form" not in forms:
        print("  ❌ report_issue_form not found in domain.yml")
        return False
    
    form = forms["report_issue_form"]
    required_slots = form.get("required_slots", [])
    
    expected_slots = [
        "report_confirm_proceed",
        "report_location",
        "report_description",
        "report_urgency"
    ]
    
    all_present = True
    print("  Required slots in form:")
    for slot in expected_slots:
        if slot in required_slots:
            print(f"    ✅ {slot}")
        else:
            print(f"    ❌ {slot} - MISSING!")
            all_present = False
    
    return all_present

def create_test_report():
    """Create a sample test report"""
    print("\n🔍 Creating test simulation log...")
    
    os.makedirs("simulation_logs", exist_ok=True)
    
    test_report = {
        "report_id": "TEST-20260127-0001",
        "timestamp": "2026-01-27T10:00:00",
        "user_id": "test_user",
        "location": "Test Location",
        "description": "Test Description",
        "urgency": "medium",
        "simulation_note": "TEST REPORT",
        "status": "test"
    }
    
    log_file = "simulation_logs/test_report.jsonl"
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(json.dumps(test_report, ensure_ascii=False) + '\n')
    
    print(f"  ✅ Created: {log_file}")
    return True

def main():
    """Run all tests"""
    print("=" * 60)
    print("🚀 HARARE CHATBOT RASA - SETUP VALIDATION")
    print("=" * 60)
    
    tests = [
        ("File Structure", test_file_structure),
        ("YAML Syntax", test_yaml_syntax),
        ("Domain Structure", test_domain_structure),
        ("NLU Training Data", test_nlu_training_data),
        ("Actions Syntax", test_actions_syntax),
        ("Form Configuration", test_form_configuration),
        ("Test Log Creation", create_test_report)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} - EXCEPTION: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("📊 VALIDATION SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✅ All validation checks passed!")
        print("\n📝 Next steps:")
        print("   1. Run: rasa train")
        print("   2. Run: rasa run actions (in separate terminal)")
        print("   3. Run: rasa run --enable-api")
        print("   4. Test: rasa shell")
        return 0
    else:
        print("\n❌ Some validation checks failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())