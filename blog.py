import os
import datetime
import re
import requests
from pathlib import Path

# ===== AI imports =====
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# ===== Config =====
TEMPLATE_FILE = "blog/TEMPLATE.html"
BLOG_DIR = "blog"
INDEX_FILE = "blog/index.html"
TOPICS_FILE = "blog/topics.md"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

# OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
# Gemini client configuration
if GEMINI_API_KEY and genai:
    genai.configure(api_key=GEMINI_API_KEY)

# ===== Functions =====

def get_next_topic():
    """Read the first topic from topics.md"""
    with open(TOPICS_FILE, "r") as f:
        topics = [line.strip() for line in f if line.strip()]
    if not topics:
        return None
    return topics[0], topics[1:]  # first topic and remaining

def update_topics_file(remaining_topics):
    """Save remaining topics back to topics.md"""
    with open(TOPICS_FILE, "w") as f:
        for topic in remaining_topics:
            f.write(topic + "\n")

def generate_blog_with_gemini(prompt: str):
    """Fallback to Gemini AI"""
    try:
        client = genai.TextGenerationClient()
        response = client.generate(
            model="gemini-1.5-t",
            prompt=prompt,
            temperature=0.7,
            max_output_tokens=2000
        )
        return response.candidates[0].output
    except Exception as e:
        print("Gemini failed:", e)
        return None

def generate_blog_html(topic):
    """Try OpenAI first, fallback to Gemini"""
    prompt = f"""
Write a detailed technical blog in HTML format for the following topic:

Topic: {topic}

Follow TEMPLATE.html placeholders exactly:
{{TITLE}}: Blog title
{{DESCRIPTION}}: Short description/intro
{{CONTENT}}: Main HTML content (<h2>, <h3>, <p>, <ul>, <ol>, <code>, <pre> etc.)
{{TAGS}}: HTML span tags for tags
{{DATE}}: Today’s date in Month Day, Year format
{{READ_TIME}}: Approx. read time in minutes
{{CATEGORY}}: Blog category
{{TOC}}: Table of contents in <ul><li><a href="#section">Section</a></li></ul>
"""
    # Try OpenAI
    if client:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "You are a technical blog writer."},
                          {"role": "user", "content": prompt}],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print("OpenAI failed:", e)
            print("Falling back to Gemini...")

    # Fallback to Gemini
    if GEMINI_API_KEY and genai:
        gemini_result = generate_blog_with_gemini(prompt)
        if gemini_result:
            return gemini_result

    raise RuntimeError("No AI service available for blog generation.")

def send_to_slack(message_html):
    """Send draft to Slack"""
    payload = {
        "text": "Here is your blog draft:",
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message_html}
            }
        ]
    }
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)
    response.raise_for_status()

def save_blog_file(title, content_html):
    """Save the generated blog as HTML in blog folder"""
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    filename_slug = re.sub(r'[^a-z0-9]+', '-', title.lower())
    filename = f"{BLOG_DIR}/{date_str}-{filename_slug}.html"
    with open(filename, "w") as f:
        f.write(content_html)
    return filename

def update_index(title, filename):
    """Add new blog entry to index.html in the blog grid"""
    with open(INDEX_FILE, "r") as f:
        html = f.read()

    date_str = datetime.date.today().strftime("%b %d, %Y")
    read_time = "5 min read"  # optional; can parse from AI output
    post_html = f'''
<div class="blog-card rounded-xl p-6 border border-gray-800 card-hover">
    <div class="flex items-center mb-3">
        <span class="text-gray-400 text-sm">{date_str}</span>
    </div>
    <h3 class="text-xl font-bold text-primary mb-3">
        🚀 {title}
    </h3>
    <p class="text-gray-300 mb-4">
        Brief intro/summary of the article. (Update after approval if needed)
    </p>
    <div class="flex flex-wrap gap-2 mb-4">
        <span class="tag">Serverless</span>
        <span class="tag">Cloud</span>
    </div>
    <div class="flex items-center justify-between">
        <span class="text-gray-400 text-sm">📖 {read_time}</span>
        <a href="{Path(filename).name}" class="bg-primary text-white px-6 py-3 rounded-lg hover:bg-primary/80 transition-colors">
            Read Full Article →
        </a>
    </div>
</div>
'''

    html = html.replace("<!-- BLOG-ENTRIES -->", post_html + "\n<!-- BLOG-ENTRIES -->")
    with open(INDEX_FILE, "w") as f:
        f.write(html)

# ===== Main =====
if __name__ == "__main__":
    next_topic_info = get_next_topic()
    if not next_topic_info:
        print("No topics found in topics.md")
        exit(0)

    topic, remaining_topics = next_topic_info

    # 1. Generate draft HTML
    blog_html = generate_blog_html(topic)

    # 2. Send draft to Slack
    send_to_slack(blog_html)

    # 3. Save draft locally
    draft_file = save_blog_file(topic, blog_html)
    print(f"Draft saved to: {draft_file}")

    # 4. Update topics.md
    update_topics_file(remaining_topics)

    # 5. Update blog/index.html
    update_index(topic, draft_file)
