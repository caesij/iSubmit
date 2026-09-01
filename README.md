# iSubmit
BSIT Capstone Project

## Project Structure

```
iSubmit/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── entrypoint.sh
├── requirements.txt
├── .env
├── .env.example
├── backend/
└── frontend/
```

There are two ways to run this project: **with Docker** (recommended — no need to install local Python or manage a virtual environment) or **without Docker** (a traditional local Python setup). Pick one.

---

## Option A: Setup with Docker (recommended)

### Step 1: Install Docker

- **Windows/Mac**: install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
- **Linux**: install Docker Engine directly (not Docker Desktop) — see [Docker's official install docs](https://docs.docker.com/engine/install/) for your distro.

### Step 2: Set up environment variables

1. Duplicate `.env.example` in the project root.
2. Rename the copy to `.env`.
3. Fill in the required credentials (ask a team member for the actual values).

### Step 3: Build and run

From the project root run in terminal:

```bash
docker compose up --build
```

Visit **http://localhost:8000** once you see `Listening at: http://0.0.0.0:8000` in the logs.

### Day-to-day usage after the first build

```bash
docker compose up             # runserver
docker compose restart        # picks up code changes (no rebuild needed)
```

Only use `--build` again if you changed `requirements.txt`, the `Dockerfile`, or `entrypoint.sh`.

### Running management commands

Since there's no local Python install, run Django commands inside the container. Example:

```bash
docker compose exec web python manage.py migrate
```

---

## Option B: Setup without Docker (local Python)

### Step 1: Create a virtual environment

**Windows**
```bash
py -m venv .venv
.venv\Scripts\activate
```

**Mac/Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2: Set up environment variables

1. Duplicate `.env.example` in the project root.
2. Rename the copy to `.env`.
3. Fill in the required credentials (ask a team member for the actual values).

### Step 3: Install the required packages

```bash
pip install -r requirements.txt
```

### Step 4: Run migrations

```bash
cd backend
python manage.py migrate
```

### Step 5: Run the development server

```bash
python manage.py runserver
```

Visit **http://localhost:8000**.
