# Insighta Labs+ Backend API

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![JWT](https://img.shields.io/badge/JWT-000000?style=for-the-badge&logo=JSON%20web%20tokens&logoColor=white)](https://jwt.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 📌 Overview

Insighta Labs+ Backend is a production-ready demographic intelligence API that powers the Insighta Labs+ platform. It provides secure authentication, role-based access control, advanced demographic data querying, and natural language search capabilities.

### Key Capabilities

- **🔐 Secure Authentication**: GitHub OAuth with PKCE, JWT tokens (3 min access, 5 min refresh)
- **👥 Role-Based Access Control**: Admin and Analyst roles with endpoint-level permissions
- **🔍 Advanced Querying**: Filtering, sorting, pagination, and natural language search
- **📊 Data Export**: CSV export with filtering support
- **⚡ High Performance**: Optimized PostgreSQL queries with strategic indexing
- **🛡️ Security Features**: Rate limiting, request logging, and CORS protection

---

## 🏗️ Architecture






---

## 📋 Table of Contents

- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Environment Variables](#environment-variables)
- [Database Setup](#database-setup)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Authentication Flow](#authentication-flow)
- [Role-Based Access Control](#role-based-access-control)
- [API Endpoints](#api-endpoints)
- [Natural Language Parsing](#natural-language-parsing)
- [Error Handling](#error-handling)
- [Deployment](#deployment)
- [Testing](#testing)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)
- [API Versioning](#api-versioning)

---

## 🛠️ Tech Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Web Framework | FastAPI | 0.104+ | High-performance API framework |
| Database | PostgreSQL | 14+ / SQLite | Relational database (PostgreSQL for production) |
| ORM | SQLAlchemy | 2.0+ | Database abstraction and models |
| Authentication | python-jose | 3.3+ | JWT token handling |
| OAuth | Authlib / httpx | 1.2+ | GitHub OAuth integration |
| Rate Limiting | slowapi | 0.1+ | Request rate limiting |
| ASGI Server | Uvicorn | 0.24+ | Production ASGI server |
| Language | Python | 3.9+ | Core programming language |

---

## 📦 Prerequisites

- Python 3.9 or higher
- PostgreSQL 14+ (or SQLite for development)
- Git
- GitHub OAuth App (for authentication)

---

## 🔧 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/insighta-backend.git
cd insighta-backend



# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate


# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt


cp .env.example .env


# Database (PostgreSQL for production, SQLite for development)
DATABASE_URL=postgresql://user:password@localhost:5432/insighta_db

# GitHub OAuth (Required)
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_REDIRECT_URI=http://localhost:8000/auth/github/callback

# JWT Security (Change in production!)
SECRET_KEY=your-super-secret-key-minimum-32-characters
ACCESS_TOKEN_EXPIRE_MINUTES=3
REFRESH_TOKEN_EXPIRE_MINUTES=5
ALGORITHM=HS256

# API Configuration
API_VERSION=1
API_VERSION_HEADER=X-API-Version

# Frontend URLs (for redirects)
WEB_PORTAL_URL=http://localhost:3000
CLI_CALLBACK_URL=http://localhost:8085/callback

# Environment
ENVIRONMENT=development
DEBUG=True



# Install PostgreSQL (Ubuntu/Debian)
sudo apt-get install postgresql postgresql-contrib

# Start PostgreSQL
sudo systemctl start postgresql

# Create database
sudo -u postgres psql
CREATE DATABASE insighta_db;
CREATE USER insighta_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE insighta_db TO insighta_user;
\q

# Run migrations
python -c "from app.database.database import init_db; init_db()"