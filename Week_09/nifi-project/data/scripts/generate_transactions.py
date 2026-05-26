#!/usr/bin/env python3
"""
Smart Traffic Data Simulator
Generates semi-structured JSON files simulating real-time traffic sensor readings
with intentional data quality issues for Apache NiFi ingestion pipeline.

Scenario: City-wide smart traffic control center receiving live data
from intersections every few seconds.
"""

import json
import os
import time
import random
import uuid
from datetime import datetime, timedelta

# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------
OUTPUT_DIR = "/data/incoming"          # NiFi watches this directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ------------------------------------------------------------
# LOOKUP DATA - Realistic city traffic values
# ------------------------------------------------------------
INTERSECTION_IDS = [f"INT-{i:04d}" for i in range(1, 31)]  # 30 intersections: INT-0001 to INT-0030

VEHICLE_TYPES = ["car", "car", "car", "truck", "bus", "motorcycle", "emergency"]
# car appears 3 times = more common

DISTRICTS = [
    "Downtown", "Industrial Zone", "Northern Suburbs", "Southern Suburbs",
    "Airport Road", "University District", "Commercial District"
]

CONGESTION_LEVELS = ["smooth", "moderate", "heavy", "gridlock", None, ""]

SIGNAL_STATUSES = ["green", "yellow", "red", "flashing", None]

# ------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------

def generate_event_id():
    """Generate a unique event ID. Occasionally returns duplicate to simulate sensor glitch."""
    if random.random() < 0.12:  # 12% chance of duplicate
        return "DUPLICATE_EVENT"
    return str(uuid.uuid4())


def generate_accident_flag(avg_speed, congestion):
    """
    Simulate accident detection logic.
    Sometimes contradicts other fields to create messy data.
    """
    # Realistic logic: low speed + gridlock = likely accident
    if avg_speed is not None and avg_speed < 5 and congestion == "gridlock":
        return random.choice([True, True, True, False])  # 75% true, but sometimes missed
    
    # Messy: sometimes returns accident flag even with high speed (sensor error)
    if random.random() < 0.05:  # 5% random noise
        return random.choice([True, False, None])
    
    return random.choice([False, None])  # normally no accident


def generate_congestion_level(vehicle_count, avg_speed):
    """
    Normally derived from vehicle_count and speed, but deliberately
    sometimes wrong to simulate sensor calibration errors.
    """
    # Check if values are valid numbers before comparison
    speed_valid = isinstance(avg_speed, (int, float))
    count_valid = isinstance(vehicle_count, int)
    
    # If either value is invalid, return random congestion
    if not speed_valid or not count_valid:
        return random.choice(["smooth", "moderate", "heavy", "gridlock", None])
    
    # Correct logic based on valid values
    if avg_speed > 50 and vehicle_count < 10:
        correct = "smooth"
    elif avg_speed > 30:
        correct = "moderate"
    elif avg_speed > 10:
        correct = "heavy"
    else:
        correct = "gridlock"
    
    # 20% chance: return something wrong (sensor calibration error)
    if random.random() < 0.20:
        return random.choice(["smooth", "moderate", "heavy", "gridlock", None])
    
    return correct


def generate_temperature():
    """Generate road surface temperature in Celsius. Sometimes invalid."""
    return random.choice([
        round(random.uniform(20.0, 70.0), 1),  # normal
        None,                                    # missing sensor
        -99.9,                                   # sensor error code
        round(random.uniform(80.0, 100.0), 1)   # extreme (desert midday)
    ])


def generate_visibility():
    """Generate visibility in meters. Sometimes invalid."""
    return random.choice([
        round(random.uniform(50.0, 5000.0), 1),  # normal range
        None,                                      # sensor offline
        0.0,                                       # impossible value
        -1.0                                       # error code
    ])


def generate_signal_status():
    """Generate traffic light status. Sometimes mismatches with other data."""
    return random.choice(SIGNAL_STATUSES)


def generate_vehicle_count():
    """Vehicle count in last 5 seconds. Sometimes missing or negative."""
    return random.choice([
        random.randint(0, 30),    # normal
        None,                      # sensor offline
        -1,                        # error code
        "unknown"                  # data format error
    ])


def generate_avg_speed(vehicle_count):
    """Average speed in km/h. Sometimes illogical."""
    # Normally: more vehicles = slower speed
    if isinstance(vehicle_count, int) and vehicle_count > 20:
        base_speed = random.uniform(0, 30)
    elif isinstance(vehicle_count, int) and vehicle_count > 10:
        base_speed = random.uniform(20, 50)
    else:
        base_speed = random.uniform(40, 80)
    
    return random.choice([
        round(base_speed, 1),     # normal
        None,                      # missing
        -10.0,                     # sensor fault
        round(random.uniform(100, 200), 1)  # unrealistic speed
    ])


# ------------------------------------------------------------
# RECORD GENERATOR
# ------------------------------------------------------------

def generate_record():
    """
    Generate a single traffic event record.
    Contains intentional data quality issues:
    - Missing values (None, empty strings)
    - Duplicate event IDs
    - Logical contradictions between fields
    - Invalid sensor readings
    - Inconsistent district names
    """
    
    vehicle_count = generate_vehicle_count()
    avg_speed = generate_avg_speed(vehicle_count)
    congestion = generate_congestion_level(vehicle_count, avg_speed)
    accident = generate_accident_flag(avg_speed, congestion)
    temp = generate_temperature()
    visibility = generate_visibility()
    signal = generate_signal_status()
    
    # District: sometimes empty or misspelled
    district = random.choice(DISTRICTS + [None, "", "downtown", "DOWNTOWN"])
    
    record = {
        "event_id": generate_event_id(),
        "intersection_id": random.choice(INTERSECTION_IDS),
        "vehicle_type": random.choice(VEHICLE_TYPES),
        "vehicle_count": vehicle_count,
        "avg_speed_kmh": avg_speed,
        "congestion_level": congestion,
        "district": district,
        "lane_id": random.choice([1, 2, 3, 4, None]),
        "temperature_c": temp,
        "visibility_m": visibility,
        "accident_flag": accident,
        "signal_status": signal,
        "event_timestamp": (datetime.now() - timedelta(seconds=random.randint(0, 5))).isoformat()
    }
    
    return record


# ------------------------------------------------------------
# FILE WRITER
# ------------------------------------------------------------

def write_batch():
    """
    Write a batch of records to a new JSON file.
    Naming pattern: Transaction_YYYYMMDD_HHMMSS_microseconds.json
    """
    # 3 to 8 records per file
    batch_size = random.randint(3, 8)
    batch = [generate_record() for _ in range(batch_size)]
    
    # Generate filename with datetime
    filename = f"Transaction_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    # Write one JSON object per line (NDJSON - Newline Delimited JSON)
    with open(filepath, 'w') as f:
        for record in batch:
            f.write(json.dumps(record) + '\n')
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Created: {filename} ({batch_size} records)")


# ------------------------------------------------------------
# MAIN LOOP
# ------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 55)
    print("  Smart Traffic Data Simulator")
    print("  Simulating city-wide intersection sensors")
    print(f"  Output: {OUTPUT_DIR}")
    print("  Press Ctrl+C to stop")
    print("=" * 55)
    
    try:
        while True:
            write_batch()
            # Wait 2-5 seconds between files
            time.sleep(random.uniform(2, 5))
    except KeyboardInterrupt:
        print("\n[STOPPED] Simulator terminated by user.")