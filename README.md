## Description

**The Healthy Plate Quest** is a gamified web application developed as the primary artefact of my Bachelor's thesis. It targets university students as its primary user group and aims to promote healthy eating awareness and engagement through gamification, behavioral science and AI coaching. 

The entire project spans 7 phases, from initial project setup and database design through to frontend polish, integrating behavioral science and user evaluation interface in the process. It is built using entirely free-tier APIs, with the AI coach powered by Meta's Llama 3.3 70B model via the Groq API.

## Environment setup

### 1. Clone the repository

```bash
git clone https://github.com/NguyenDK2247/The-Healthy-Plate-Quest.git
cd The-Healthy-Plate-Quest
```

### 2. Create and activate a virtual environment

```bash
# Windows (Command Prompt - recommended over PowerShell)
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

> **Note (Windows):** If you have multiple Python installations (e.g. Anaconda alongside a standalone Python), use the full path to a specific Python when creating the venv to avoid conflicts:
> ```cmd
> C:\Python313\python.exe -m venv venv
> ```
> Run `where python` to see which installations you have, or `py -0` to list all available versions.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** The AI coach uses the `openai` Python package as an HTTP client to communicate with Groq's API. This is expected - no OpenAI account or API key is required.

### 4. Configure environment variables

Create a `.env` file in the project root:

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Your `.env` should contain:

```
SECRET_KEY=your-secret-key-here
GROQ_API_KEY=your-groq-api-key-here
```

> **Note:** Never commit your `.env` file. It is already listed in `.gitignore`.

- Generate a strong `SECRET_KEY` with: `python -c "import secrets; print(secrets.token_hex(32))"`
- Get a `GROQ_API_KEY` from [console.groq.com](https://console.groq.com)

### 5. Initialize the database

The recommended terminal is **Command Prompt** (not PowerShell) on Windows.

```bash
# Windows
set FLASK_APP=run.py
flask init-db

# macOS / Linux
export FLASK_APP=run.py
flask init-db
```

This creates all database tables and seeds the default quests and badges.

### 6. Run the application

```bash
python run.py
```

The app will be available at `http://127.0.0.1:5000`. To stop it, press `Ctrl+C`.

### User evaluation & survey

- Navigate to `/eval/survey/` to take the usability survey.
- Navigate to `/eval/results` to view survey results.
