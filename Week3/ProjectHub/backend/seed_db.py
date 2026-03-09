# PROJECTHUB/backend/seed_db.py

import random
from faker import Faker
from database import SessionLocal, engine, Base
from models.user import User
from models.project import Project
from models.task import Task
from utils.security import hash_password

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    GREEN = Fore.GREEN; RED = Fore.RED; YELLOW = Fore.YELLOW; RESET = Style.RESET_ALL
except ImportError:
    GREEN = RED = YELLOW = RESET = ""

fake = Faker()

def seed_database():
    db = SessionLocal()
    
    try:
        print(f"{YELLOW}--- 🗑️  Cleaning Database ---")
        db.query(Task).delete()
        db.query(Project).delete()
        db.query(User).delete()
        db.commit()
        # ------------------ Create Admin User ------------------
        print(f"{GREEN}--- 👤 Creating Admin User ---")
        admin = User(
            username="admin",
            email="admin@gmail.com",
            hashed_password=hash_password("123"),
            is_active=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        all_users = [admin]

        # ------------------ Create 30 Random Users ------------------
        print(f"{GREEN}--- 👥 Creating 30 Random Users ---")
        for _ in range(30):
            u = User(
                username=fake.unique.user_name(),
                email=fake.unique.email(),
                hashed_password=hash_password("password123"),
                is_active=True
            )
            db.add(u)
            all_users.append(u)
        
        db.flush()

        # ------------------ Create 50 Random Projects ------------------
        all_projects = []
        print(f"{GREEN}--- 🏗️  Creating 50 Projects ---")
        for _ in range(50):
            p = Project(
                title=fake.catch_phrase(),
                description=fake.text(max_nb_chars=100),
                owner_id=random.choice(all_users).id
            )
            db.add(p)
            all_projects.append(p)
        
        db.flush() 

        # ------------------ Create 100 Random Tasks ------------------
        print(f"{GREEN}--- ✅ Creating Realistic Tasks ---")
        status_options = ["pending", "in_progress", "completed"]

        for _ in range(100):
            t = Task(
                title=fake.bs().capitalize(), 
                description=fake.sentence(),
                status=random.choice(status_options),
                project_id=random.choice(all_projects).id,
                assigned_to=random.choice(all_users).id
            )
            db.add(t)
        db.commit()
        print(f"\n{GREEN}🚀 Database is ready with Admin, Users, Projects, and Tasks!")

    except Exception as e:
        db.rollback()
        print(f"{RED}❌ Error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    seed_database()

