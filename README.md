<div align="center">

# Quizly Backend

REST API for an AI-powered quiz application that generates interactive quizzes from YouTube videos using speech recognition and artificial intelligence.

![Python](https://img.shields.io/badge/Python-3.12-0F172A?style=flat-square&logo=python&logoColor=FF9800)
![Django](https://img.shields.io/badge/Django-6.1-0F172A?style=flat-square&logo=django&logoColor=FF9800)
![Django REST Framework](https://img.shields.io/badge/DRF-3.18-0F172A?style=flat-square)

</div>

## Contents

- [Features](#features)
- [Technologies](#technologies)
- [Quick Start](#quick-start)
- [Frontend Integration](#frontend-integration)
- [Authentication](#authentication)
- [Permissions](#permissions)
- [Testing](#testing)
- [Admin Interface](#admin-interface)
- [Project Structure](#project-structure)
- [Notes](#notes)

## Features

The API provides:

- User registration and login
- JWT authentication with HttpOnly cookies
- Token refresh and secure logout
- Automatic quiz generation from YouTube videos
- Audio transcription using OpenAI Whisper (default mode)
- AI-generated questions using Google Gemini
- Optional direct Gemini video mode for deployments where YouTube blocks yt-dlp
- Quizzes with 10 questions and 4 answer options each
- Quiz management, including editing and deletion
- User-specific access permissions

## Technologies

- Python 3.12
- Django
- Django REST Framework
- SimpleJWT
- django-cors-headers
- yt-dlp & yt-dlp-ejs
- FFmpeg
- OpenAI Whisper
- Google Gemini
- python-dotenv
- SQLite

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/biancaliebholz/quizly_backend.git
cd quizly_backend
```

### 2. Create a virtual environment

Python 3.12 is required.

**macOS / Linux:**

```bash
python3.12 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
```

On Windows Command Prompt (CMD), activate with `venv\Scripts\activate.bat` instead.

### 3. Install the dependencies

FFmpeg and Node.js 22 or newer must be installed and available in your PATH.

```bash
python -m pip install -r requirements.txt
```

### 4. Configure the environment

Create the local environment file:

**macOS / Linux:**

```bash
cp .env.example .env
```

**Windows (PowerShell):**

```powershell
Copy-Item .env.example .env
```

On Windows CMD, use `copy .env.example .env`.

Generate a Django secret key (all systems):

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Add the generated key and your Gemini API key to `.env`:

```env
DJANGO_SECRET_KEY=your-generated-secret-key
GEMINI_API_KEY=your-gemini-api-key
DJANGO_DEBUG=True
```

Additional configuration options are documented in `.env.example`.

### 5. Apply the migrations

```bash
python manage.py migrate
```

### 6. Start the development server

```bash
python manage.py runserver 127.0.0.1:8000
```

The API is available at:

```text
http://127.0.0.1:8000/api/
```

## Frontend Integration

The compatible frontend is maintained in a separate repository:

[Quizly Frontend](https://github.com/Developer-Akademie-Backendkurs/project.Quizly.git)

Run the backend on port `8000` and start the frontend with VS Code Live Server on port `5500`.

```text
Backend:  http://127.0.0.1:8000
Frontend: http://127.0.0.1:5500
```

Both servers must be running for the complete application to work.

Use `127.0.0.1` instead of `localhost` to ensure cookie authentication works correctly. Other frontend ports must be added to `FRONTEND_ORIGINS` in `.env`.

## Authentication

The API uses JWT authentication with HttpOnly cookies.

Access tokens expire after 15 minutes, while refresh tokens remain valid for one day. Tokens are automatically sent with authenticated browser requests.

Logout invalidates both tokens and removes the authentication cookies.

For authenticated POST, PATCH and DELETE requests in Postman, include:

```http
Origin: http://127.0.0.1:5500
```

## Permissions

Protected endpoints require authentication. Users can access and manage their own quizzes, while access to another user's quizzes is restricted.

## Testing

Run the complete test suite:

```bash
python manage.py test
```

Check the Django configuration:

```bash
python manage.py check
```

Verify that no migrations are missing:

```bash
python manage.py makemigrations --check --dry-run
```

The current test suite contains **164 automated tests**, covering authentication, permissions, quiz management, AI services and error handling.

External services are mocked during testing, so no API calls or YouTube downloads are required.

## Admin Interface

Create an administrator account:

```bash
python manage.py createsuperuser
```

Start the development server and open:

```text
http://127.0.0.1:8000/admin/
```

The Django admin interface can be used to manage users, quizzes and individual questions.

## Project Structure

```text
quizly_backend/
├── auth_app/
│   ├── api/
│   └── tests/
├── quizzes_app/
│   ├── api/
│   ├── services/
│   └── tests/
├── core/
├── .env.example
├── manage.py
├── requirements.txt
└── README.md
```

Each application separates API logic, business logic and tests according to its responsibilities.

## Notes

- Quiz generation has two modes, selected with `QUIZ_USE_DIRECT_GEMINI_VIDEO` in `.env`:
    - `False` (default): yt-dlp and FFmpeg download the audio, Whisper transcribes it, and Gemini creates the quiz from the transcript.
    - `True`: Gemini processes the public YouTube URL directly, without a download and without Whisper. Use this for deployments where YouTube blocks yt-dlp. YouTube URL support in the Gemini API is a preview feature, so its pricing and rate limits may change.
- In both modes, the AI output is validated with the same rules and saved atomically.
- In the default mode, video duration is limited to 10 minutes and videos with insufficient speech are rejected. These are additional restrictions beyond the provided API contract. The direct Gemini video mode does not check either of them.
- Whisper runs locally, while Gemini requires an internet connection and API key.
- Python 3.12 and the pinned dependencies are required for the tested environment.
- The frontend is maintained separately and is not included in this repository.
- SQLite is used for local development. Production deployment requires additional security configuration.
- The local database, virtual environment and `.env` file are excluded from version control.
- The project was tested on macOS; Windows setup instructions are provided but have not been independently tested.
- This project was created for educational purposes.
