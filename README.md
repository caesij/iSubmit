# iSubmit
BSIT Capstone Project

## Setup Instructions (Development)

### Step 1: Create a virtual environment

#### Windows

```bash
py -m venv .venv
```

Activate the virtual environment:

```bash
.venv\Scripts\activate
```

### Step 2: Set up the environment variables

A `.env.example` file is included in the project root (backend folder) as a template.

1. Duplicate the `.env.example` file.
2. Rename the copy to `.env`.
3. Fill in the required environment variables with the appropriate credentials.

## Step 3: Install the required packages

```bash
pip install -r requirements.txt
```