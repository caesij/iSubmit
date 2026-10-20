# iSubmit

BSIT Capstone Project

This guide will help you run the iSubmit website on your computer using Docker. You don't need to install Python or set up a virtual environment, since Docker handles everything.

---

## Setup (first time only)

### Step 1: Install Docker

**Windows / macOS**

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/).

**Linux**

Install Docker Engine using the [official Docker installation guide](https://docs.docker.com/engine/install/).

---

### Step 2: Clone the Repository

```bash
git clone <REPOSITORY_URL>
cd iSubmit
```

You can also use GitHub Desktop to clone the repository.

---

### Step 3: Set Up Environment Variables

1. Copy `.env.example`.
2. Rename the copy to `.env`.
3. Fill in the required values.

```text
.env.example → .env
```

Ask teammates for the required environment variable values.

> Do not commit `.env` to Git.

---

### Step 4: Start the Website

From the **project root** (the folder with `docker-compose.yml`), run:

```bash
docker compose up -d --build
```

The first run can take a few minutes because Docker has to download and build everything. Later runs are much faster.

---

### Step 5: Set Up the Database (first time only)

Once the containers are running, run:

```bash
docker compose exec web python manage.py migrate
```

---

### Step 6: Open the Website

Go to:

**http://127.0.0.1:8000**

---

## Regular Usage

**Start the website**

```bash
docker compose up -d
```

Then open **http://127.0.0.1:8000**.

**Stop the website**

```bash
docker compose stop
```

---

## Getting the Latest Changes

Whenever a teammate pushes updates, follow these steps.

**1. Pull the latest code**

```bash
git pull
```

You can also use GitHub Desktop and click **Pull origin**.

**2. Rebuild and restart the website**

```bash
docker compose up -d --build
```

**3. Update the database (if needed)**

If the update includes database changes, run this after the website has started:

```bash
docker compose exec web python manage.py migrate
```


> Run the migrate command **after** rebuilding. The running container needs the new code before it can see the new migrations.