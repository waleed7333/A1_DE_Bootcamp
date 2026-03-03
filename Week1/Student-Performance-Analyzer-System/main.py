"""
==============================================================
FILE: main.py
DESCRIPTION: Main program entry point with interactive menu
==============================================================
"""

import os
from colorama import Fore, init

# Import project modules
import auth
import utils
import analytics
import models

# Initialize colorama
init(autoreset=True)


# -------------------- Menu Display --------------------
def display_menu(title: str, user, options: dict) -> str:
    """
    Show main menu with user info and available options.
    Returns user's choice.
    """
    utils.clear_screen()
    
    # Set role color
    role_color = Fore.RED if user.is_admin() else Fore.GREEN
    role_text = "ADMIN" if user.is_admin() else "USER"
    
    # Print header
    print(Fore.CYAN + "\n" + "="*60)
    print(Fore.CYAN + f" {title}")
    print(Fore.CYAN + "="*60)
    print(role_color + f" User: {user.username} | Role: {role_text}")
    print(Fore.CYAN + "-"*60)
    
    # Print options
    for key, desc in options.items():
        print(Fore.YELLOW + f" {key}. " + Fore.WHITE + desc)
    
    print(Fore.CYAN + "-"*60)
    
    # Get choice
    return input(Fore.CYAN + " Select option: " + Fore.WHITE).strip()


# -------------------- Admin Functions --------------------
def add_student_flow(classroom):
    """Handle add new student process"""
    utils.print_header("ADD NEW STUDENT")
    
    # Get student info
    name = input("Enter student name: ").strip()
    if not name:
        utils.print_error("Name cannot be empty")
        return
    
    # Collect grades
    grades = {}
    for subject in models.SUBJECTS:
        grade = utils.get_valid_grade(f"  {subject} grade: ")
        grades[subject] = grade
    
    # Generate ID and create student
    new_id = utils.generate_id(classroom.students)
    student = models.Student(new_id, name, grades)
    
    # Add to classroom
    if classroom.add_student(student):
        # Save to file
        utils.save_students("data/students.csv", classroom.students)
        utils.record_action(f"ADD student: {name} (ID: {new_id})")
        utils.print_success(f"Student added with ID: {new_id}")
    else:
        utils.print_error("Failed to add student")


def delete_student_flow(classroom):
    """Handle delete student process"""
    utils.print_header("DELETE STUDENT")
    
    student_id = input("Enter student ID to delete: ").strip()
    student = classroom.find_by_id(student_id)
    
    if not student:
        utils.print_error(f"Student ID {student_id} not found")
        return
    
    # Show student info and confirm
    print(f"Name: {student.name}")
    if utils.confirm_action(f"Delete {student.name}?"):
        if classroom.remove_student(student_id):
            utils.save_students("data/students.csv", classroom.students)
            utils.record_action(f"DELETE student: {student.name} (ID: {student_id})")
            utils.print_success("Student deleted")
        else:
            utils.print_error("Delete failed")


def update_grades_flow(classroom):
    """Handle update grades process"""
    utils.print_header("UPDATE GRADES")
    
    student_id = input("Enter student ID: ").strip()
    student = classroom.find_by_id(student_id)
    
    if not student:
        utils.print_error(f"Student ID {student_id} not found")
        return
    
    # Show current grades
    print(f"\nStudent: {student.name}")
    print("Current grades:")
    for i, subject in enumerate(models.SUBJECTS, 1):
        print(f"  {i}. {subject}: {student.grades[subject]}")
    
    # Select subject
    try:
        choice = int(input("\nSelect subject number: "))
        if 1 <= choice <= len(models.SUBJECTS):
            subject = models.SUBJECTS[choice - 1]
        else:
            utils.print_error("Invalid choice")
            return
    except ValueError:
        utils.print_error("Please enter a number")
        return
    
    # Get new grade
    print(f"Current {subject} grade: {student.grades[subject]}")
    new_grade = utils.get_valid_grade(f"New grade for {subject}: ")
    
    # Confirm and update
    if utils.confirm_action("Update grade?"):
        if student.update_grade(subject, new_grade):
            utils.save_students("data/students.csv", classroom.students)
            utils.record_action(f"UPDATE {subject} for {student.name}: {new_grade}")
            utils.print_success("Grade updated")
        else:
            utils.print_error("Update failed")


# -------------------- User Functions --------------------
def list_students_flow(classroom):
    """Display all students"""
    utils.print_header("STUDENT LIST")
    utils.display_students_table(classroom.students)
    utils.pause()


def search_by_id_flow(classroom):
    """Search and display student by ID"""
    utils.print_header("SEARCH BY ID")
    student_id = input("Enter student ID: ").strip()
    classroom.display_student_details(student_id)
    utils.pause()


def search_by_name_flow(classroom):
    """Search and display students by name"""
    utils.print_header("SEARCH BY NAME")
    name = input("Enter name (or part of name): ").strip()
    
    results = classroom.find_by_name(name)
    
    if results:
        print(f"\nFound {len(results)} student(s):")
        utils.display_students_table(results)
    else:
        utils.print_warning(f"No students found with '{name}'")
    
    utils.pause()


def show_distribution_flow(classroom):
    """Show grade distribution"""
    utils.print_header("GRADE DISTRIBUTION")
    analytics.display_grade_distribution(classroom.students)
    utils.pause()


def show_analytics_flow(classroom):
    """Show comprehensive analytics"""
    utils.print_header("ANALYTICS DASHBOARD")
    analytics.display_analytics_summary(classroom.students)
    utils.pause()


# -------------------- Main Program --------------------
def main():
    """Main program entry point"""
    
    # Create data directory if needed
    os.makedirs("data", exist_ok=True)
    
    # Load data
    users = auth.load_users("data/users.csv")
    students = utils.load_students("data/students.csv")
    
    # Create classroom and add students
    classroom = models.Classroom()
    for s in students:
        classroom.add_student(s)
    
    # Welcome message
    utils.clear_screen()
    print(Fore.CYAN + "\n🎓 WELCOME TO STUDENT MANAGEMENT SYSTEM")
    print(Fore.CYAN + "="*60)
    
    # Login
    user = None
    while not user:
        user = auth.login(users)
        if not user:
            print(Fore.YELLOW + "\nTry again or press Ctrl+C to exit")
    
    utils.print_success(f"Welcome, {user.username}!")
    utils.record_action(f"SESSION_START user={user.username}")
    
    # Main loop
    running = True
    while running:
        # Define menu based on role
        if user.is_admin():
            menu = {
                "1": "📋 List all students",
                "2": "➕ Add new student",
                "3": "🗑️ Delete student",
                "4": "✏️ Update grades",
                "5": "🔍 Search by ID",
                "6": "🔎 Search by name",
                "7": "📊 Grade distribution",
                "8": "📈 Analytics dashboard",
                "0": "🚪 Logout"
            }
        else:
            menu = {
                "1": "📋 List students",
                "5": "🔍 Search by ID",
                "6": "🔎 Search by name",
                "7": "📊 Grade distribution",
                "8": "📈 Analytics dashboard",
                "0": "🚪 Exit"
            }
        
        # Show menu and get choice
        choice = display_menu("MAIN MENU", user, menu)
        
        # Process choice
        if choice == "1":
            list_students_flow(classroom)
        
        elif choice == "2" and user.is_admin():
            add_student_flow(classroom)
        
        elif choice == "3" and user.is_admin():
            delete_student_flow(classroom)
        
        elif choice == "4" and user.is_admin():
            update_grades_flow(classroom)
        
        elif choice == "5":
            search_by_id_flow(classroom)
        
        elif choice == "6":
            search_by_name_flow(classroom)
        
        elif choice == "7":
            show_distribution_flow(classroom)
        
        elif choice == "8":
            show_analytics_flow(classroom)
        
        elif choice == "0":
            # Logout and exit
            auth.logout(user)
            utils.print_success("Thank you for using the system!")
            running = False
        
        else:
            utils.print_error("Invalid option")
            utils.pause()
    
    # Final message
    print(Fore.CYAN + "\n👋 Goodbye!")
    utils.record_action(f"SESSION_END user={user.username}")


# Program entry point
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n\n⚠️ Program interrupted by user")
        print(Fore.CYAN + "Goodbye!")
    except Exception as e:
        print(Fore.RED + f"\n❌ Unexpected error: {e}")
        utils.record_action(f"ERROR: {e}")