# Reddit User Persona Generator

This tool generates a detailed, structured persona for any Reddit user by analyzing their public posts and comments. Each persona includes citations for every characteristic, directly in the output file.

## Setup Instructions

### 1. (Recommended) Create and activate a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure your Reddit and Groq API credentials
Create a `.env` file in the project root with the following content:
```
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=your_user_agent
GROQ_API_KEY=your_groq_api_key
```
- [Create a Reddit app for credentials](https://www.reddit.com/prefs/apps)
- [Get a Groq API key](https://console.groq.com/)

### 4. Run the script for any Reddit user
```bash
python reddit_persona.py https://www.reddit.com/user/username/
```
- Replace `username` with the actual Reddit username you want to analyze.
- Use `--output` to specify a different output directory (default: `personas`).

### 5. Output
- The generated persona will be saved as `<username>_persona.txt` in the output directory.
- **Citations:** At the end of the persona file, a `## Citations` section lists the supporting post or comment (permalink) for each characteristic, or 'No evidence found' if not available.

---
