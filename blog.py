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
    # Import types for better type hinting and configuration
    from google.generativeai.types import GenerationConfig
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
    # Ensure the directory for topics.md exists or handle its absence gracefully
    if not Path(TOPICS_FILE).exists():
        print(f"Error: {TOPICS_FILE} not found.")
        return None

    with open(TOPICS_FILE, "r") as f:
        topics = [line.strip() for line in f if line.strip()]
    if not topics:
        return None
    
    # Return the first topic and the rest
    return topics[0], topics[1:]

def update_topics_file(remaining_topics):
    """Save remaining topics back to topics.md"""
    with open(TOPICS_FILE, "w") as f:
        for topic in remaining_topics:
            f.write(topic + "\n")

def generate_blog_with_gemini(prompt: str):
    """Fallback to Gemini AI to generate blog content."""
    if not genai:
        print("Gemini AI library not imported.")
        return None
    
    if not GEMINI_API_KEY:
        print("Gemini API key not configured.")
        return None

    try:
        # Using 'gemini-2.5-flash-preview-05-20' for text generation as 'gemini-pro' might not be available for generateContent in v1beta
        model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
        response = model.generate_content(
            prompt,
            generation_config=GenerationConfig( # Use imported GenerationConfig
                temperature=0.7,
                max_output_tokens=2000
            )
        )
        
        # Access the generated text directly from the response object
        # Check if any parts are present before accessing .text
        if response and response.parts: # Check if response.parts exist
            print(response.text)
            return response.text
        else:
            # If no parts, check for finish_reason for more specific feedback
            finish_reason = None
            if hasattr(response, 'candidates') and response.candidates:
                # Assuming the first candidate for finish_reason
                first_candidate = response.candidates[0]
                if hasattr(first_candidate, 'finish_reason'):
                    finish_reason = first_candidate.finish_reason

            if finish_reason == 2:
                print("Gemini generated no readable text content. Response was likely blocked due to safety concerns or content policy.")
            else:
                print(f"Gemini generated no readable text content. Finish reason: {finish_reason}.")
            return None
    except Exception as e:
        print(f"Gemini failed: {e}")
        return None

def generate_blog_html(topic):
    """Try OpenAI first, fallback to Gemini."""
    prompt = f"""
Write a detailed, informative, and purely technical blog in HTML format for the following topic:

Topic: {topic}

Focus solely on explaining concepts, best practices, and practical implementation details. Avoid any content that could be interpreted as controversial, harmful, or speculative beyond the technical scope.

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
    blog_content = None

    # Try OpenAI
    if client:
        try:
            print("Attempting to generate blog with OpenAI...")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "You are a technical blog writer."},
                          {"role": "user", "content": prompt}],
                temperature=0.7
            )
            blog_content = response.choices[0].message.content
            print("OpenAI generation successful.")
            return blog_content
        except Exception as e:
            print(f"OpenAI failed: {e}")
            print("Falling back to Gemini...")

    # Fallback to Gemini
    if GEMINI_API_KEY and genai:
        print("Attempting to generate blog with Gemini...")
        gemini_result = generate_blog_with_gemini(prompt)
        if gemini_result:
            print("Gemini generation successful.")
            return gemini_result
        else:
            print("Gemini fallback also failed to generate content.")
    else:
        print("Gemini API key or library not available for fallback.")

    raise RuntimeError("No AI service available for blog generation.")

def send_to_slack(message_html):
    """Send draft to Slack."""
    if not SLACK_WEBHOOK_URL:
        print("Slack Webhook URL not configured. Skipping Slack notification.")
        return

    payload = {
        "text": "Here is your blog draft:",
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message_html}
            }
        ]
    }
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print("Blog draft sent to Slack.")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send blog draft to Slack: {e}")

def save_blog_file(title, content_html):
    """Save the generated blog as HTML in blog folder."""
    # Ensure BLOG_DIR exists
    Path(BLOG_DIR).mkdir(parents=True, exist_ok=True)

    date_str = datetime.date.today().strftime("%Y-%m-%d")
    # Clean title for filename slug
    filename_slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    if not filename_slug: # Fallback if title becomes empty after sanitization
        filename_slug = "untitled-blog-post"
    filename = f"{BLOG_DIR}/{date_str}-{filename_slug}.html"
    
    with open(filename, "w") as f:
        f.write(content_html)
    return filename

def update_index(title, filename):
    """Add new blog entry to index.html in the blog grid."""
    if not Path(INDEX_FILE).exists():
        print(f"Error: {INDEX_FILE} not found. Cannot update index.")
        return

    with open(INDEX_FILE, "r") as f:
        html = f.read()

    date_str = datetime.date.today().strftime("%b %d, %Y")
    read_time = "5 min read"  # This can be parsed from AI output if {{READ_TIME}} is filled
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

    # Ensure the placeholder exists before attempting to replace
    if "<!-- BLOG-ENTRIES -->" in html:
        html = html.replace("<!-- BLOG-ENTRIES -->", post_html + "\n<!-- BLOG-ENTRIES -->")
        with open(INDEX_FILE, "w") as f:
            f.write(html)
        print(f"Updated {INDEX_FILE} with new blog entry.")
    else:
        print(f"Warning: '<!-- BLOG-ENTRIES -->' placeholder not found in {INDEX_FILE}. Index not updated.")


# ===== Main =====
if __name__ == "__main__":
    next_topic_info = get_next_topic()
    if not next_topic_info:
        print("Exiting: No topics found or topics.md is missing.")
        exit(0)

    topic, remaining_topics = next_topic_info
    print(f"Generating blog for topic: '{topic}'")

    try:
        # 1. Generate draft HTML
        blog_html = generate_blog_html(topic)

        # 2. Send draft to Slack (this will only work if blog_html is not None)
        if blog_html:
            send_to_slack(blog_html)
        else:
            print("Skipping Slack notification as no blog content was generated.")

        # 3. Save draft locally (this will only work if blog_html is not None)
        if blog_html:
            draft_file = save_blog_file(topic, blog_html)
            print(f"Draft saved to: {draft_file}")
            # 4. Update topics.md
            update_topics_file(remaining_topics)
            # 5. Update blog/index.html
            update_index(topic, draft_file)
        else:
            print("Skipping local save and index update as no blog content was generated.")

    except RuntimeError as e:
        print(f"Critical error during blog generation: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

