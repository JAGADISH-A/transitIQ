import os
import sys

# Add the backend directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from app.services.transit_service import parse_gtfs_time_to_display

def test_time_architecture():
    cases = [
        {"name": "Case 1", "departure": "28:30:00", "expected_time": "04:30 AM", "expected_offset": 1},
        {"name": "Case 2", "departure": "23:10:00", "expected_time": "11:10 PM", "expected_offset": 0},
        {"name": "Case 3", "departure": "01:30:00", "expected_time": "01:30 AM", "expected_offset": 0},
        {"name": "Case 4 - Transfer Leg 1", "departure": "23:40:00", "expected_time": "11:40 PM", "expected_offset": 0},
        {"name": "Case 4 - Transfer Leg 2", "departure": "25:15:00", "expected_time": "01:15 AM", "expected_offset": 1},
        {"name": "Case 5 - Exact Midnight", "departure": "24:00:00", "expected_time": "12:00 AM", "expected_offset": 1},
        {"name": "Case 6 - Exact Noon", "departure": "12:00:00", "expected_time": "12:00 PM", "expected_offset": 0},
        {"name": "Case 7 - Single Digit Hour", "departure": "08:05:00", "expected_time": "08:05 AM", "expected_offset": 0},
        {"name": "Case 8 - Far Future", "departure": "72:00:00", "expected_time": "12:00 AM", "expected_offset": 3},
    ]

    print("Running Day-Aware Time Architecture Tests...")
    print("-" * 50)
    all_passed = True
    
    for case in cases:
        result = parse_gtfs_time_to_display(case["departure"])
        if result is None:
            print(f"❌ {case['name']} FAILED: Returned None")
            all_passed = False
            continue
            
        time_match = result.display_time == case["expected_time"]
        offset_match = result.day_offset == case["expected_offset"]
        
        if time_match and offset_match:
            print(f"PASS: {case['name']}")
            print(f"   Input: {case['departure']} -> Result: {result.display_time} (+{result.day_offset} Day)")
        else:
            print(f"FAIL: {case['name']}")
            print(f"   Input: {case['departure']}")
            print(f"   Expected: {case['expected_time']} (+{case['expected_offset']} Day)")
            print(f"   Got:      {result.display_time} (+{result.day_offset} Day)")
            all_passed = False
            
    print("-" * 50)
    if all_passed:
        print("All 4 Edge Cases (and more) passed successfully!")
    else:
        print("Some tests failed. Please review the output.")

if __name__ == "__main__":
    test_time_architecture()
