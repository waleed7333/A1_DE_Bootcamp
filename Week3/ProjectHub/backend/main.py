# PROJECTHUB/backend/main.py
from fastapi import FastAPI
from fastapi.security import HTTPBearer
from routers import users, projects, tasks, auth
from database import Base, engine, SessionLocal
from fastapi.middleware.cors import CORSMiddleware
from models.user import User

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ProjectHub API", version="1.0.0")

# Security scheme
security = HTTPBearer()

# ✅ CORS Configuration
origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(auth.router)


# ✅ Seed Database on Startup
@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        if user_count == 0:
            print("🚀 Seeding database with initial data...")
            from seed_db import seed_database
            seed_database()
            print("✅ Database seeded successfully!")
        else:
            print(f"📊 Database already has {user_count} users. Skipping seed.")
    finally:
        db.close()


@app.get("/")
def root():
    return {"message": "Welcome to ProjectHub API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}

