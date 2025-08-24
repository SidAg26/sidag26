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
    if not Path(TOPICS_FILE).exists():
        print(f"Error: {TOPICS_FILE} not found.")
        return None

    with open(TOPICS_FILE, "r") as f:
        topics = [line.strip() for line in f if line.strip()]
    if not topics:
        return None
    
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
        model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
        response = model.generate_content(
            prompt,
            generation_config=GenerationConfig(
                temperature=0.7,
                max_output_tokens=2000
            )
        )
        
        if response and response.parts:
            return response.text
        else:
            finish_reason = None
            if hasattr(response, 'candidates') and response.candidates:
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
Write a detailed technical blog post about: {topic}

Requirements:
- Use proper HTML structure with <h2>, <h3>, <p>, <ul>, <ol>, <code>, <pre>
- Include practical examples and code snippets
- Make it informative and engaging
- Target length: 800-1500 words
- Focus on cloud computing, serverless, or distributed systems
- Do NOT include <h1> tags (title is handled separately)
- Do NOT include <html>, <head>, or <body> tags

Format the content with proper HTML tags but keep it as content only.
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
        except Exception as e:
            print(f"OpenAI failed: {e}")
            print("Falling back to Gemini...")

    # Fallback to Gemini
    if not blog_content and GEMINI_API_KEY and genai:
        print("Attempting to generate blog with Gemini...")
        blog_content = generate_blog_with_gemini(prompt)
        if blog_content:
            print("Gemini generation successful.")
    
    if not blog_content:
        raise RuntimeError("No AI service available for blog generation.")
    
    # Format the content using your template
    return format_blog_with_template(topic, blog_content)

def format_blog_with_template(topic, content_html):
    """Format the AI-generated content using TEMPLATE.html"""
    
    # Read the template file
    template_path = Path(TEMPLATE_FILE)
    if not template_path.exists():
        print(f"Warning: {TEMPLATE_FILE} not found. Using raw content.")
        return content_html
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()
    
    # Extract key information from the AI content
    # Extract title (look for first <h2> or use topic)
    title_match = re.search(r'<h2[^>]*>(.*?)</h2>', content_html, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else topic
    
    # Extract description (first paragraph)
    desc_match = re.search(r'<p[^>]*>(.*?)</p>', content_html, re.IGNORECASE)
    description = desc_match.group(1).strip() if desc_match else f"Comprehensive guide about {topic}"
    
    # Clean description (remove HTML tags)
    description = re.sub(r'<[^>]+>', '', description)
    
    # Generate tags based on topic
    tags = generate_tags_from_topic(topic)
    
    # Get current date and time
    current_date = datetime.datetime.now().strftime("%B %d, %Y")
    
    # Estimate read time (rough calculation: 200 words per minute)
    word_count = len(content_html.split())
    read_time = max(1, round(word_count / 200))
    
    # Generate table of contents from headings
    toc = generate_table_of_contents(content_html)
    
    # Replace template placeholders (using double curly braces as in your template)
    formatted_content = template.replace('{{TITLE}}', title)
    formatted_content = formatted_content.replace('{{DESCRIPTION}}', description)
    formatted_content = formatted_content.replace('{{CONTENT}}', content_html)
    formatted_content = formatted_content.replace('{{TAGS}}', tags)
    formatted_content = formatted_content.replace('{{DATE}}', current_date)
    formatted_content = formatted_content.replace('{{READ_TIME}}', str(read_time))
    formatted_content = formatted_content.replace('{{CATEGORY}}', 'Research')
    formatted_content = formatted_content.replace('{{TOC}}', toc)
    
    return formatted_content

def generate_tags_from_topic(topic):
    """Generate relevant tags based on the topic"""
    topic_lower = topic.lower()
    tags = []
    
    # Define tag mappings
    tag_mappings = {
        'serverless': 'Serverless',
        'cloud': 'Cloud Computing',
        'aws': 'AWS',
        'lambda': 'AWS Lambda',
        'performance': 'Performance',
        'optimization': 'Optimization',
        'scaling': 'Scaling',
        'architecture': 'Architecture',
        'distributed': 'Distributed Systems',
        'research': 'Research',
        'function': 'Functions',
        'cold': 'Cold Start',
        'start': 'Cold Start',
        'autoscaling': 'Auto-scaling',
        'faas': 'FaaS'
    }
    
    for keyword, tag in tag_mappings.items():
        if keyword in topic_lower:
            tags.append(f'<span class="tag">{tag}</span>')
    
    # Add default tags if none found
    if not tags:
        tags = [
            '<span class="tag">Cloud Computing</span>',
            '<span class="tag">Research</span>'
        ]
    
    return ' '.join(tags)

def generate_table_of_contents(content):
    """Generate table of contents from HTML content"""
    # Find all headings (h2, h3)
    headings = re.findall(r'<h([23])[^>]*>(.*?)</h[23]>', content, re.IGNORECASE)
    
    if not headings:
        return '<ul><li><a href="#introduction">Introduction</a></li></ul>'
    
    toc_items = []
    for level, heading_text in headings:
        # Create anchor ID
        anchor = re.sub(r'[^a-z0-9]+', '-', heading_text.lower()).strip('-')
        
        # Clean heading text (remove HTML tags)
        clean_text = re.sub(r'<[^>]+>', '', heading_text)
        
        # Add to TOC
        toc_items.append(f'<li><a href="#{anchor}">{clean_text}</a></li>')
    
    return f'<ul>{"".join(toc_items)}</ul>'

def send_to_slack(message_html):
    """Send draft to Slack."""
    if not SLACK_WEBHOOK_URL:
        print("Slack Webhook URL not configured. Skipping Slack notification.")
        return

    # Convert HTML to plain text for Slack
    import re
    
    def html_to_text(html_content):
        """Convert HTML to readable plain text"""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html_content)
        # Decode HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        # Limit length to avoid Slack limits
        if len(text) > 2000:
            text = text[:1997] + "..."
        return text
    
    # Convert HTML to plain text
    plain_text = html_to_text(message_html)
    
    # Create a better Slack message structure
    payload = {
        "text": "📝 New Blog Draft Generated!",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚀 New Blog Post Draft"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Topic:* {plain_text[:100]}..."
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Preview:* {plain_text[:500]}..."
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Check your local files for the complete draft"
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print("Blog draft sent to Slack successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send blog draft to Slack: {e}")
        # Try a simpler fallback message
        try:
            simple_payload = {
                "text": f"📝 Blog draft generated for topic: {plain_text[:100]}...",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*New Blog Draft:* {plain_text[:200]}..."
                        }
                    }
                ]
            }
            response = requests.post(SLACK_WEBHOOK_URL, json=simple_payload)
            response.raise_for_status()
            print("Fallback Slack message sent successfully.")
        except Exception as fallback_error:
            print(f"Fallback Slack message also failed: {fallback_error}")

def save_blog_file(title, content_html):
    """Save the generated blog as HTML in blog folder and commit to git."""
    # Ensure BLOG_DIR exists
    Path(BLOG_DIR).mkdir(parents=True, exist_ok=True)

    date_str = datetime.date.today().strftime("%Y-%m-%d")
    # Clean title for filename slug
    filename_slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    if not filename_slug: # Fallback if title becomes empty after sanitization
        filename_slug = "untitled-blog-post"
    filename = f"{BLOG_DIR}/{date_str}-{filename_slug}.html"
    
    # Save the file locally
    with open(filename, "w", encoding='utf-8') as f:
        f.write(content_html)
    
    # Commit and push to git
    try:
        import subprocess
        
        # Configure git for the workflow
        subprocess.run(["git", "config", "--global", "user.name", "GitHub Actions"], check=True)
        subprocess.run(["git", "config", "--global", "user.email", "actions@github.com"], check=True)
        
        # Add the new file
        subprocess.run(["git", "add", filename], check=True)
        
        # Commit the changes
        commit_message = f"Add blog post: {title}"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        
        # Push to the current branch
        subprocess.run(["git", "push"], check=True)
        
        print(f"Blog post committed and pushed to git: {filename}")
        
    except subprocess.CalledProcessError as e:
        print(f"Git operations failed: {e}")
        print("Blog file saved locally but not committed to git")
    except Exception as e:
        print(f"Unexpected error during git operations: {e}")
        print("Blog file saved locally but not committed to git")
    
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
        �� {title}
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