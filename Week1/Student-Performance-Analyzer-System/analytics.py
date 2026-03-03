"""
==============================================================
FILE: analytics.py
DESCRIPTION: Analytical functions for student performance data
==============================================================
"""

from models import SUBJECTS

GRADE_LABELS = {
    "A": "Excellent",
    "B": "Very Good",
    "C": "Good",
    "D": "Pass",
    "F": "Fail"
}


# -------------------- Student Rankings --------------------
def get_top_students(students: list, count: int = 5) -> list:
    """
    Get top N students by average score.
    Returns empty list if no students.
    """
    if not students:
        return []
    
    # Sort by average (highest first)
    sorted_students = sorted(
        students,
        key=lambda s: s.get_average(),
        reverse=True
    )
    
    return sorted_students[:count]


def get_bottom_students(students: list, count: int = 5) -> list:
    """
    Get bottom N students by average score.
    Returns empty list if no students.
    """
    if not students:
        return []
    
    # Sort by average (lowest first)
    sorted_students = sorted(
        students,
        key=lambda s: s.get_average()
    )
    
    return sorted_students[:count]


def get_struggling_students(students: list, threshold: float = 60.0) -> list:
    """
    Get students with average below threshold.
    """
    return [
        s for s in students
        if s.get_average() < threshold
    ]


def get_excellent_students(students: list, threshold: float = 90.0) -> list:
    """
    Get students with average above threshold (excellent).
    """
    return [
        s for s in students
        if s.get_average() >= threshold
    ]


# -------------------- Subject Analysis --------------------
def get_subject_averages(students: list) -> dict:
    """
    Calculate average for each subject.
    Returns dict {subject: average_score}
    """
    if not students:
        return {subject: 0.0 for subject in SUBJECTS}
    
    averages = {}
    for subject in SUBJECTS:
        total = sum(s.grades[subject] for s in students)
        averages[subject] = total / len(students)
    
    return averages


def get_best_subject(students: list) -> tuple:
    """
    Find subject with highest average.
    Returns (subject_name, average_score)
    """
    if not students:
        return (None, 0.0)
    
    averages = get_subject_averages(students)
    best_subject = max(averages, key=averages.get)
    
    return (best_subject, averages[best_subject])


def get_worst_subject(students: list) -> tuple:
    """
    Find subject with lowest average.
    Returns (subject_name, average_score)
    """
    if not students:
        return (None, 0.0)
    
    averages = get_subject_averages(students)
    worst_subject = min(averages, key=averages.get)
    
    return (worst_subject, averages[worst_subject])


# -------------------- Grade Distribution --------------------
def get_grade_distribution(students: list) -> dict:
    """
    Count students in each grade category.
    Returns dict {'A': count, 'B': count, ...}
    """
    distribution = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    
    for student in students:
        grade = student.get_letter_grade()
        if grade in distribution:
            distribution[grade] += 1
    
    return distribution


def display_grade_distribution(students: list):
    """
    Display grade distribution with percentages and bar chart.
    """
    if not students:
        print("No students to analyze")
        return
    
    distribution = get_grade_distribution(students)
    total = len(students)
    
    print("\n" + "="*50)
    print("📊 GRADE DISTRIBUTION")
    print("="*50)
    
    for grade in ["A", "B", "C", "D", "F"]:
        count = distribution[grade]
        percentage = (count / total * 100) if total > 0 else 0
        label = GRADE_LABELS[grade]
        
        # Create simple bar chart (each █ represents 5%)
        bar_length = int(percentage / 5)
        bar = "█" * bar_length
        
        print(f"{grade} ({label:10}): {count:2d} students ({percentage:5.1f}%) {bar}")
    
    print("="*50)


# -------------------- Statistics --------------------
def get_class_average(students: list) -> float:
    """Calculate overall class average"""
    if not students:
        return 0.0
    
    total = sum(s.get_average() for s in students)
    return total / len(students)


def get_median_score(students: list) -> float:
    """Calculate median average score"""
    if not students:
        return 0.0
    
    # Get all averages and sort
    averages = sorted([s.get_average() for s in students])
    n = len(averages)
    
    # Find median
    if n % 2 == 1:
        return averages[n // 2]
    else:
        return (averages[n // 2 - 1] + averages[n // 2]) / 2


def get_pass_rate(students: list, passing_score: float = 60.0) -> float:
    """Calculate percentage of students with average >= passing_score"""
    if not students:
        return 0.0
    
    passing = sum(1 for s in students if s.get_average() >= passing_score)
    return (passing / len(students)) * 100


# -------------------- Display Functions --------------------
def display_analytics_summary(students: list):
    """Show comprehensive analytics summary"""
    if not students:
        print("No students to analyze")
        return
    
    print("\n" + "="*60)
    print("📈 ANALYTICS SUMMARY")
    print("="*60)
    
    # Basic stats
    print(f"Total Students: {len(students)}")
    print(f"Class Average: {get_class_average(students):.1f}")
    print(f"Median Score: {get_median_score(students):.1f}")
    print(f"Pass Rate: {get_pass_rate(students):.1f}%")
    
    # Top students
    print("\n🏆 TOP 3 STUDENTS:")
    for i, s in enumerate(get_top_students(students, 3), 1):
        print(f"  {i}. {s.name} - {s.get_average():.1f} ({s.get_letter_grade()})")
    
    # Bottom students
    print("\n📉 BOTTOM 3 STUDENTS:")
    for i, s in enumerate(get_bottom_students(students, 3), 1):
        print(f"  {i}. {s.name} - {s.get_average():.1f} ({s.get_letter_grade()})")
    
    # Subject analysis
    best_subject, best_score = get_best_subject(students)
    worst_subject, worst_score = get_worst_subject(students)
    
    print(f"\n✅ Best Subject: {best_subject} ({best_score:.1f} avg)")
    print(f"❌ Worst Subject: {worst_subject} ({worst_score:.1f} avg)")
    
    # Grade distribution
    display_grade_distribution(students)