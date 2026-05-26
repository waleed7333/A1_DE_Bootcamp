#!/usr/bin/env python3
"""
Intersection Database Simulator
Manages the intersections reference table in PostgreSQL.
Simulates slow-changing reference data: new intersections added,
existing ones updated (maintenance, signal timing changes).
"""

import psycopg2
import time
import random
from datetime import datetime, timedelta

# ------------------------------------------------------------
# DATABASE CONNECTION CONFIGURATION
# ------------------------------------------------------------
DB_CONFIG = {
    "host": "postgres",       # Docker service name
    "port": 5432,
    "database": "nifi_db",
    "user": "nifi_user",
    "password": "strongpassword"
}

# ------------------------------------------------------------
# LOOKUP DATA
# ------------------------------------------------------------
DISTRICTS = [
    "Downtown", "Industrial Zone", "Northern Suburbs", "Southern Suburbs",
    "Airport Road", "University District", "Commercial District"
]

SIGNAL_TYPES = ["smart", "fixed", "adaptive", "manual"]
STATUSES = ["active", "active", "active", "maintenance", "offline"]  # active is more common
FIRMWARE_VERSIONS = ["v2.1", "v2.2", "v3.0", "v3.1", "v1.5"]

# ------------------------------------------------------------
# DATABASE SETUP
# ------------------------------------------------------------

def setup_database():
    """
    Create the intersections table if it doesn't exist.
    Also inserts initial 20 intersections if table is empty.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Create table for intersections reference data
    cur.execute("""
        CREATE TABLE IF NOT EXISTS intersections (
            intersection_id VARCHAR(10) PRIMARY KEY,
            intersection_name VARCHAR(100),
            district VARCHAR(50),
            total_lanes INTEGER,
            has_camera BOOLEAN,
            has_sensor BOOLEAN,
            signal_type VARCHAR(20),
            signal_timing_sec INTEGER,
            last_maintenance DATE,
            status VARCHAR(20),
            firmware_version VARCHAR(10),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Check if table is empty, insert initial data if needed
    cur.execute("SELECT COUNT(*) FROM intersections;")
    count = cur.fetchone()[0]
    
    if count == 0:
        print("[INIT] Inserting initial 20 intersections...")
        insert_initial_intersections(cur)
        conn.commit()
        print("[INIT] Initial intersections inserted successfully.")
    
    cur.close()
    conn.close()


def insert_initial_intersections(cur):
    """
    Insert initial set of 20 intersections with realistic data.
    Some have intentional data quality issues.
    """
    street_pairs = [
        ("King Fahd Rd", "Olaya St"), ("Airport Rd", "Sitteen St"),
        ("Makkah Rd", "Madinah Rd"), ("Tahlia St", "Thumamah Rd"),
        ("Dabab St", "Khurais Rd"), ("Batha St", "Salam St"),
        ("Imam Saud Rd", "Abi Bakr St"), ("Uthman St", "Shafa St"),
        ("Qassim St", "Yarmouk St"), ("Rawdah St", "Nuzha St"),
        ("Prince Sultan Rd", "Andalus St"), ("Hamra St", "Jazeera St"),
        ("Sheikh Zayed Rd", "Emirates Rd"), ("Corniche Rd", "Pearl St"),
        ("University Blvd", "College Rd"), ("Industrial Rd", "Factory St"),
        ("Garden Rd", "Park Ave"), ("River Rd", "Bridge St"),
        ("Mountain Rd", "Valley St"), ("Desert Rd", "Oasis St")
    ]
    
    for i in range(20):
        int_id = f"INT-{i+1:04d}"
        name = f"{street_pairs[i][0]} & {street_pairs[i][1]}"
        district = random.choice(DISTRICTS)
        lanes = random.choice([2, 3, 4, None])  # Sometimes None (missing data)
        has_camera = random.choice([True, False])
        has_sensor = random.choice([True, False])
        sig_type = random.choice(SIGNAL_TYPES)
        timing = random.choice([30, 45, 60, 90, 120, None])  # Sometimes None
        maintenance = (datetime.now() - timedelta(days=random.randint(1, 365))).date()
        status = random.choice(STATUSES)
        firmware = random.choice(FIRMWARE_VERSIONS + [None])  # Sometimes None
        
        cur.execute("""
            INSERT INTO intersections 
            (intersection_id, intersection_name, district, total_lanes, 
             has_camera, has_sensor, signal_type, signal_timing_sec,
             last_maintenance, status, firmware_version, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
        """, (int_id, name, district, lanes, has_camera, has_sensor,
              sig_type, timing, maintenance, status, firmware))


# ------------------------------------------------------------
# SIMULATION FUNCTIONS
# ------------------------------------------------------------

def add_new_intersection():
    """
    Add a brand new intersection (simulates city expansion).
    Sometimes has messy data intentionally.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Get next ID
    cur.execute("SELECT COUNT(*) FROM intersections;")
    count = cur.fetchone()[0]
    new_id = f"INT-{count+1:04d}"
    
    # Some messy data
    district = random.choice(DISTRICTS + [None, "", "unknown"])
    signal_timing = random.choice([30, 45, 60, None, 0, -1, "N/A"])
    
    # Ensure signal_timing is valid type
    if isinstance(signal_timing, str):
        signal_timing = None
    
    cur.execute("""
        INSERT INTO intersections 
        (intersection_id, intersection_name, district, total_lanes,
         has_camera, has_sensor, signal_type, signal_timing_sec,
         last_maintenance, status, firmware_version, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
    """, (
        new_id,
        f"New Intersection {new_id}",
        district,
        random.choice([2, 3, 4]),
        random.choice([True, False]),
        random.choice([True, False]),
        random.choice(SIGNAL_TYPES),
        signal_timing,
        datetime.now().date(),
        "active",
        random.choice(FIRMWARE_VERSIONS)
    ))
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] INSERT: Added {new_id}")


def update_existing_intersection():
    """
    Update an existing intersection (simulates maintenance, firmware updates).
    Sometimes has messy data intentionally.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Get all IDs
    cur.execute("SELECT intersection_id FROM intersections;")
    ids = [row[0] for row in cur.fetchall()]
    
    if not ids:
        cur.close()
        conn.close()
        return
    
    selected_id = random.choice(ids)
    update_field = random.choice(["status", "firmware", "timing", "maintenance"])
    
    if update_field == "status":
        new_status = random.choice(STATUSES + [None])
        cur.execute("""
            UPDATE intersections SET status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE intersection_id = %s;
        """, (new_status, selected_id))
    
    elif update_field == "firmware":
        new_firmware = random.choice(FIRMWARE_VERSIONS + [None])
        cur.execute("""
            UPDATE intersections SET firmware_version = %s, updated_at = CURRENT_TIMESTAMP
            WHERE intersection_id = %s;
        """, (new_firmware, selected_id))
    
    elif update_field == "timing":
        new_timing = random.choice([30, 45, 60, 90, None, -1])
        cur.execute("""
            UPDATE intersections SET signal_timing_sec = %s, updated_at = CURRENT_TIMESTAMP
            WHERE intersection_id = %s;
        """, (new_timing, selected_id))
    
    elif update_field == "maintenance":
        new_date = datetime.now().date()
        cur.execute("""
            UPDATE intersections SET last_maintenance = %s, updated_at = CURRENT_TIMESTAMP
            WHERE intersection_id = %s;
        """, (new_date, selected_id))
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] UPDATE: Changed {update_field} on {selected_id}")


# ------------------------------------------------------------
# MAIN LOOP
# ------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 50)
    print("  Intersection Database Simulator")
    print("  Managing slow-changing reference data")
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    
    # Setup table and initial data
    setup_database()
    
    try:
        while True:
            # 30% chance: add new intersection (city expansion)
            if random.random() < 0.30:
                add_new_intersection()
            
            # 70% chance: update existing intersection (maintenance)
            else:
                update_existing_intersection()
            
            # Wait 10-15 seconds between operations
            time.sleep(random.uniform(3, 5))
    
    except KeyboardInterrupt:
        print("\n[STOPPED] Database simulator terminated by user.")