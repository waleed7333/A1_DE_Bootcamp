"""
==============================================================
FILE: models.py
DESCRIPTION: Core data models - Student and Classroom classes
==============================================================
"""

# -------------------- Constants --------------------
SUBJECTS = ["Math", "Science", "English", "History", "Art"]

GRADE_LABELS = {
    "A": "Excellent",
    "B": "Very Good",
    "C": "Good",
    "D": "Pass",
    "F": "Fail"
}


# -------------------- Student Class --------------------
class Student:
    """
    Represents a single student with personal info and grades.
    Uses encapsulation (private attributes) for data protection.
    """
    
    def __init__(self, student_id: str, name: str, grades: dict):
        # Private attributes (encapsulation)
        self.__id = str(student_id)
        self.__name = name.strip()
        self.__grades = {}
        
        # Validate and store grades
        for subject, score in grades.items():
            if subject in SUBJECTS:
                self.__grades[subject] = self._validate_grade(score)
    
    # ---------- Private Helper Method ----------
    @staticmethod
    def _validate_grade(score) -> int:
        """Ensure grade is between 0-100"""
        score = int(score)
        if not (0 <= score <= 100):
            raise ValueError(f"Grade must be 0-100, got {score}")
        return score
    
    # ---------- Properties (Controlled Access) ----------
    @property
    def id(self) -> str:
        """Read-only ID"""
        return self.__id
    
    @property
    def name(self) -> str:
        """Read-only name"""
        return self.__name
    
    @property
    def grades(self) -> dict:
        """Return a COPY of grades (prevents direct modification)"""
        return self.__grades.copy()
    
    # ---------- Grade Calculation Methods ----------
    def get_total_score(self) -> int:
        """Sum of all subject grades"""
        return sum(self.__grades.values())
    
    def get_average(self) -> float:
        """Average score across all subjects"""
        if not self.__grades:
            return 0.0
        return self.get_total_score() / len(self.__grades)
    
    def get_letter_grade(self) -> str:
        """Convert average to letter grade (A, B, C, D, F)"""
        avg = self.get_average()
        
        if avg >= 90:
            return "A"
        if avg >= 80:
            return "B"
        if avg >= 70:
            return "C"
        if avg >= 60:
            return "D"
        return "F"
    
    def get_grade_description(self) -> str:
        """Get description for the letter grade"""
        return GRADE_LABELS[self.get_letter_grade()]
    
    def get_display_grade(self) -> str:
        """Combined format: 'B     Very Good'"""
        return f"{self.get_letter_grade()}     {self.get_grade_description()}"
    
    # ---------- Update Methods ----------
    def update_grade(self, subject: str, new_score: int) -> bool:
        """Update a specific subject grade"""
        try:
            if subject not in SUBJECTS:
                print(f"Error: '{subject}' is not a valid subject")
                return False
            
            validated_score = self._validate_grade(new_score)
            self.__grades[subject] = validated_score
            return True
            
        except ValueError as e:
            print(f"Error: {e}")
            return False
    
    # ---------- CSV Methods ----------
    def to_csv_row(self) -> dict:
        """Convert student to CSV row dictionary"""
        row = {"id": self.__id, "name": self.__name}
        for subject in SUBJECTS:
            row[subject] = self.__grades.get(subject, 0)
        return row
    
    @classmethod
    def from_csv_row(cls, row: dict):
        """Create Student from CSV row (alternative constructor)"""
        grades = {}
        for subject in SUBJECTS:
            try:
                grades[subject] = int(row.get(subject, 0))
            except (ValueError, TypeError):
                grades[subject] = 0
        
        return cls(row["id"], row["name"], grades)
    
    # ---------- String Representation ----------
    def __str__(self) -> str:
        return f"Student(ID: {self.__id}, Name: {self.__name})"
    
    def __repr__(self) -> str:
        return f"Student('{self.__id}', '{self.__name}', {self.__grades})"


# -------------------- Classroom Class --------------------
class Classroom:
    """
    Manages a collection of students with search and analysis methods.
    """
    
    def __init__(self):
        self.__students = []  # Private list of students
    
    # ---------- Properties ----------
    @property
    def students(self) -> list:
        """Return a copy to prevent direct manipulation"""
        return self.__students.copy()
    
    @property
    def count(self) -> int:
        """Number of students in classroom"""
        return len(self.__students)
    
    # ---------- Core Management Methods ----------
    def add_student(self, student: Student) -> bool:
        """Add a new student to the classroom"""
        # Check for duplicate ID
        if self.find_by_id(student.id):
            print(f"Error: Student ID {student.id} already exists")
            return False
        
        self.__students.append(student)
        return True
    
    def remove_student(self, student_id: str) -> bool:
        """Remove a student by ID"""
        student = self.find_by_id(student_id)
        if student:
            self.__students.remove(student)
            return True
        return False
    
    # ---------- Search Methods ----------
    def find_by_id(self, student_id: str):
        """Find student by exact ID"""
        for student in self.__students:
            if student.id == str(student_id):
                return student
        return None
    
    def find_by_name(self, name: str) -> list:
        """
        Find students by name (partial match, case insensitive)
        Returns list of matching students
        """
        search_term = name.lower().strip()
        results = []
        
        for student in self.__students:
            if search_term in student.name.lower():
                results.append(student)
        
        return results
    
    def display_student_details(self, student_id: str) -> bool:
        """Show detailed information for a specific student"""
        student = self.find_by_id(student_id)
        
        if not student:
            print(f"❌ Student ID {student_id} not found")
            return False
        
        print("\n" + "="*50)
        print(f"📋 STUDENT DETAILS: {student.name}")
        print("="*50)
        print(f"ID: {student.id}")
        
        print("\n📚 Grades:")
        for subject, grade in student.grades.items():
            print(f"  {subject:10}: {grade:3}")
        
        print(f"\n📊 Total: {student.get_total_score()}")
        print(f"📈 Average: {student.get_average():.1f}")
        print(f"🏆 Grade: {student.get_display_grade()}")
        
        return True
    
    # ---------- Analytics Methods ----------
    def calculate_class_average(self) -> float:
        """Average of all student averages"""
        if not self.__students:
            return 0.0
        
        total = sum(s.get_average() for s in self.__students)
        return total / len(self.__students)
    
    def get_top_students(self, count: int = 3) -> list:
        """Get top N students by average"""
        sorted_students = sorted(
            self.__students,
            key=lambda s: s.get_average(),
            reverse=True
        )
        return sorted_students[:count]
    
    def get_lowest_students(self, count: int = 3) -> list:
        """Get lowest N students by average"""
        sorted_students = sorted(
            self.__students,
            key=lambda s: s.get_average()
        )
        return sorted_students[:count]
    
    def get_grade_distribution(self) -> dict:
        """Count students in each grade category"""
        distribution = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        
        for student in self.__students:
            grade = student.get_letter_grade()
            distribution[grade] += 1
        
        return distribution
    
    def get_subject_averages(self) -> dict:
        """Calculate average for each subject"""
        if not self.__students:
            return {s: 0.0 for s in SUBJECTS}
        
        averages = {}
        for subject in SUBJECTS:
            total = sum(s.grades[subject] for s in self.__students)
            averages[subject] = total / len(self.__students)
        
        return averages