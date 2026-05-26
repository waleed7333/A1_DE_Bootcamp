# 🎓 Student Management & Analytics System

A comprehensive Student Management System built with Python that demonstrates **Object-Oriented Programming**, **Encapsulation**, **Data Analysis**, and **Clean Code** principles. Perfect for learning Python project structure and best practices.

---

## 🚀 After Running the Code

**Admin Account**  
- Username: `admin`  
- Password: `admin123`  

**User Account**  
- Username: `user`  
- Password: `user123`  

---

## 👑 Admin Permissions

- View all students  
- Add new student  
- Delete student  
- Update grades  
- Search by ID  
- Search by name  
- View grade distribution  
- View analytics  

---

## 👤 User Permissions

- View all students  
- Search by ID  
- Search by name  
- View grade distribution  
- View analytics  

---

## 📁 Project Structure

```text
student-management-system/
│
├── 📄 main.py                 # Entry point & interactive CLI menu
├── 📄 models.py               # Student & Classroom classes (core models)
├── 📄 auth.py                 # User authentication & session management
├── 📄 utils.py                # Helper functions (I/O, validation, display)
├── 📄 analytics.py            # Data analysis & statistics functions
│
├── 📁 data/                   # Data storage directory
│   ├── 📄 users.csv           # User credentials (manual setup)
│   └── 📄 students.csv        # Student records (auto-generated)
│
├── 📁 reports/                # System logs directory
│   └── 📄 system_log.txt      # Activity log with timestamps (auto-generated)
│
└── 📄 README.md               # Project documentation (you are here)
```

---

# 📦 Module Details

---

## 1️⃣ models.py — Core Data Models

```python
"""
Contains the fundamental data structures of the system.
"""

# Constants
SUBJECTS = ["Math", "Science", "English", "History", "Art"]
GRADE_LABELS = {"A": "Excellent", "B": "Very Good", ...}

class Student:
    """Represents a single student with private attributes."""
    # attributes:
    - __id 
    - __name
    - __grades 

    # methods:
    - get_average(), 
    - get_letter_grade(), 
    - update_grade()
    - to_csv_row(), 
    - from_csv_row() (CSV conversion)

class Classroom:
    """Manages collection of students."""
    - __students

    - add_student(), 
    - remove_student(), 
    - find_by_id()
    - find_by_name(), 
    - display_student_details()
    - get_top_students(), 
    - get_grade_distribution()
```

---

## 2️⃣ auth.py — Authentication System

```python
"""
Handles user authentication and session management.
"""

class User:
    """Represents authenticated user."""
    - username
    - role: str (admin/user)
    - is_admin(): bool

# Functions
- load_users() : Load users from CSV
- login() : Authenticate and return User object
- logout() : End session and log action
```

---

## 3️⃣ utils.py — Utility Functions

```python
"""
Helper functions for file operations, validation, and display.
"""

# File Operations
- load_students() : Read students from CSV
- save_students() : Write students to CSV

# Input Validation
- get_valid_grade() : Validate grade (0-100)
- confirm_action() : Get yes/no confirmation
- generate_id() : Create unique student ID

# Display Functions
- display_students_table() : Show formatted table
- print_header() : Print section headers
- clear_screen() : Clear terminal
- pause() : Wait for user input

# Logging
- record_action() : Write to log file
```

---

## 4️⃣ analytics.py — Data Analysis

```python
"""
Analytical functions for student performance data.
"""

# Rankings
- get_top_students() : Best performers
- get_bottom_students() : Lowest performers
- get_struggling_students() : Students below threshold

# Subject Analysis
- get_subject_averages() : Average per subject
- get_best_subject() : Subject with highest average
- get_worst_subject() : Subject with lowest average

# Distribution
- get_grade_distribution() : Count per grade
- display_grade_distribution() : Show with bar chart

# Statistics
- get_class_average() : Overall class average
- get_median_score() : Median average
- get_pass_rate() : Percentage passing
```

---

## 5️⃣ main.py — Application Entry Point

```python
"""
Main program with interactive menu and user flows.
"""

# Menu System
- display_menu() : Show options based on role

# Admin Flows
- add_student_flow() : Complete add process
- delete_student_flow() : Remove student with confirmation
- update_grades_flow() : Modify student grades

# User Flows
- list_students_flow() : Display all students
- search_by_id_flow() : Find and show student by ID
- search_by_name_flow() : Search by name (partial)
- show_distribution_flow() : Display grade distribution
- show_analytics_flow() : Show comprehensive analytics

# Main Loop
- main() : Program entry point with error handling
```