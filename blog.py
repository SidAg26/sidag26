import os
import datetime
import re
import requests
import json
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

# Debug API key configuration
print("🔑 API Key Configuration:")
print(f"   OpenAI: {'✅ Configured' if OPENAI_API_KEY else '❌ Not configured'}")
print(f"   Gemini: {'✅ Configured' if GEMINI_API_KEY else '❌ Not configured'}")
print(f"   Slack: {'✅ Configured' if SLACK_WEBHOOK_URL else '❌ Not configured'}")

# OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
# Gemini client configuration
if GEMINI_API_KEY and genai:
    genai.configure(api_key=GEMINI_API_KEY)
    print("✅ Gemini client configured successfully")
else:
    print("❌ Gemini client not configured (missing API key or library)")

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
        print("❌ Gemini AI library not imported.")
        return None
    
    if not GEMINI_API_KEY:
        print("❌ Gemini API key not configured.")
        return None

    try:
        print("🔑 Using Gemini API key:", GEMINI_API_KEY[:10] + "..." if GEMINI_API_KEY else "None")
        
        # Create a more concise prompt for Gemini to avoid truncation
        concise_prompt = f"""
Generate a blog post about: {prompt.split('Generate a blog post about: ')[1].split('\n')[0]}

Return ONLY a valid JSON object with this structure:
{{
    "title": "Blog Title",
    "description": "Short description",
    "sections": [
        {{
            "heading": "Introduction",
            "content": "1 paragraph about the topic",
            "code_examples": []
        }},
        {{
            "heading": "Core Concepts",
            "content": "1-2 paragraphs explaining main concepts",
            "code_examples": ["// Example code 1", "// Example code 2"]
        }},
        {{
            "heading": "Best Practices",
            "content": "1 paragraph with implementation guidance",
            "code_examples": ["// Best practice example"]
        }},
        {{
            "heading": "Conclusion",
            "content": "1 paragraph summarizing key points",
            "code_examples": []
        }}
    ],
    "tags": ["Serverless", "Cloud Computing"],
    "read_time": 5
}}

IMPORTANT: Return ONLY valid JSON, no other text. Keep content concise to avoid truncation.
"""
        
        model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
        response = model.generate_content(
            concise_prompt,
            generation_config=GenerationConfig(
                temperature=0.3,
                max_output_tokens=4000  # Increased token limit
            )
        )
        
        if response and response.parts:
            content = response.text
            print(f"✅ Gemini generated content: {len(content)} characters")
            return content
        else:
            finish_reason = None
            if hasattr(response, 'candidates') and response.candidates:
                first_candidate = response.candidates[0]
                if hasattr(first_candidate, 'finish_reason'):
                    finish_reason = first_candidate.finish_reason

            if finish_reason == 2:
                print("❌ Gemini generated no readable text content. Response was likely blocked due to safety concerns or content policy.")
            else:
                print(f"❌ Gemini generated no readable text content. Finish reason: {finish_reason}.")
            return None
    except Exception as e:
        print(f"❌ Gemini failed with error: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_structured_content(topic):
    """Generate structured content that's easier to format"""
    prompt = f"""
You are a technical blog writer. Generate a blog post about: {topic}

IMPORTANT: You must return ONLY a valid JSON object. No other text, no explanations, no markdown formatting.

Return this exact JSON structure:
{{
    "title": "Your Blog Title Here",
    "description": "A clear, concise description of what this blog post covers",
    "sections": [
        {{
            "heading": "Introduction",
            "content": "Your introduction content here. Write 2-3 paragraphs explaining the topic and why it matters.",
            "code_examples": []
        }},
        {{
            "heading": "Core Concepts",
            "content": "Explain the main concepts. Use clear examples and practical insights. Write 3-4 paragraphs.",
            "code_examples": ["// Example code snippet 1", "// Example code snippet 2"]
        }},
        {{
            "heading": "Implementation Details",
            "content": "Provide specific implementation guidance. Include best practices and common pitfalls. Write 3-4 paragraphs.",
            "code_examples": ["// Implementation example", "// Best practice code"]
        }},
        {{
            "heading": "Conclusion",
            "content": "Summarize key takeaways and suggest next steps. Write 1-2 paragraphs.",
            "code_examples": []
        }}
    ],
    "tags": ["Serverless", "Cloud Computing", "Performance"],
    "read_time": 8
}}

Requirements:
- Focus on cloud computing, serverless, or distributed systems
- Make content informative and engaging
- Include practical examples where relevant
- Target total content: 800-1500 words
- Return ONLY valid JSON, no other text
- Use technical but accessible language
- Ensure JSON is properly formatted with no syntax errors

Remember: Return ONLY the JSON object, nothing else.
"""
    
    blog_content = None

    # Try OpenAI
    if client:
        try:
            print("🔄 Attempting to generate structured content with OpenAI...")
            print(f"🔑 OpenAI API key configured: {'Yes' if OPENAI_API_KEY else 'No'}")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a technical blog writer. You must ALWAYS return ONLY valid JSON. Never include markdown, HTML, or any other formatting. Only return the JSON object."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3  # Lower temperature for more consistent output
            )
            blog_content = response.choices[0].message.content
            print("✅ OpenAI generation successful.")
        except Exception as e:
            print(f"❌ OpenAI failed: {e}")
            import traceback
            traceback.print_exc()
            print("🔄 Falling back to Gemini...")

    # Fallback to Gemini
    if not blog_content and GEMINI_API_KEY and genai:
        print("🔄 Attempting to generate structured content with Gemini...")
        blog_content = generate_blog_with_gemini(prompt)
        if blog_content:
            print("✅ Gemini generation successful.")
    
    if not blog_content:
        print("❌ Both AI services failed. Creating fallback content...")
        # Create a simple fallback blog post
        fallback_content = {
            "title": f"Understanding {topic}",
            "description": f"A comprehensive guide about {topic} and its importance in modern cloud computing.",
            "sections": [
                {
                    "heading": "Introduction",
                    "content": f"This blog post explores the fundamentals of {topic} and why it matters in today's cloud-native world. We'll dive deep into the concepts, implementation strategies, and best practices that can help you build better systems.",
                    "code_examples": []
                },
                {
                    "heading": "Core Concepts",
                    "content": f"To understand {topic}, we need to grasp several key concepts. This includes understanding the underlying principles, common patterns, and how it fits into the broader ecosystem of cloud computing and distributed systems.",
                    "code_examples": ["// Example: Basic implementation", "// Example: Configuration setup"]
                },
                {
                    "heading": "Implementation Details",
                    "content": f"Implementing {topic} requires careful consideration of several factors. We'll explore practical approaches, common pitfalls to avoid, and strategies for ensuring your implementation is robust and scalable.",
                    "code_examples": ["// Best practice implementation", "// Error handling example"]
                },
                {
                    "heading": "Conclusion",
                    "content": f"Understanding {topic} is crucial for building modern, scalable cloud applications. By following the principles and practices outlined in this post, you'll be better equipped to tackle the challenges of cloud-native development.",
                    "code_examples": []
                }
            ],
            "tags": ["Cloud Computing", "Research", "Best Practices"],
            "read_time": 5
        }
        
        print("✅ Generated fallback content structure")
        return build_html_from_structure(fallback_content)
    
    # Clean the response - remove any markdown formatting
    blog_content = blog_content.strip()
    if blog_content.startswith('```json'):
        blog_content = blog_content[7:]
    if blog_content.endswith('```'):
        blog_content = blog_content[:-3]
    blog_content = blog_content.strip()
    
    # Parse JSON and convert to HTML
    try:
        structured_data = json.loads(blog_content)
        return build_html_from_structure(structured_data)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse JSON: {e}")
        print("📄 Raw content:", blog_content)
        
        # Try to extract JSON from the response
        json_match = re.search(r'\{.*\}', blog_content, re.DOTALL)
        if json_match:
            try:
                extracted_json = json_match.group(0)
                # Try to fix common JSON issues
                fixed_json = fix_truncated_json(extracted_json)
                structured_data = json.loads(fixed_json)
                print("✅ Successfully parsed extracted and fixed JSON")
                return build_html_from_structure(structured_data)
            except json.JSONDecodeError as json_error:
                print(f"❌ Failed to parse extracted JSON: {json_error}")
        
        # Try to build content from partial JSON
        print("🔄 Attempting to build content from partial JSON...")
        partial_content = build_from_partial_json(blog_content, topic)
        if partial_content:
            return partial_content
        
        # Final fallback: treat as plain text
        print("⚠️ Using final fallback: plain text conversion")
        return f"<h2>Introduction</h2><p>Error: Could not parse structured content. Please check the AI generation.</p>"

def fix_truncated_json(json_string):
    """Attempt to fix common JSON truncation issues"""
    print("🔧 Attempting to fix truncated JSON...")
    
    # Remove trailing commas before closing braces/brackets
    json_string = re.sub(r',(\s*[}\]])', r'\1', json_string)
    
    # Try to close unclosed strings
    json_string = re.sub(r'([^"])\s*$', r'\1"', json_string)
    
    # Try to close unclosed objects/arrays
    open_braces = json_string.count('{') - json_string.count('}')
    open_brackets = json_string.count('[') - json_string.count(']')
    
    if open_braces > 0:
        json_string += '}' * open_braces
    if open_brackets > 0:
        json_string += ']' * open_brackets
    
    print(f"🔧 Fixed JSON: {len(json_string)} characters")
    return json_string

def build_from_partial_json(content, topic):
    """Build HTML content from partial or malformed JSON"""
    print("🔄 Building content from partial JSON...")
    
    try:
        # Try to extract what we can from the content
        title_match = re.search(r'"title":\s*"([^"]+)"', content)
        title = title_match.group(1) if title_match else f"Understanding {topic}"
        
        # Extract sections content
        sections_match = re.search(r'"sections":\s*\[(.*?)\]', content, re.DOTALL)
        if sections_match:
            sections_content = sections_match.group(1)
            # Try to extract individual sections
            section_matches = re.findall(r'\{[^{}]*"heading":\s*"([^"]+)"[^{}]*"content":\s*"([^"]*)"', sections_content, re.DOTALL)
            
            if section_matches:
                sections = []
                for heading, content_text in section_matches:
                    # Clean up content text
                    clean_content = content_text.replace('\\n', '\n').replace('\\"', '"')
                    sections.append({
                        "heading": heading,
                        "content": clean_content,
                        "code_examples": []
                    })
                
                # Create structured content
                structured_data = {
                    "title": title,
                    "description": f"A comprehensive guide about {topic}",
                    "sections": sections,
                    "tags": ["Cloud Computing", "Research"],
                    "read_time": 5
                }
                
                print(f"✅ Built content from {len(sections)} extracted sections")
                return build_html_from_structure(structured_data)
        
        # If we can't extract sections, try to get any content
        content_match = re.search(r'"content":\s*"([^"]*)"', content)
        if content_match:
            content_text = content_match.group(1).replace('\\n', '\n').replace('\\"', '"')
            fallback_content = {
                "title": title,
                "description": f"A comprehensive guide about {topic}",
                "sections": [
                    {
                        "heading": "Introduction",
                        "content": content_text,
                        "code_examples": []
                    }
                ],
                "tags": ["Cloud Computing", "Research"],
                "read_time": 3
            }
            
            print("✅ Built content from extracted content field")
            return build_html_from_structure(fallback_content)
            
    except Exception as e:
        print(f"❌ Error building from partial JSON: {e}")
    
    return None

def build_html_from_structure(structured_content):
    """Build HTML from structured content"""
    html_parts = []
    
    # Validate required fields
    if not isinstance(structured_content, dict):
        print("❌ Error: structured_content is not a dictionary")
        return "<h2>Error</h2><p>Invalid content structure</p>"
    
    # Get sections, default to empty list if missing
    sections = structured_content.get('sections', [])
    if not sections:
        print("❌ Warning: No sections found in structured content")
        return "<h2>Introduction</h2><p>Content structure is incomplete</p>"
    
    for i, section in enumerate(sections):
        if not isinstance(section, dict):
            print(f"❌ Warning: Section {i} is not a dictionary, skipping")
            continue
            
        heading = section.get('heading', f'Section {i+1}')
        content = section.get('content', 'Content not available')
        code_examples = section.get('code_examples', [])
        
        # Create heading with ID for TOC
        heading_id = re.sub(r'[^a-z0-9]+', '-', heading.lower()).strip('-')
        if not heading_id:
            heading_id = f'section-{i+1}'
        
        html_parts.append(f'<h2 id="{heading_id}">{heading}</h2>')
        
        # Process content - split into paragraphs if it contains newlines
        if '\n\n' in content:
            # Split by double newlines and create separate paragraphs
            paragraphs = content.split('\n\n')
            for para in paragraphs:
                para = para.strip()
                if para:  # Only add non-empty paragraphs
                    html_parts.append(f'<p>{para}</p>')
        else:
            # Single paragraph
            html_parts.append(f'<p>{content}</p>')
        
        # Add code examples if any
        if code_examples and isinstance(code_examples, list):
            for code in code_examples:
                if code and isinstance(code, str):
                    # Clean the code example
                    clean_code = code.strip()
                    if clean_code:
                        html_parts.append(f'<pre><code>{clean_code}</code></pre>')
    
    if not html_parts:
        return "<h2>Introduction</h2><p>No content could be generated from the structured data.</p>"
    
    return '\n'.join(html_parts)

def generate_test_blog(topic):
    """Generate a test blog post without requiring API keys"""
    print("🧪 Generating test blog post (no API keys required)...")
    
    test_content = {
        "title": f"Understanding {topic}: A Comprehensive Guide",
        "description": f"This blog post explores the fundamentals of {topic} and its importance in modern cloud computing and distributed systems.",
        "sections": [
            {
                "heading": "Introduction",
                "content": f"In today's rapidly evolving cloud computing landscape, understanding {topic} has become increasingly important for developers, architects, and DevOps engineers. This concept plays a crucial role in building scalable, reliable, and cost-effective systems that can handle the demands of modern applications.\n\nAs organizations continue to adopt cloud-native architectures, the principles behind {topic} provide a foundation for making informed decisions about system design, resource allocation, and performance optimization. Whether you're working with serverless functions, microservices, or traditional cloud infrastructure, grasping these concepts will help you build better systems.",
                "code_examples": []
            },
            {
                "heading": "Core Concepts and Fundamentals",
                "content": f"At its heart, {topic} revolves around several key principles that govern how systems behave and scale. The first concept to understand is the relationship between resource allocation and performance. When we talk about {topic}, we're essentially discussing how systems allocate and manage resources to meet varying demands.\n\nAnother fundamental aspect is the trade-off between efficiency and reliability. Systems that optimize for {topic} often need to balance these competing concerns, making architectural decisions that prioritize certain characteristics over others. This balancing act requires deep understanding of both the technical constraints and business requirements.",
                "code_examples": [
                    "// Example: Basic resource allocation\nconst allocateResources = (demand) => {\n  return Math.min(demand * 1.5, MAX_RESOURCES);\n};",
                    "// Example: Performance monitoring\nconst monitorPerformance = () => {\n  return {\n    latency: measureLatency(),\n    throughput: measureThroughput(),\n    resourceUtilization: getResourceUsage()\n  };\n};"
                ]
            },
            {
                "heading": "Implementation Strategies and Best Practices",
                "content": f"Implementing effective {topic} strategies requires a systematic approach that considers multiple factors. Start by establishing clear metrics and monitoring capabilities that will help you understand how your system is performing. This includes setting up logging, metrics collection, and alerting systems that can provide real-time insights into system behavior.\n\nNext, consider implementing gradual rollout strategies that allow you to test changes in production without affecting all users. This might involve feature flags, canary deployments, or A/B testing approaches that minimize risk while maximizing learning opportunities. Remember that successful {topic} implementation is often iterative, requiring continuous monitoring and adjustment based on real-world performance data.",
                "code_examples": [
                    "// Example: Feature flag implementation\nconst isFeatureEnabled = (featureName, userId) => {\n  const feature = getFeatureConfig(featureName);\n  return feature.enabled && \n         (feature.percentage === 100 || \n          hashUserId(userId) % 100 < feature.percentage);\n};",
                    "// Example: Canary deployment check\nconst shouldUseCanary = (request) => {\n  return request.headers['x-canary'] === 'true' || \n         Math.random() < CANARY_PERCENTAGE;\n};"
                ]
            },
            {
                "heading": "Conclusion and Future Considerations",
                "content": f"As we've explored throughout this post, understanding {topic} is fundamental to building modern, scalable cloud systems. The concepts and strategies we've discussed provide a solid foundation for making architectural decisions that balance performance, reliability, and cost-effectiveness.\n\nLooking forward, the landscape of {topic} will continue to evolve as new technologies and approaches emerge. Staying current with these developments, while maintaining focus on fundamental principles, will be key to building systems that can adapt to changing requirements and scale with your organization's growth.",
                "code_examples": []
            }
        ],
        "tags": ["Cloud Computing", "System Design", "Performance", "Best Practices"],
        "read_time": 8
    }
    
    print("✅ Test blog content generated successfully")
    return build_html_from_structure(test_content)

def generate_blog_html(topic):
    """Generate blog content using structured approach"""
    # Check if we have any API keys configured
    if not OPENAI_API_KEY and not GEMINI_API_KEY:
        print("⚠️ No API keys configured. Running in test mode...")
        return generate_test_blog(topic)
    
    return generate_structured_content(topic)

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

    with open(INDEX_FILE, "r", encoding='utf-8') as f:
        html = f.read()

    date_str = datetime.date.today().strftime("%b %d, %Y")
    read_time = "5 min read"  # This can be parsed from AI output if {{READ_TIME}} is filled
    
    # Create the new blog card HTML
    post_html = f'''
<div class="blog-card rounded-xl p-6 border border-gray-800 card-hover">
    <div class="flex items-center mb-3">
        <span class="text-gray-400 text-sm">{date_str}</span>
    </div>
    <h3 class="text-xl font-bold text-primary mb-3">
        🚀 {title}
    </h3>
    <p class="text-gray-300 mb-4">
        A comprehensive guide about {title.lower()}. Click to read the full article.
    </p>
    <div class="flex flex-wrap gap-2 mb-4">
        <span class="tag">Serverless</span>
        <span class="tag">Cloud Computing</span>
        <span class="tag">Research</span>
    </div>
    <div class="flex items-center justify-between">
        <span class="text-gray-400 text-sm">📖 {read_time}</span>
        <a href="{Path(filename).name}" class="bg-primary text-white px-6 py-3 rounded-lg hover:bg-primary/80 transition-colors">
            Read Full Article →
        </a>
    </div>
</div>'''

    # Check if the placeholder exists
    if "<!-- BLOG-ENTRIES -->" in html:
        # Replace the placeholder with new post + placeholder
        html = html.replace("<!-- BLOG-ENTRIES -->", post_html + "\n<!-- BLOG-ENTRIES -->")
        
        # Write the updated HTML back to the file
        with open(INDEX_FILE, "w", encoding='utf-8') as f:
            f.write(html)
        
        print(f"✅ Updated {INDEX_FILE} with new blog entry: {title}")
        print(f"📝 Blog post added to index: {filename}")
    else:
        print(f"❌ Warning: '<!-- BLOG-ENTRIES -->' placeholder not found in {INDEX_FILE}")
        print("🔍 Looking for alternative insertion points...")
        
        # Try to find a good place to insert (before the "Coming Soon" card)
        if "Coming Soon" in html:
            # Insert before the "Coming Soon" card
            html = html.replace(
                '<div class="blog-card rounded-xl p-6 border border-gray-800 card-hover">',
                post_html + '\n\n<div class="blog-card rounded-xl p-6 border border-gray-800 card-hover">',
                1  # Only replace the first occurrence (the "Coming Soon" card)
            )
            
            with open(INDEX_FILE, "w", encoding='utf-8') as f:
                f.write(html)
            
            print(f"✅ Updated {INDEX_FILE} by inserting before 'Coming Soon' card")
        else:
            print(f"❌ Could not find suitable insertion point in {INDEX_FILE}")
            print("📋 New blog post HTML (copy manually if needed):")
            print(post_html)

# ===== Main =====
if __name__ == "__main__":
    print("🚀 Starting blog generation process...")
    
    next_topic_info = get_next_topic()
    if not next_topic_info:
        print("❌ Exiting: No topics found or topics.md is missing.")
        exit(0)

    topic, remaining_topics = next_topic_info
    print(f"📝 Generating blog for topic: '{topic}'")

    try:
        # 1. Generate draft HTML
        print("🔄 Step 1: Generating structured content...")
        blog_html = generate_blog_html(topic)
        
        if not blog_html:
            print("❌ Error: No blog content generated")
            exit(1)
        
        print(f"✅ Content generated successfully. Length: {len(blog_html)} characters")
        print("📄 Preview of generated content:")
        print("-" * 50)
        print(blog_html[:200] + "..." if len(blog_html) > 200 else blog_html)
        print("-" * 50)

        # 2. Send draft to Slack
        print("\n🔄 Step 2: Sending draft to Slack...")
        if blog_html:
            send_to_slack(blog_html)
        else:
            print("⚠️ Skipping Slack notification as no blog content was generated.")

        # 3. Save draft locally
        print("\n🔄 Step 3: Saving draft locally...")
        if blog_html:
            draft_file = save_blog_file(topic, blog_html)
            print(f"✅ Draft saved to: {draft_file}")
            
            # 4. Update topics.md
            print("\n🔄 Step 4: Updating topics file...")
            update_topics_file(remaining_topics)
            print("✅ Topics file updated")
            
            # 5. Update blog/index.html
            print("\n🔄 Step 5: Updating blog index...")
            update_index(topic, draft_file)
            print("✅ Blog index updated")
            
            print(f"\n🎉 Blog generation complete! New post: {draft_file}")
        else:
            print("❌ Skipping local save and index update as no blog content was generated.")

    except RuntimeError as e:
        print(f"❌ Critical error during blog generation: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        exit(1)