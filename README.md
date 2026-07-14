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
# Windows (Command Prompt — recommended over PowerShell)
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example file and fill in your values:

```bash
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

```bash
flask init-db
```

### 6. Run the application

The recommended terminal is the **command prompt**. Execute this command to run the program:

```bash
python run.py
```

The app will be available at `http://127.0.0.1:5000`. To stop it, press `Ctrl+C`.

### User evaluation & survey

- Navigate to `/eval/survey/` to take the usability survey.
- Navigate to `/eval/results` to view survey results.
