# iSubmit

BSIT Capstone Project

---

## Setup

This project uses **Docker for Redis** and **Uvicorn for running the Django application**.

You will need:

* Python 3.12+
* Docker Desktop
* Git

---

## Step 1: Install Docker

### Windows / macOS

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/).

### Linux

Install Docker Engine using the [official Docker installation guide](https://docs.docker.com/engine/install/).

---

## Step 2: Clone the Repository

Clone the repository:

```bash
git clone <REPOSITORY_URL>
```

Then enter the project directory:

```bash
cd iSubmit
```

You can also use GitHub Desktop.

---

## Step 3: Set Up Environment Variables

1. Copy `.env.example`.
2. Rename the copy to `.env`.
3. Fill in the required credentials.

Example:

```text
.env.example → .env
```

Ask a team member for the required environment variable values.

> Do not commit `.env` to Git.

---

## Step 4: Create a Virtual Environment

Create a Python virtual environment from the project root:

### Windows

```powershell
py -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

---

## Step 5: Install Dependencies

With the virtual environment activated:

```bash
pip install -r requirements.txt
```

---

## Step 6: Start Redis

Redis is required for the application's real-time functionality.

From the **project root**, run:

```bash
docker compose up -d redis
```

Check that Redis is running:

```bash
docker compose ps
```

You should see the Redis container running.

---

## Step 7: Run Database Migrations

Move into the backend directory:

```bash
cd backend
```

Run:

```bash
python manage.py migrate
```

---

## Step 8: Start the Application

The application uses **Uvicorn** to run the Django ASGI application.

From the `backend` directory, run:

```bash
uvicorn config.asgi:application --host 127.0.0.1 --port 8000
```

Once the server starts, open:

**http://127.0.0.1:8000**

---
# Daily Workflow

Whenever you start working on the project:

### Step 1 - Start Redis

From the project root:

```bash
docker compose up -d redis
```

### Step 2 - Run Database Migrations

From the `backend` directory:

```bash
cd backend
python manage.py migrate
```

> **Note:** Always run migrations before starting the application. This helps ensure that your local database is up to date with the latest database changes made to the project.

### Step 3 - Start Uvicorn

From the `backend` directory:

```bash
uvicorn config.asgi:application --host 127.0.0.1 --port 8000
```

Then open:

**http://127.0.0.1:8000**

---

# Stopping the Application

To stop Uvicorn, press:

```text
Ctrl + C
```

To stop Redis:

```bash
docker compose stop redis
```


> **Note:** Stop the application whenever a new change is made to the codebase. `Ctrl + C` to stop, then `uvicorn config.asgi:application --host 127.0.0.1 --port 8000` to run again.

---

# Restarting Redis

If Redis has already been created but is stopped:

```bash
docker compose start redis
```

Alternatively, this is also safe to use:

```bash
docker compose up -d redis
```

---