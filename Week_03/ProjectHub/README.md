# ProjectHub

A professional full-stack project management platform built with FastAPI and modern web technologies.

![ProjectHub](https://img.shields.io/badge/ProjectHub-v1.0.0-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-00a393?style=flat&logo=fastapi)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791?style=flat&logo=postgresql)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Default Credentials](#default-credentials)
- [Frontend Pages](#frontend-pages)
- [Database Schema](#database-schema)
- [Security](#security)
- [Screenshots](#screenshots)
- [Contributing](#contributing)
- [License](#license)

---

## 📖 Overview

**ProjectHub** is a comprehensive project management system that enables teams to efficiently manage projects, tasks, and team members. It provides a modern, intuitive interface for tracking project progress, managing assignments, and collaborating effectively.

The application consists of two main components:
- **Backend**: A RESTful API built with FastAPI
- **Frontend**: A responsive web interface using vanilla JavaScript

---

## ✨ Features

### Authentication & Authorization
- JWT-based authentication
- Secure password hashing with bcrypt
- Protected routes and API endpoints
- Session management with token expiration

### Dashboard
- Real-time statistics (total projects, tasks, users, pending tasks)
- Recent projects overview
- Recent tasks overview
- Quick action buttons

### Project Management
- Create, read, update, and delete projects
- Assign project owners
- View project details with associated tasks
- Project status tracking

### Task Management
- Full CRUD operations for tasks
- Task assignment to users
- Status tracking (pending, in_progress, completed)
- Filter tasks by project

### User Management
- User registration and profile management
- Role-based access control
- Activity status tracking
- Secure password management

### UI/UX Features
- Modern, responsive design
- Toast notifications
- Modal dialogs
- Loading states
- Empty state handling
- Keyboard shortcuts
- Confirmation dialogs

---

## 🛠 Tech Stack

### Backend
| Technology | Description |
|------------|-------------|
| **FastAPI** | Modern Python web framework for building APIs |
| **SQLAlchemy** | SQL toolkit and ORM |
| **PostgreSQL** | Powerful, open source database |
| **Pydantic** | Data validation using Python type annotations |
| **JWT** | JSON Web Tokens for authentication |
| **Bcrypt** | Password hashing |
| **Uvicorn** | ASGI server implementation |

### Frontend
| Technology | Description |
|------------|-------------|
| **HTML5** | Semantic markup |
| **CSS3** | Modern styling with CSS variables |
| **JavaScript (ES6+)** | Client-side functionality |
| **Fetch API** | HTTP requests |
| **Local Storage** | Token and user data persistence |

---

## 📁 Project Structure

```
ProjectHub/
├── backend/
│   ├── main.py              # FastAPI application entry point
│   ├── database.py          # Database configuration
│   ├── seed_db.py           # Database seeding script
│   ├── requirements.txt     # Python dependencies
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py
│   │   ├── project.py
│   │   └── task.py
│   ├── routers/             # API route handlers
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── projects.py
│   │   └── tasks.py
│   ├── schemas/             # Pydantic schemas
│   │   ├── user.py
│   │   ├── project.py
│   │   └── task.py
│   └── utils/               # Utility functions
│       ├── auth_deps.py     # Authentication dependencies
│       ├── jwt.py           # JWT token handling
│       └── security.py      # Password hashing
│
└── frontend/
    ├── index.html           # Login page
    ├── dashboard.html       # Dashboard page
    ├── projects.html        # Projects management
    ├── tasks.html           # Tasks management
    ├── users.html           # Users management
    ├── css/
    │   └── style.css        # Main stylesheet
    └── js/
        ├── config.js        # Configuration and API client
        ├── api.js           # API functions
        ├── login.js         # Login functionality
        ├── dashboard.js     # Dashboard logic
        ├── projects.js      # Projects management
        ├── tasks.js         # Tasks management
        └── users.js         # Users management
```

---

## ✅ Prerequisites

Before running the application, ensure you have the following installed:

- **Python 3.9+**
- **PostgreSQL 15+** (or use default PostgreSQL credentials)
- **Node.js** (optional, for development)
- **Git** (for version control)

---

## 🔧 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd ProjectHub
```

### 2. Set Up Virtual Environment (Backend)

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate

# On macOS/Linux:
source .venv/bin/activate
```

### 3. Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the `backend` directory:

```env
# Database Configuration
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/projecthub_db

# JWT Configuration
SECRET_KEY=your-super-secret-key-change-this-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### 5. Set Up PostgreSQL Database

```bash
# Create database
createdb projecthub_db

# Or using psql
psql -U postgres -c "CREATE DATABASE projecthub_db;"
```

---

## 🚀 Running the Application

### Start the Backend Server

```bash
cd backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

The API will be available at: **http://127.0.0.1:8000**

### Start the Frontend

You can serve the frontend using any HTTP server:

**Option 1: Using Python**
```bash
cd frontend
python -m http.server 5500
```

**Option 2: Using VS Code Live Server**

Open `frontend/index.html` in VS Code and use the Live Server extension.

**Option 3: Using Node.js**
```bash
npx serve frontend
```

The frontend will be available at: **http://localhost:5500**

---

## 📚 API Documentation

Once the backend is running, access the interactive API documentation:

| Documentation | URL |
|---------------|-----|
| **Swagger UI** | http://127.0.0.1:8000/docs |
| **ReDoc** | http://127.0.0.1:8000/redoc |

### API Endpoints

#### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register a new user |
| POST | `/auth/login` | Login and get JWT token |

#### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users/` | Get all users |
| GET | `/users/{id}` | Get user by ID |
| POST | `/users/` | Create new user |
| PUT | `/users/{id}` | Update user |
| DELETE | `/users/{id}` | Delete user |

#### Projects
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/projects/` | Get all projects |
| GET | `/projects/{id}` | Get project by ID |
| POST | `/projects/` | Create new project |
| PUT | `/projects/{id}` | Update project |
| DELETE | `/projects/{id}` | Delete project |

#### Tasks
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tasks/` | Get all tasks (optional: `?project_id={id}`) |
| GET | `/tasks/{id}` | Get task by ID |
| POST | `/tasks/` | Create new task |
| PUT | `/tasks/{id}` | Update task |
| DELETE | `/tasks/{id}` | Delete task |

---

## 🔑 Default Credentials

After the first run, the database is automatically seeded with:

| Field | Value |
|-------|-------|
| **Username** | `admin` |
| **Email** | `admin@gmail.com` |
| **Password** | `123` |

> ⚠️ **Security Note**: Change the default admin password in production!

The seeding script also creates:
- 30 random users
- 50 sample projects
- 100 sample tasks

---

## 🖥 Frontend Pages

### 1. Login Page (`index.html`)
- User authentication
- JWT token storage
- Error handling

### 2. Dashboard (`dashboard.html`)
- Statistics cards (projects, tasks, users, pending)
- Recent projects list
- Recent tasks list
- Quick actions

### 3. Projects Page (`projects.html`)
- Project cards grid
- Create/Edit/Delete projects
- Project detail modal
- Owner assignment

### 4. Tasks Page (`tasks.html`)
- Task list view
- Status indicators (pending, in_progress, completed)
- Create/Edit/Delete tasks
- Project and assignee assignment

### 5. Users Page (`users.html`)
- User table view
- Create/Edit/Delete users
- Status badges

---

## 🗄 Database Schema

### Users Table
```
id          - Integer (Primary Key)
username    - String (Unique, Index)
email       - String (Unique, Index)
hashed_password - String
is_active   - Boolean (Default: True)
```

### Projects Table
```
id          - Integer (Primary Key)
title       - String (Required)
description - String
owner_id    - Integer (Foreign Key -> Users)
```

### Tasks Table
```
id          - Integer (Primary Key)
title       - String (Required)
description - String
status      - String (Default: "pending")
project_id  - Integer (Foreign Key -> Projects)
assigned_to - Integer (Foreign Key -> Users)
```

### Relationships
- **User -> Projects**: One-to-Many (A user can own multiple projects)
- **User -> Tasks**: One-to-Many (A user can have multiple assigned tasks)
- **Project -> Tasks**: One-to-Many (A project can have multiple tasks)

---

## 🔒 Security Features

- **Password Hashing**: All passwords are hashed using bcrypt
- **JWT Authentication**: Secure token-based authentication
- **CORS Protection**: Configured for specific origins only
- **Input Validation**: Pydantic models validate all inputs
- **SQL Injection Prevention**: SQLAlchemy ORM prevents SQL injection
- **XSS Prevention**: HTML escaping in user inputs

---

## 📸 Screenshots

### Login Page
Modern gradient login page with professional branding and form validation.

### Dashboard
Comprehensive dashboard showing:
- Project statistics
- Task overview
- Recent activity

### Projects Page
Grid layout with project cards, badges, and action buttons.

### Tasks Page
Clean task list with status indicators and quick actions.

### Users Page
Professional data table with user management capabilities.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License**.

---

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - The web framework used
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM
- [PostgreSQL](https://www.postgresql.org/) - Database
- [Faker](https://faker.readthedocs.io/) - For generating fake data
- [Colorama](https://pypi.org/project/colorama/) - For colored terminal output

---

## 📞 Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/issues) page
2. Review the API documentation at `/docs`
3. Check the console logs for error details

---

**Built with ❤️ using FastAPI and modern web technologies**

---

<p align="center">
  <strong>ProjectHub v1.0.0</strong><br>
  Professional Project Management Platform
</p>

