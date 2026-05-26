"""
Smart Grid Data Generator
==========================
This script generates fake electrical grid data to simulate a real-time stream.
The data contains errors on purpose (missing values, duplicates, etc.)
so we can test our data pipeline later.
"""

import csv
import os
import random
import time
from datetime import datetime, timedelta
#import uuid

# Try to load yaml library, if not found use a simple dictionary instead
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    print("Note: pyyaml not installed. Using default settings.")
    print("To install: pip install pyyaml")


# ============================================================================
# STEP 1: Load Configuration
# ============================================================================

def load_config(filepath="config.yaml"):
    """
    Load configuration and force output directory relative to the script location.
    """
    # Get the absolute path of the directory containing this script (data_ingestion/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Force absolute paths based on the script location
    absolute_config_path = os.path.join(script_dir, filepath)
    absolute_output_path = os.path.join(script_dir, "output") # project/data_ingestion/output
    
    # Default settings using the script's local directory
    default = {
        "output_folder": absolute_output_path, 
        "file_rotation_seconds": 30,
        "readings_per_second": 20,
        "duration_minutes": 5,
        "transformers": [
            {"id": "TRF-0001", "location": "Riyadh-North"},
            {"id": "TRF-0002", "location": "Riyadh-East"},
            {"id": "TRF-0003", "location": "Jeddah-Main"},
            {"id": "TRF-0004", "location": "Jeddah-Industrial"},
            {"id": "TRF-0005", "location": "Dammam-Central"},
            {"id": "TRF-0006", "location": "Dammam-Port"},
            {"id": "TRF-0007", "location": "Mecca-Haram"},
            {"id": "TRF-0008", "location": "Medina-Central"},
            {"id": "TRF-0009", "location": "Abha-City"},
            {"id": "TRF-0010", "location": "Tabuk-Center"},
        ],
        "normal_ranges": {
            "voltage_min": 220, "voltage_max": 240,
            "current_min": 100, "current_max": 500,
            "frequency_min": 59.8, "frequency_max": 60.2,
            "temperature_min": 30, "temperature_max": 65,
        },
        "error_rates": {
            "missing_value": 0.04,
            "duplicate_row": 0.02,
            "corrupted_row": 0.01,
            "invalid_value": 0.04,
            "frequency_drift": 0.02,
            "overload": 0.01,
            "wrong_timestamp": 0.03,
        }
    }
    
    if not HAS_YAML:
        return default
    
    try:
        # Open the config file from the correct directory
        with open(absolute_config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
            # If config specifies a relative folder like "./output", lock it to the script directory
            if config.get("output_folder", "").startswith("."):
                config["output_folder"] = os.path.abspath(os.path.join(script_dir, config["output_folder"]))
            else:
                # If no output folder is provided, use the absolute fallback
                config["output_folder"] = absolute_output_path
                
            return config
    except FileNotFoundError:
        print(f"Config file '{absolute_config_path}' not found. Using default settings.")
        return default


# ============================================================================
# STEP 2: Helper Functions (small, simple, one job each)
# ============================================================================

def random_timestamp():
    """
    Generate a timestamp. Sometimes use a weird format on purpose.
    This simulates inconsistent data from different sensor types.
    """
    now = datetime.now()
    
    # Different date formats (to create messy data)
    formats = [
        "%Y-%m-%d %H:%M:%S",       # 2026-05-15 10:30:00
        "%m/%d/%Y %H:%M:%S",       # 05/15/2026 10:30:00
        "%d-%m-%Y %H:%M",          # 15-05-2026 10:30
        "%Y/%m/%d %H:%M:%S",       # 2026/05/15 10:30:00
        "%Y%m%dT%H%M%S",          # 20260515T103000
    ]
    
    chosen_format = random.choice(formats)
    return now.strftime(chosen_format)


def generate_normal_reading(transformer):
    """
    Create one normal (correct) reading for a transformer.
    All values are within acceptable ranges.
    """
    # Generate random values within normal ranges
    voltage = round(random.uniform(220, 240), 2)
    current = round(random.uniform(100, 500), 2)
    power_mw = round((voltage * current) / 1000, 2)
    frequency = round(random.uniform(59.8, 60.2), 2)
    temperature = round(random.uniform(30, 65), 1)
    
    return {
        "transformer_id": transformer["id"],
        "location": transformer["location"],
        "voltage": voltage,
        "current": current,
        "frequency": frequency,
        "power_mw": power_mw,
        "temperature": temperature,
        "status": "NORMAL",
        "phase": random.choice(["A", "B", "C"]),
        "timestamp": random_timestamp()
    }


# ============================================================================
# STEP 3: Functions to Add Errors (each function = one type of error)
# ============================================================================

def add_missing_value(reading):
    """Remove one random field to simulate missing data."""
    # Choose a random numeric field and empty it
    fields = ["voltage", "current", "frequency", "power_mw", "temperature"]
    field_to_empty = random.choice(fields)
    reading[field_to_empty] = ""


def add_invalid_value(reading):
    """Put a wrong value that makes no physical sense."""
    error_type = random.choice(["negative", "zero_power", "extreme_temp"])
    
    if error_type == "negative":
        reading["voltage"] = -230       # Negative voltage is impossible
    elif error_type == "zero_power":
        reading["current"] = 0.0        # Power outage
        reading["power_mw"] = 0.0
        reading["status"] = "OUTAGE"
    elif error_type == "extreme_temp":
        reading["temperature"] = 250.0  # Way too hot!
        reading["status"] = "OVERHEAT"


def add_frequency_drift(reading):
    """Frequency is too high or too low (grid instability)."""
    if random.choice([True, False]):
        reading["frequency"] = round(random.uniform(62, 70), 2)  # Too high
    else:
        reading["frequency"] = round(random.uniform(45, 55), 2)  # Too low
    reading["status"] = "FREQ_DRIFT"


def add_overload(reading):
    """Too much current flowing through the transformer."""
    reading["current"] = round(random.uniform(800, 1200), 2)
    reading["power_mw"] = round(random.uniform(200, 300), 2)
    reading["temperature"] = round(random.uniform(90, 130), 1)
    reading["status"] = "OVERLOAD"


def make_corrupted_row():
    """Create a completely broken row that cannot be parsed."""
    garbage_options = [
        "CORRUPTED_DATA_###!!!@@@@",
        "",
        ";;;;;",
        "SENSOR_ERROR_0xFFA2",
    ]
    return random.choice(garbage_options)


# ============================================================================
# STEP 4: Main Function that Creates One Reading (Maybe with Error)
# ============================================================================

def create_one_reading(transformer, error_rates):
    """
    Create one reading. Maybe add an error to it based on probability.
    Returns: (reading_dict, error_name_or_None)
    """
    # Step 1: Start with a normal reading
    reading = generate_normal_reading(transformer)
    error_type = None
    
    # Step 2: Roll the dice - should we add an error?
    dice = random.random()  # Number between 0 and 1
    
    # Step 3: Check each error type in order
    if dice < error_rates["missing_value"]:
        add_missing_value(reading)
        error_type = "MISSING_VALUE"
    
    elif dice < error_rates["missing_value"] + error_rates["invalid_value"]:
        add_invalid_value(reading)
        error_type = "INVALID_VALUE"
    
    elif dice < error_rates["missing_value"] + error_rates["invalid_value"] + error_rates["frequency_drift"]:
        add_frequency_drift(reading)
        error_type = "FREQ_DRIFT"
    
    elif dice < (error_rates["missing_value"] + error_rates["invalid_value"] + 
                 error_rates["frequency_drift"] + error_rates["overload"]):
        add_overload(reading)
        error_type = "OVERLOAD"
    
    return reading, error_type


# ============================================================================
# STEP 5: Write Readings to a CSV File
# ============================================================================

def write_to_csv(rows, folder):
    """
    Write a list of readings to a CSV file.
    Returns the filename.
    """
    # Create a unique filename with timestamp
#    unique_id = uuid.uuid4().hex[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#    filename = f"grid_{unique_id}_{timestamp}.csv"
    filename = f"grid_{timestamp}.csv"
    filepath = os.path.join(folder, filename)
    
    # Define the column order
    columns = [
        "transformer_id", "location", "voltage", "current",
        "frequency", "power_mw", "temperature", "status",
        "phase", "timestamp"
    ]
    
    # Make sure the output folder exists
    os.makedirs(folder, exist_ok=True)
    
    # Write the CSV file
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        
        for row in rows:
            if isinstance(row, dict):
                writer.writerow(row)
            else:
                # This is a corrupted row, write it as raw text
                f.write(str(row) + '\n')
    
    return filename


# ============================================================================
# STEP 6: Print Pretty Statistics
# ============================================================================

def print_statistics(total_records, total_errors, total_files, start_time):
    """Print current progress to the console."""
    elapsed = (datetime.now() - start_time).seconds
    rate = total_records / elapsed if elapsed > 0 else 0
    error_pct = (total_errors / total_records * 100) if total_records > 0 else 0
    
    # Clear the current line and print stats
    print(f"\rRecords: {total_records:,} | "
          f"Errors: {total_errors:,} ({error_pct:.1f}%) | "
          f"Files: {total_files} | "
          f"Speed: {rate:.0f} rec/s | "
          f"Time: {elapsed}s", end="")


# ============================================================================
# STEP 7: Main Loop - The Heart of the Generator
# ============================================================================

def run_generator(config):
    """
    Main function. Runs the generator for the specified duration.
    """
    # Extract settings from config
    folder = config["output_folder"]
    rotation = config["file_rotation_seconds"]
    rate = config["readings_per_second"]
    duration = config["duration_minutes"]
    transformers = config["transformers"]
    error_rates = config["error_rates"]
    
    # Statistics counters
    total_records = 0
    total_errors = 0
    total_files = 0
    
    # Timing variables
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=duration)
    last_file_time = time.time()
    
    # Batch of readings to write
    batch = []
    
    # Print header
    print("=" * 55)
    print("  SMART GRID DATA GENERATOR")
    print("=" * 55)
    print(f"  Transformers : {len(transformers)}")
    print(f"  Rate         : {rate} readings/second")
    print(f"  Duration     : {duration} minutes")
    print(f"  Output       : {folder}")
    print("-" * 55)
    
    # Main generation loop
    while datetime.now() < end_time:
        
        # Generate one reading per transformer
        for transformer in transformers:
            
            # 1) Create a normal reading (maybe with error)
            reading, error = create_one_reading(transformer, error_rates)
            batch.append(reading)
            total_records += 1
            if error:
                total_errors += 1
            
            # 2) Maybe add a corrupted row
            if random.random() < error_rates["corrupted_row"]:
                batch.append(make_corrupted_row())
                total_records += 1
                total_errors += 1
            
            # 3) Maybe duplicate the last reading
            if random.random() < error_rates["duplicate_row"] and len(batch) > 0:
                batch.append(reading.copy())
                total_records += 1
                total_errors += 1
        
        # Rotate file every N seconds
        if time.time() - last_file_time >= rotation:
            if batch:
                filename = write_to_csv(batch, folder)
                total_files += 1
                batch = []  # Clear batch
                last_file_time = time.time()
        
        # Print statistics every second
        if total_records % 20 == 0:
            print_statistics(total_records, total_errors, total_files, start_time)
        
        # Control the speed (how many readings per second)
        time.sleep(1.0 / rate)
    
    # Write any remaining readings
    if batch:
        write_to_csv(batch, folder)
        total_files += 1
    
    # Print final summary
    elapsed = (datetime.now() - start_time).seconds
    print("\n" + "=" * 55)
    print("  GENERATION COMPLETE")
    print("=" * 55)
    print(f"  Total records : {total_records:,}")
    print(f"  Total errors  : {total_errors:,}")
    print(f"  Total files   : {total_files}")
    print(f"  Duration      : {elapsed} seconds")
    print(f"  Output folder : {os.path.abspath(folder)}")
    print("=" * 55)


# ============================================================================
# STEP 8: Program Entry Point
# ============================================================================

if __name__ == "__main__":
    config = load_config("config.yaml")
    run_generator(config)