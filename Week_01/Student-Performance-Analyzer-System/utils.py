"""
==============================================================
FILE: utils.py
DESCRIPTION: Utility functions for file I/O, validation, display
==============================================================
"""

import csv
import os
import platform
from datetime import datetime
from colorama import Fore, Style

# Import constants only (not classes to avoid circular imports)
from models import SUBJECTS


# -------------------- File Operations --------------------
def load_students(file_path: str) -> list:
    """Load students from CSV file"""
    from models import Student  # Local import to avoid circular dependency
    
    students = []
    
    if not os.path.exists(file_path):
        print(Fore.YELLOW + f"Note: File '{file_path}' not found. Starting fresh.")
        return students
    
    try:
        with open(file_path, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                try:
                    student = Student.from_csv_row(row)
                    students.append(student)
                except Exception as e:
                    print(Fore.RED + f"Error loading student: {e}")
        
        print(Fore.GREEN + f"✓ Loaded {len(students)} students")
        
    except Exception as e:
        print(Fore.RED + f"Error reading file: {e}")
    
    return students


def save_students(file_path: str, students: list) -> bool:
    """Save students to CSV file"""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, mode="w", newline="", encoding="utf-8") as file:
            fieldnames = ["id", "name"] + SUBJECTS
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            
            writer.writeheader()
            for student in students:
                writer.writerow(student.to_csv_row())
        
        print(Fore.GREEN + f"✓ Saved {len(students)} students to file")
        return True
        
    except Exception as e:
        print(Fore.RED + f"Error saving file: {e}")
        return False


# -------------------- Input Validation --------------------
def get_valid_grade(prompt: str) -> int:
    """
    Prompt user for a grade and validate it's between 0-100.
    Keeps asking until valid input is received.
    """
    while True:
        try:
            grade = input(prompt).strip()
            
            # Check if empty
            if not grade:
                print(Fore.RED + "Error: Grade cannot be empty")
                continue
            
            # Convert to integer
            grade = int(grade)
            
            # Check range
            if 0 <= grade <= 100:
                return grade
            else:
                print(Fore.RED + "Error: Grade must be between 0 and 100")
                
        except ValueError:
            print(Fore.RED + "Error: Please enter a valid number")


def get_valid_id(prompt: str, students: list) -> str:
    """
    Get a valid student ID that doesn't already exist.
    Used when adding new students.
    """
    while True:
        student_id = input(prompt).strip()
        
        if not student_id:
            print(Fore.RED + "Error: ID cannot be empty")
            continue
        
        # Check if ID already exists
        exists = any(s.id == student_id for s in students)
        if exists:
            print(Fore.RED + f"Error: ID '{student_id}' already exists")
            continue
        
        return student_id


def confirm_action(message: str) -> bool:
    """Ask user for confirmation (y/n)"""
    while True:
        response = input(Fore.YELLOW + message + " (y/n): ").lower().strip()
        
        if response in ['y', 'yes']:
            return True
        if response in ['n', 'no']:
            return False
        
        print(Fore.RED + "Please enter 'y' or 'n'")


def generate_id(students: list) -> str:
    """Generate a new unique student ID"""
    if not students:
        return "1"
    
    # Find max existing ID and add 1
    try:
        max_id = max(int(s.id) for s in students)
        return str(max_id + 1)
    except ValueError:
        # If IDs aren't numbers, use timestamp
        return str(int(datetime.now().timestamp()))


# -------------------- Screen Management --------------------
def clear_screen():
    """Clear terminal screen (cross-platform)"""
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")


def pause():
    """Wait for user to press Enter"""
    input(Fore.CYAN + "\nPress Enter to continue..." + Style.RESET_ALL)


def print_header(title: str):
    """Print a formatted header"""
    print(Fore.CYAN + "\n" + "="*60)
    print(Fore.CYAN + f" {title}")
    print(Fore.CYAN + "="*60 + Style.RESET_ALL)


def print_success(message: str):
    """Print success message in green"""
    print(Fore.GREEN + f"✓ {message}" + Style.RESET_ALL)


def print_error(message: str):
    """Print error message in red"""
    print(Fore.RED + f"✗ {message}" + Style.RESET_ALL)


def print_warning(message: str):
    """Print warning message in yellow"""
    print(Fore.YELLOW + f"⚠ {message}" + Style.RESET_ALL)


# -------------------- Display Functions --------------------
def display_students_table(students: list):
    """Display students in a formatted table"""
    if not students:
        print_warning("No students to display")
        return
    
    # Table header
    header = f"{'ID':<4} {'Name':<18}"
    for subject in SUBJECTS:
        header += f"{subject:<8}"
    header += f"{'Total':<7}{'Avg':<7}{'Grade':<20}"
    
    print(Fore.CYAN + header)
    print(Fore.CYAN + "-" * len(header))
    
    # Table rows
    for student in students:
        row = f"{student.id:<4} {student.name:<18}"
        
        for subject in SUBJECTS:
            grade = student.grades.get(subject, 0)
            row += f"{grade:<8}"
        
        row += f"{student.get_total_score():<7}"
        row += f"{student.get_average():<7.1f}"
        row += f"{student.get_display_grade():<20}"
        
        print(Fore.WHITE + row)
    
    # Footer with count
    print(Fore.CYAN + "-" * len(header))
    print(Fore.CYAN + f"Total: {len(students)} students" + Style.RESET_ALL)


# -------------------- Logging System --------------------
def record_action(action: str):
    """Record an action to the log file"""
    try:
        # Create reports directory
        log_dir = "reports"
        os.makedirs(log_dir, exist_ok=True)
        
        # Prepare log entry
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {action}\n"
        
        # Write to log file
        log_file = os.path.join(log_dir, "system_log.txt")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
            
    except Exception as e:
        # Don't crash the program if logging fails
        print(Fore.RED + f"Warning: Could not write to log file: {e}")