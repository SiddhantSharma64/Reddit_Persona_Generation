import argparse
import os
import json
import asyncio
import asyncpraw
from dotenv import load_dotenv
import aiohttp
import re

def parse_arguments():
    parser = argparse.ArgumentParser(description="Generate a Reddit user persona from a profile URL.")
    parser.add_argument("profile_url", type=str, nargs="?", help="Reddit user profile URL (e.g. https://www.reddit.com/user/username/)")
    parser.add_argument("--output", type=str, default="personas", help="Output directory for persona files")
    return parser.parse_args()

def create_reddit_client():
    load_dotenv()
    return asyncpraw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT")
    )

async def fetch_user_activity(profile_url):
    reddit = create_reddit_client()
    username = profile_url.rstrip('/').split('/')[-1]
    user = await reddit.redditor(username)
    posts, comments = [], []
    async for submission in user.submissions.new(limit=100):
        posts.append({
            "id": submission.id,
            "title": submission.title,
            "selftext": submission.selftext,
            "subreddit": str(submission.subreddit),
            "url": submission.url,
            "created_utc": submission.created_utc,
            "permalink": f"https://www.reddit.com{submission.permalink}"
        })
    async for comment in user.comments.new(limit=100):
        comments.append({
            "id": comment.id,
            "body": comment.body,
            "subreddit": str(comment.subreddit),
            "link_title": getattr(comment.submission, 'title', ''),
            "created_utc": comment.created_utc,
            "permalink": f"https://www.reddit.com{comment.permalink}"
        })
    await reddit.close()
    return {"posts": posts, "comments": comments}

async def generate_persona_summary(user_data):
    load_dotenv()
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY not set in .env file.")
    prompt = (
        "You are an expert in user research and persona creation. "
        "Given the following Reddit posts and comments, generate a comprehensive, professional, and nuanced user persona. "
        "For each characteristic, cite the specific post or comment (by permalink) that supports it. If no evidence is found, state 'No evidence found'. "
        "The persona should be detailed and insightful, capturing not only basic demographics but also motivations, personality traits, behavioral patterns, frustrations, goals, interests, values, writing style, and online behavior. "
        "Use clear, structured formatting: each section should have a header (e.g., '## Motivations'), and details should be presented as bullet points, each with a supporting permalink in parentheses. Do not include any reasoning, instructions, or explanations—output only the persona content.\n\n"
        "---\n"
        "# Reddit User Persona\n"
        "## Name\n- (Reddit Username) (permalink)\n"
        "## Age\n- (if available, else 'Unknown') (permalink)\n"
        "## Occupation\n- (if available, else 'Unknown') (permalink)\n"
        "## Location\n- (if available, else 'Unknown') (permalink)\n"
        "## Motivations\n- (detailed, with citation)\n"
        "## Personality Traits\n- (detailed, with citation)\n"
        "## Behavioral Patterns\n- (detailed, with citation)\n"
        "## Frustrations\n- (detailed, with citation)\n"
        "## Goals & Needs\n- (detailed, with citation)\n"
        "## Interests\n- (detailed, with citation)\n"
        "## Values\n- (detailed, with citation)\n"
        "## Writing Style\n- (detailed, with citation)\n"
        "## Online Behavior\n- (detailed, with citation)\n"
        "---\n\n"
        f"POSTS: {json.dumps(user_data['posts'][:10], indent=2)}\n\nCOMMENTS: {json.dumps(user_data['comments'][:10], indent=2)}\n\n"
        "Output the persona in the above format. For each bullet point, include the supporting permalink in parentheses immediately after the trait. "
        "Ensure the output is easy to parse for extracting each trait and its citation."
    )
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 2048,
        "temperature": 0.7
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(f"Groq API error: {response.status} {text}")
            result = await response.json()
            persona_text = result["choices"][0]["message"]["content"]
    citations = extract_citations_from_persona(persona_text)
    return persona_text, citations

def extract_citations_from_persona(persona_text):
    characteristics = [
        "Name", "Age", "Occupation", "Location",
        "Motivations", "Personality Traits", "Behavioral Patterns", "Frustrations", "Goals & Needs",
        "Interests", "Values", "Writing Style", "Online Behavior"
    ]
    citations = {}
    for char in characteristics:
        # Find the section header
        section_pattern = rf"## {re.escape(char)}\n((?:- .+\n)+)"
        section_match = re.search(section_pattern, persona_text)
        permalinks = []
        if section_match:
            bullets = section_match.group(1).strip().split('\n')
            for bullet in bullets:
                link_match = re.search(r'\((https?://[^)]+)\)', bullet)
                if link_match:
                    permalinks.append(link_match.group(1))
        if permalinks:
            citations[char] = permalinks if len(permalinks) > 1 else permalinks[0]
        else:
            citations[char] = 'No evidence found'
    return citations

def format_persona_text(persona):
    persona = re.sub(r'(?<!^)\*+', '', persona)
    persona = re.sub(r'(?m)(^[^\n]+:)$', r'\1\n', persona)
    persona = re.sub(r'(?m)([^\n])\n([^\n]+:)', r'\1\n\n\2', persona)
    persona = re.sub(r'(^\* .+)', r'\1\n', persona, flags=re.MULTILINE)
    persona = re.sub(r'\n{3,}', '\n\n', persona)
    return persona.strip() + '\n'

def save_persona_to_file(persona, output_dir, username, citations=None):
    persona_lines = persona.splitlines()
    start_idx = 0
    for i, line in enumerate(persona_lines):
        if line.strip().startswith("Name:") or line.strip().startswith("# Reddit User Persona"):
            start_idx = i
            break
    persona_main = "\n".join(persona_lines[start_idx:])
    end_idx = len(persona_main)
    for char in ["Online Behavior:", "Online Behavior"]:
        last_idx = persona_main.rfind(char)
        if last_idx != -1:
            end_of_line = persona_main.find("\n", last_idx)
            if end_of_line != -1:
                end_idx = end_of_line
            else:
                end_idx = len(persona_main)
            break
    persona_main = persona_main[:end_idx].strip()
    persona_no_links = re.sub(r'https?://\S+', '', persona_main)
    persona_no_links = re.sub(r'\(\s*\)', '', persona_no_links)
    persona_no_links = re.sub(r'\[\s*\]', '', persona_no_links)
    persona_no_links = re.sub(r'\(\s*\)$', '', persona_no_links, flags=re.MULTILINE)
    persona_no_links = re.sub(r'(:|\*|-)\s*\($', r'\1', persona_no_links, flags=re.MULTILINE)
    persona_no_links = re.sub(r'\(\s*$', '', persona_no_links, flags=re.MULTILINE)
    persona_pretty = format_persona_text(persona_no_links)
    # Append citations section if available
    if citations is not None:
        citations_section = ['\n## Citations']
        for k, v in citations.items():
            citations_section.append(f"- {k}: {v if v else 'No evidence found'}")
        persona_pretty += "\n" + "\n".join(citations_section)
    persona_path = os.path.join(output_dir, f"{username}_persona.txt")
    with open(persona_path, "w", encoding="utf-8") as f:
        f.write(persona_pretty)
    print(f"Persona saved to {persona_path}")

def extract_reddit_username(profile_url):
    match = re.search(r"/user/([A-Za-z0-9_\-]+)/?", profile_url)
    return match.group(1) if match else None

async def main():
    args = parse_arguments()
    os.makedirs(args.output, exist_ok=True)
    if not args.profile_url:
        print("Error: You must provide a Reddit user profile URL as an argument.")
        return
    if "/user/" not in args.profile_url:
        print(f"Error: The provided URL is not a Reddit user profile URL: {args.profile_url}")
        return
    username = extract_reddit_username(args.profile_url)
    if not username:
        print(f"Error: Could not extract username from URL: {args.profile_url}")
        return
    print(f"Processing user: {username}")
    profile_url = f"https://www.reddit.com/user/{username}/"
    try:
        user_data = await fetch_user_activity(profile_url)
        if not user_data["posts"] and not user_data["comments"]:
            print(f"Warning: No posts or comments found for user {username}. Skipping persona generation.")
            return
        persona, citations = await generate_persona_summary(user_data)
        save_persona_to_file(persona, args.output, username, citations)
        print(f"Persona for {username} saved in {args.output}/\n")
    except Exception as e:
        print(f"Error processing user {username}: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 