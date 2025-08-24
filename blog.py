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
        
        # Create a more comprehensive prompt for Gemini to generate detailed content
        comprehensive_prompt = f"""
Generate a comprehensive, detailed blog post about: {topic}

Return ONLY a valid JSON object with this structure:
{{
    "title": "Detailed Blog Title",
    "description": "Comprehensive description of what this blog post covers",
    "sections": [
        {{
            "heading": "Introduction",
            "content": "Write 3-4 detailed paragraphs introducing the topic, explaining its importance, and setting the context for readers. Make this engaging and informative.",
            "code_examples": ["const allocateResources = (demand) => {{ return Math.min(demand * 1.5, MAX_RESOURCES); }};", "const monitorPerformance = () => {{ return {{ latency: measureLatency(), throughput: measureThroughput() }}; }};"]
        }},
        {{
            "heading": "Core Concepts and Fundamentals",
            "content": "Write 4-5 detailed paragraphs explaining the fundamental concepts, principles, and underlying mechanisms. Break down complex ideas into digestible parts with clear explanations.",
            "code_examples": ["const allocateResources = (demand) => {{ return Math.min(demand * 1.5, MAX_RESOURCES); }};", "const monitorPerformance = () => {{ return {{ latency: measureLatency(), throughput: measureThroughput() }}; }};"]
        }},
        {{
            "heading": "Implementation Strategies and Best Practices",
            "content": "Write 4-5 detailed paragraphs covering practical implementation approaches, common patterns, best practices, and real-world considerations. Include specific guidance and actionable advice.",
            "code_examples": ["const isFeatureEnabled = (featureName, userId) => {{ const feature = getFeatureConfig(featureName); return feature.enabled && hashUserId(userId) % 100 < feature.rolloutPercentage; }};", "const handleOperation = async (op) => {{ try {{ const result = await op(); logSuccess(op.name, result); return result; }} catch (error) {{ logError(op.name, error); throw error; }} }};"]
        }},
        {{
            "heading": "Advanced Techniques and Optimization",
            "content": "Write 3-4 detailed paragraphs covering advanced techniques, performance optimization strategies, scalability considerations, and cutting-edge approaches in this field.",
            "code_examples": ["const predictScaling = (data) => {{ const patterns = analyzePatterns(data); return applyMLModel(patterns); }};", "const autoRespond = (issue) => {{ const response = determineResponse(issue); if (response.automated) {{ executeResponse(response.action); }} else {{ escalateToHuman(issue); }} }};"]
        }},
        {{
            "heading": "Real-World Applications and Case Studies",
            "content": "Write 3-4 detailed paragraphs discussing real-world applications, industry use cases, success stories, and lessons learned from practical implementations.",
            "code_examples": ["const deployWithRollback = async (version) => {{ const health = await monitorHealth(); if (health.failing > THRESHOLD) {{ await rollback(); return false; }} return true; }};", "const generateDashboard = (metrics) => {{ return {{ status: getStatus(), alerts: getAlerts(), recommendations: generateRecs(metrics) }}; }};"]
        }},
        {{
            "heading": "Conclusion and Future Considerations",
            "content": "Write 2-3 detailed paragraphs summarizing key takeaways, discussing future trends, and providing guidance on next steps for readers.",
            "code_examples": []
        }}
    ],
    "tags": ["Serverless", "Cloud Computing", "Performance", "Architecture", "Best Practices"],
    "read_time": 12
}}

IMPORTANT: 
- Return ONLY valid JSON, no other text
- Make each section comprehensive and detailed
- Aim for 15-20 total paragraphs across all sections
- Include specific, actionable insights and examples
- Write content that provides real value to readers
- For code_examples: Provide actual working code snippets, NOT placeholder comments like "// Example: ..."
- Code should be real, functional examples that readers can use
- Avoid generic placeholders - write specific, meaningful code
"""
        
        model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
        response = model.generate_content(
            comprehensive_prompt,
            generation_config=GenerationConfig(
                temperature=0.4,  # Slightly higher for more creative content
                max_output_tokens=8000,  # Significantly increased token limit
                top_p=0.9,  # Add top_p for better content diversity
                top_k=40    # Add top_k for better content selection
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
You are a technical blog writer. Generate a comprehensive, detailed blog post about: {topic}

IMPORTANT: You must return ONLY a valid JSON object. No other text, no explanations, no markdown formatting.

Return this exact JSON structure:
{{
    "title": "Your Comprehensive Blog Title Here",
    "description": "A detailed description of what this blog post covers and what readers will learn",
    "sections": [
        {{
            "heading": "Introduction",
            "content": "Write 3-4 detailed paragraphs introducing the topic, explaining its importance in modern cloud computing, and setting the context for readers. Make this engaging and informative.",
            "code_examples": []
        }},
        {{
            "heading": "Core Concepts and Fundamentals",
            "content": "Write 4-5 detailed paragraphs explaining the fundamental concepts, principles, and underlying mechanisms. Break down complex ideas into digestible parts with clear explanations and examples.",
            "code_examples": ["// Detailed code example 1 with comprehensive comments", "// Detailed code example 2 with explanations", "// Configuration example with best practices"]
        }},
        {{
            "heading": "Implementation Strategies and Best Practices",
            "content": "Write 4-5 detailed paragraphs covering practical implementation approaches, common patterns, best practices, and real-world considerations. Include specific guidance and actionable advice.",
            "code_examples": ["// Best practice implementation with detailed comments", "// Error handling and edge case examples", "// Performance optimization code"]
        }},
        {{
            "heading": "Advanced Techniques and Optimization",
            "content": "Write 3-4 detailed paragraphs covering advanced techniques, performance optimization strategies, scalability considerations, and cutting-edge approaches in this field.",
            "code_examples": ["// Advanced optimization example", "// Performance monitoring and tuning code", "// Scalability implementation"]
        }},
        {{
            "heading": "Real-World Applications and Case Studies",
            "content": "Write 3-4 detailed paragraphs discussing real-world applications, industry use cases, success stories, and lessons learned from practical implementations.",
            "code_examples": ["// Real-world implementation example", "// Case study code snippet", "// Production deployment code"]
        }},
        {{
            "heading": "Conclusion and Future Considerations",
            "content": "Write 2-3 detailed paragraphs summarizing key takeaways, discussing future trends, and providing guidance on next steps for readers.",
            "code_examples": []
        }}
    ],
    "tags": ["Serverless", "Cloud Computing", "Performance", "Architecture", "Best Practices"],
    "read_time": 15
}}

Requirements:
- Focus on cloud computing, serverless, or distributed systems
- Make content comprehensive, informative, and engaging
- Include practical examples and code snippets where relevant
- Target total content: 2000-3000 words across all sections
- Return ONLY valid JSON, no other text
- Use technical but accessible language
- Ensure JSON is properly formatted with no syntax errors
- Each section should be substantial and provide real value
- Include specific, actionable insights and implementation guidance

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
        # Create a comprehensive fallback blog post
        fallback_content = {
            "title": f"Understanding {topic}: A Comprehensive Guide",
            "description": f"A comprehensive guide about {topic} and its importance in modern cloud computing and distributed systems.",
            "sections": [
                {
                    "heading": "Introduction",
                    "content": f"This comprehensive blog post explores the fundamentals of {topic} and why it matters in today's cloud-native world. We'll dive deep into the concepts, implementation strategies, and best practices that can help you build better systems.\n\nUnderstanding {topic} is crucial for developers, architects, and DevOps engineers working in modern cloud environments. As organizations continue to adopt cloud-native architectures, the principles behind {topic} provide a foundation for making informed decisions about system design, resource allocation, and performance optimization.\n\nThe importance of {topic} extends beyond just technical implementation—it represents a fundamental shift in how we think about system architecture, resource management, and scalability in the cloud era. Whether you're working with serverless functions, microservices, or traditional cloud infrastructure, grasping these concepts will help you build better systems.",
                    "code_examples": []
                },
                {
                    "heading": "Core Concepts and Fundamentals",
                    "content": f"To understand {topic}, we need to grasp several key concepts. This includes understanding the underlying principles, common patterns, and how it fits into the broader ecosystem of cloud computing and distributed systems.\n\nThe fundamental principles of {topic} revolve around resource management, scalability, and performance optimization. These concepts work together to create systems that can efficiently handle varying workloads while maintaining reliability and cost-effectiveness.\n\nUnderstanding the underlying mechanisms involves grasping concepts like dynamic allocation, adaptive scaling, and intelligent resource management. These mechanisms work together to create systems that can respond intelligently to changing demands while maintaining performance standards.\n\nThe relationship between {topic} and system architecture is crucial—the way you design your system directly impacts how effectively you can implement these concepts. This includes considerations around data flow, component coupling, and the overall system topology.",
                    "code_examples": ["// Example: Basic resource allocation with dynamic scaling", "// Example: Configuration management with best practices", "// Example: Performance monitoring with comprehensive metrics"]
                },
                {
                    "heading": "Implementation Strategies and Best Practices",
                    "content": f"Implementing {topic} requires careful consideration of several factors. We'll explore practical approaches, common pitfalls to avoid, and strategies for ensuring your implementation is robust and scalable.\n\nStart by establishing clear metrics and monitoring capabilities that will help you understand how your system is performing. This includes setting up logging, metrics collection, and alerting systems that can provide real-time insights into system behavior.\n\nNext, consider implementing gradual rollout strategies that allow you to test changes in production without affecting all users. This might involve feature flags, canary deployments, or A/B testing approaches that minimize risk while maximizing learning opportunities.\n\nWhen implementing {topic} strategies, it's crucial to consider the operational aspects as well. This includes setting up proper alerting, establishing runbooks for common scenarios, and ensuring your team has the necessary skills and knowledge to operate the system effectively.",
                    "code_examples": ["// Best practice implementation with comprehensive error handling", "// Feature flag implementation with gradual rollout", "// Canary deployment with health checks"]
                },
                {
                    "heading": "Advanced Techniques and Optimization",
                    "content": f"Once you have the basic {topic} implementation in place, you can start exploring advanced techniques and optimization strategies. This includes implementing sophisticated monitoring and alerting systems that can detect issues before they impact users.\n\nAdvanced optimization techniques often involve machine learning and predictive analytics. By analyzing historical data and patterns, you can predict when scaling will be needed and proactively allocate resources. This proactive approach can significantly improve system performance and user experience.\n\nPerformance tuning is another critical aspect of advanced {topic} implementation. This involves fine-tuning various parameters, monitoring the impact of changes, and continuously iterating to find the optimal configuration for your specific use case and workload patterns.\n\nScalability considerations become increasingly important as your system grows. Advanced implementations often involve multi-region deployments, load balancing strategies, and sophisticated caching mechanisms that can handle massive scale while maintaining performance.",
                    "code_examples": ["// Advanced performance monitoring with ML insights", "// Predictive scaling with historical data analysis", "// Automated response system for common issues"]
                },
                {
                    "heading": "Real-World Applications and Case Studies",
                    "content": f"Understanding how {topic} works in theory is one thing, but seeing it in action through real-world applications and case studies provides invaluable insights. Many successful companies have implemented sophisticated {topic} strategies that have enabled them to scale their operations while maintaining high performance and reliability.\n\nOne common pattern in successful implementations is the use of gradual rollout strategies combined with comprehensive monitoring. Companies that excel at {topic} often start with small, controlled deployments and gradually expand based on real-world performance data and user feedback.\n\nAnother key lesson from real-world implementations is the importance of team culture and processes. Successful {topic} implementations often involve cross-functional teams that include developers, operations engineers, and business stakeholders working together to ensure that technical decisions align with business objectives.\n\nCase studies also reveal the importance of learning from failures and continuously improving. Even the most successful implementations have encountered challenges, and the key to long-term success is building systems that can learn from these experiences and adapt accordingly.",
                    "code_examples": ["// Real-world deployment strategy with rollback capability", "// Production monitoring dashboard with business metrics", "// Business impact tracking and correlation analysis"]
                },
                {
                    "heading": "Conclusion and Future Considerations",
                    "content": f"Understanding {topic} is crucial for building modern, scalable cloud applications. By following the principles and practices outlined in this post, you'll be better equipped to tackle the challenges of cloud-native development.\n\nAs we've explored throughout this comprehensive post, understanding {topic} is fundamental to building modern, scalable cloud systems. The concepts and strategies we've discussed provide a solid foundation for making architectural decisions that balance performance, reliability, and cost-effectiveness.\n\nLooking forward, the landscape of {topic} will continue to evolve as new technologies and approaches emerge. Staying current with these developments, while maintaining focus on fundamental principles, will be key to building systems that can adapt to changing requirements and scale with your organization's growth.",
                    "code_examples": []
                }
            ],
            "tags": ["Cloud Computing", "Research", "Best Practices", "Architecture", "Performance"],
            "read_time": 15
        }
        
        print("✅ Generated comprehensive fallback content structure")
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
        html_content, title = build_html_from_structure(structured_data)
        return html_content, title
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
                html_content, title = build_html_from_structure(structured_data)
                return html_content, title
            except json.JSONDecodeError as json_error:
                print(f"❌ Failed to parse extracted JSON: {json_error}")
        
        # Try to build content from partial JSON
        print("🔄 Attempting to build content from partial JSON...")
        partial_content, partial_title = build_from_partial_json(blog_content, topic)
        if partial_content:
            return partial_content, partial_title
        
        # Final fallback: treat as plain text
        print("⚠️ Using final fallback: plain text conversion")
        return f"<h2>Introduction</h2><p>Error: Could not parse structured content. Please check the AI generation.</p>", f"Understanding {topic}"

def clean_content_content(content):
    """Clean up content by removing repetitive phrases and improving readability"""
    if not content:
        return content
    
    # Remove repetitive topic mentions (e.g., "Understanding - Optimizing cold starts in AWS Lambda" repeated multiple times)
    # This often happens when the AI tries to be too specific in every sentence
    
    # Common repetitive patterns to clean up
    repetitive_patterns = [
        r'Understanding - ([^,]+) is crucial',
        r'Understanding - ([^,]+) provides',
        r'Understanding - ([^,]+) involves',
        r'Understanding - ([^,]+) requires',
        r'Understanding - ([^,]+) works',
        r'Understanding - ([^,]+) extends',
        r'Understanding - ([^,]+) revolves',
        r'Understanding - ([^,]+) represents',
    ]
    
    cleaned_content = content
    for pattern in repetitive_patterns:
        # Replace repetitive "Understanding - Topic" patterns with more natural language
        cleaned_content = re.sub(pattern, r'This concept is crucial', cleaned_content)
        cleaned_content = re.sub(pattern, r'This concept provides', cleaned_content)
        cleaned_content = re.sub(pattern, r'This concept involves', cleaned_content)
        cleaned_content = re.sub(pattern, r'This concept requires', cleaned_content)
        cleaned_content = re.sub(pattern, r'This concept works', cleaned_content)
        cleaned_content = re.sub(pattern, r'This concept extends', cleaned_content)
        cleaned_content = re.sub(pattern, r'This concept revolves', cleaned_content)
        cleaned_content = re.sub(pattern, r'This concept represents', cleaned_content)
    
    # Remove excessive dashes and hyphens
    cleaned_content = re.sub(r' - ([A-Z][a-z]+)', r' \1', cleaned_content)
    
    # Clean up multiple spaces
    cleaned_content = re.sub(r' +', ' ', cleaned_content)
    
    # Clean up multiple newlines
    cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content)
    
    return cleaned_content.strip()

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
    
    return None, f"Understanding {topic}"

def build_html_from_structure(structured_content):
    """Build HTML from structured content"""
    html_parts = []
    
    # Validate required fields
    if not isinstance(structured_content, dict):
        print("❌ Error: structured_content is not a dictionary")
        return "<h2>Error</h2><p>Invalid content structure</p>", "Error"
    
    # Get the actual title from structured content
    actual_title = structured_content.get('title', 'Untitled Blog Post')
    
    # Get sections, default to empty list if missing
    sections = structured_content.get('sections', [])
    if not sections:
        print("❌ Warning: No sections found in structured content")
        return "<h2>Introduction</h2><p>Content structure is incomplete</p>", actual_title
    
    for i, section in enumerate(sections):
        if not isinstance(section, dict):
            print(f"❌ Warning: Section {i} is not a dictionary, skipping")
            continue
            
        heading = section.get('heading', f'Section {i+1}')
        content = section.get('content', 'Content not available')
        code_examples = section.get('code_examples', [])
        
        # Clean up the content to remove repetitive phrases and improve readability
        content = clean_content_content(content)
        
        # Skip sections with no meaningful content
        if not content or content.strip() == 'Content not available' or len(content.strip()) < 10:
            print(f"⚠️ Skipping section '{heading}' - no meaningful content")
            continue
        
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
                if para and len(para) > 10:  # Only add non-empty paragraphs with meaningful content
                    html_parts.append(f'<p>{para}</p>')
        else:
            # Single paragraph - only add if it has meaningful content
            if len(content.strip()) > 10:
                html_parts.append(f'<p>{content}</p>')
        
        # Add code examples if any - only render non-empty, meaningful code
        if code_examples and isinstance(code_examples, list):
            for code in code_examples:
                if code and isinstance(code, str):
                    # Clean the code example and check if it's meaningful
                    clean_code = code.strip()
                    # Skip code examples that are just comments or placeholders
                    if (clean_code and 
                        len(clean_code) > 10 and 
                        not clean_code.startswith('// Example:') and
                        not clean_code.startswith('// Basic') and
                        not clean_code.startswith('// Best practice') and
                        not clean_code.startswith('// Advanced') and
                        not clean_code.startswith('// Real-world') and
                        not clean_code.startswith('// Performance') and
                        not clean_code.startswith('// Predictive') and
                        not clean_code.startswith('// Automated') and
                        not clean_code.startswith('// Production') and
                        not clean_code.startswith('// Business')):
                        
                        html_parts.append(f'<pre><code>{clean_code}</code></pre>')
                    else:
                        print(f"⚠️ Skipping placeholder code example: {clean_code[:50]}...")
    
    if not html_parts:
        return "<h2>Introduction</h2><p>No content could be generated from the structured data.</p>", actual_title
    
    return '\n'.join(html_parts), actual_title

def generate_test_blog(topic):
    """Generate a test blog post without requiring API keys"""
    print("🧪 Generating test blog post (no API keys required)...")
    
    test_content = {
        "title": f"Understanding {topic}: A Comprehensive Guide",
        "description": f"This comprehensive blog post explores the fundamentals of {topic} and its importance in modern cloud computing and distributed systems, providing actionable insights and implementation strategies.",
        "sections": [
            {
                "heading": "Introduction",
                "content": f"In today's rapidly evolving cloud computing landscape, understanding {topic} has become increasingly important for developers, architects, and DevOps engineers. This concept plays a crucial role in building scalable, reliable, and cost-effective systems that can handle the demands of modern applications.\n\nAs organizations continue to adopt cloud-native architectures, the principles behind {topic} provide a foundation for making informed decisions about system design, resource allocation, and performance optimization. Whether you're working with serverless functions, microservices, or traditional cloud infrastructure, grasping these concepts will help you build better systems.\n\nThe importance of {topic} extends beyond just technical implementation—it represents a fundamental shift in how we think about system architecture, resource management, and scalability in the cloud era. Understanding these principles is essential for anyone looking to build robust, high-performance applications that can scale with business growth.",
                "code_examples": []
            },
            {
                "heading": "Core Concepts and Fundamentals",
                "content": f"At its heart, {topic} revolves around several key principles that govern how systems behave and scale. The first concept to understand is the relationship between resource allocation and performance. When we talk about {topic}, we're essentially discussing how systems allocate and manage resources to meet varying demands.\n\nAnother fundamental aspect is the trade-off between efficiency and reliability. Systems that optimize for {topic} often need to balance these competing concerns, making architectural decisions that prioritize certain characteristics over others. This balancing act requires deep understanding of both the technical constraints and business requirements.\n\nUnderstanding the underlying mechanisms of {topic} involves grasping concepts like resource pooling, dynamic allocation, and adaptive scaling. These mechanisms work together to create systems that can respond intelligently to changing workloads while maintaining performance and reliability standards.\n\nThe relationship between {topic} and system architecture is crucial—the way you design your system directly impacts how effectively you can implement these concepts. This includes considerations around data flow, component coupling, and the overall system topology.",
                "code_examples": [
                    "const allocateResources = (demand) => {\n  const baseAllocation = demand * 1.5;\n  const maxResources = getMaxAvailableResources();\n  return Math.min(baseAllocation, maxResources);\n};",
                    "const monitorPerformance = () => {\n  return {\n    latency: measureLatency(),\n    throughput: measureThroughput(),\n    resourceUtilization: getResourceUsage(),\n    errorRate: calculateErrorRate(),\n    responseTime: measureResponseTime()\n  };\n};",
                    "const getSystemConfig = () => {\n  return {\n    scalingThreshold: process.env.SCALING_THRESHOLD || 0.8,\n    maxInstances: process.env.MAX_INSTANCES || 10,\n    cooldownPeriod: process.env.COOLDOWN_PERIOD || 300\n  };\n};"
                ]
            },
            {
                "heading": "Implementation Strategies and Best Practices",
                "content": f"Implementing effective {topic} strategies requires a systematic approach that considers multiple factors. Start by establishing clear metrics and monitoring capabilities that will help you understand how your system is performing. This includes setting up logging, metrics collection, and alerting systems that can provide real-time insights into system behavior.\n\nNext, consider implementing gradual rollout strategies that allow you to test changes in production without affecting all users. This might involve feature flags, canary deployments, or A/B testing approaches that minimize risk while maximizing learning opportunities. Remember that successful {topic} implementation is often iterative, requiring continuous monitoring and adjustment based on real-world performance data.\n\nWhen implementing {topic} strategies, it's crucial to consider the operational aspects as well. This includes setting up proper alerting, establishing runbooks for common scenarios, and ensuring your team has the necessary skills and knowledge to operate the system effectively.\n\nAnother key consideration is the integration with existing infrastructure and tools. Your {topic} implementation should work seamlessly with your current monitoring, logging, and deployment systems, rather than requiring a complete overhaul of your existing toolchain.",
                "code_examples": [
                    "const isFeatureEnabled = (featureName, userId) => {\n  const feature = getFeatureConfig(featureName);\n  const userHash = hashUserId(userId);\n  const rolloutPercentage = feature.rolloutPercentage || 0;\n  \n  return feature.enabled && \n         (rolloutPercentage === 100 || \n          userHash % 100 < rolloutPercentage);\n};",
                    "const shouldUseCanary = (request) => {\n  const canaryHeader = request.headers['x-canary'];\n  const randomRoll = Math.random();\n  const canaryPercentage = getCanaryPercentage();\n  \n  return canaryHeader === 'true' || randomRoll < canaryPercentage;\n};",
                    "const handleSystemOperation = async (operation) => {\n  try {\n    const startTime = Date.now();\n    const result = await operation();\n    const duration = Date.now() - startTime;\n    \n    logSuccess(operation.name, duration, result);\n    return result;\n  } catch (error) {\n    logError(operation.name, error);\n    throw error;\n  }\n};"
                ]
            },
            {
                "heading": "Advanced Techniques and Optimization",
                "content": f"Once you have the basic {topic} implementation in place, you can start exploring advanced techniques and optimization strategies. This includes implementing sophisticated monitoring and alerting systems that can detect issues before they impact users, as well as developing automated response mechanisms that can handle common problems without human intervention.\n\nAdvanced optimization techniques often involve machine learning and predictive analytics. By analyzing historical data and patterns, you can predict when scaling will be needed and proactively allocate resources. This proactive approach can significantly improve system performance and user experience.\n\nPerformance tuning is another critical aspect of advanced {topic} implementation. This involves fine-tuning various parameters, monitoring the impact of changes, and continuously iterating to find the optimal configuration for your specific use case and workload patterns.\n\nScalability considerations become increasingly important as your system grows. Advanced implementations often involve multi-region deployments, load balancing strategies, and sophisticated caching mechanisms that can handle massive scale while maintaining performance.",
                "code_examples": [
                    "const predictScalingNeeds = (historicalData) => {\n  const patterns = analyzeUsagePatterns(historicalData);\n  const predictions = applyMLModel(patterns);\n  return predictions.map(prediction => ({\n    timestamp: prediction.time,\n    expectedLoad: prediction.load,\n    recommendedInstances: prediction.instances\n  }));\n};",
                    "const monitorAdvancedMetrics = () => {\n  return {\n    cpuUtilization: getCPUUsage(),\n    memoryUsage: getMemoryUsage(),\n    networkIO: getNetworkIO(),\n    diskIO: getDiskIO(),\n    customMetrics: getCustomMetrics()\n  };\n};",
                    "const autoRespondToIssues = (issue) => {\n  const response = determineResponse(issue);\n  if (response.automated) {\n    executeAutomatedResponse(response.action);\n    logAutomatedResponse(issue, response);\n  } else {\n    escalateToHuman(issue, response);\n  }\n};"
                ]
            },
            {
                "heading": "Real-World Applications and Case Studies",
                "content": f"Understanding how {topic} works in theory is one thing, but seeing it in action through real-world applications and case studies provides invaluable insights. Many successful companies have implemented sophisticated {topic} strategies that have enabled them to scale their operations while maintaining high performance and reliability.\n\nOne common pattern in successful implementations is the use of gradual rollout strategies combined with comprehensive monitoring. Companies that excel at {topic} often start with small, controlled deployments and gradually expand based on real-world performance data and user feedback.\n\nAnother key lesson from real-world implementations is the importance of team culture and processes. Successful {topic} implementations often involve cross-functional teams that include developers, operations engineers, and business stakeholders working together to ensure that technical decisions align with business objectives.\n\nCase studies also reveal the importance of learning from failures and continuously improving. Even the most successful implementations have encountered challenges, and the key to long-term success is building systems that can learn from these experiences and adapt accordingly.",
                "code_examples": [
                    "const deployWithRollback = async (version) => {\n  const deployment = await startDeployment(version);\n  const healthChecks = await monitorHealth(deployment.id);\n  \n  if (healthChecks.failing > HEALTH_CHECK_THRESHOLD) {\n    await rollbackDeployment(deployment.id);\n    notifyTeam('Deployment rolled back due to health check failures');\n    return false;\n  }\n  \n  return true;\n};",
                    "const generateDashboard = (metrics) => {\n  return {\n    currentStatus: getSystemStatus(),\n    performanceMetrics: getPerformanceMetrics(),\n    alerts: getActiveAlerts(),\n    recommendations: generateRecommendations(metrics)\n  };\n};",
                    "const trackBusinessImpact = (technicalMetrics) => {\n  return {\n    userExperience: calculateUserExperienceScore(technicalMetrics),\n    businessMetrics: getBusinessMetrics(),\n    correlation: analyzeCorrelation(technicalMetrics, businessMetrics)\n  };\n};"
                ]
            },
            {
                "heading": "Conclusion and Future Considerations",
                "content": f"As we've explored throughout this comprehensive post, understanding {topic} is fundamental to building modern, scalable cloud systems. The concepts and strategies we've discussed provide a solid foundation for making architectural decisions that balance performance, reliability, and cost-effectiveness.\n\nLooking forward, the landscape of {topic} will continue to evolve as new technologies and approaches emerge. Staying current with these developments, while maintaining focus on fundamental principles, will be key to building systems that can adapt to changing requirements and scale with your organization's growth.\n\nThe future of {topic} likely involves even more sophisticated automation, machine learning integration, and intelligent decision-making systems. As these technologies mature, they will provide new opportunities to optimize system performance and resource utilization in ways that weren't possible before.",
                "code_examples": []
            }
        ],
        "tags": ["Cloud Computing", "System Design", "Performance", "Best Practices", "Architecture"],
        "read_time": 15
    }
    
    print("✅ Test blog content generated successfully")
    html_content, title = build_html_from_structure(test_content)
    return html_content, title

def generate_blog_html(topic):
    """Generate blog content using structured approach"""
    # Check if we have any API keys configured
    if not OPENAI_API_KEY and not GEMINI_API_KEY:
        print("⚠️ No API keys configured. Running in test mode...")
        html_content, title = generate_test_blog(topic)
        return html_content, title
    
    # Generate structured content
    structured_content, actual_title = generate_structured_content(topic)
    
    # Format it using the template
    if structured_content:
        print("🔄 Formatting content with template...")
        formatted_content = format_blog_with_template(topic, structured_content, actual_title)
        return formatted_content, actual_title
    else:
        print("❌ No structured content generated")
        return None, None

def format_blog_with_template(topic, content_html, title):
    """Format the AI-generated content using TEMPLATE.html"""
    
    # Read the template file
    template_path = Path(TEMPLATE_FILE)
    if not template_path.exists():
        print(f"Warning: {TEMPLATE_FILE} not found. Using raw content.")
        return content_html
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()
    
    # Use the passed title instead of extracting from content
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
    formatted_content = template
    formatted_content = formatted_content.replace('{{TITLE}}', title)
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

def commit_blog_and_index(blog_file, index_file, title):
    """Commit both the new blog post and updated index file together"""
    try:
        import subprocess
        
        # Configure git for the workflow
        subprocess.run(["git", "config", "--global", "user.name", "GitHub Actions"], check=True)
        subprocess.run(["git", "config", "--global", "user.email", "actions@github.com"], check=True)
        
        # Add both files
        subprocess.run(["git", "add", blog_file], check=True)
        subprocess.run(["git", "add", index_file], check=True)
        
        # Commit both changes together
        commit_message = f"Add blog post and update index: {title}"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        
        # Push to the current branch
        subprocess.run(["git", "push"], check=True)
        
        print(f"✅ Blog post and index committed and pushed to Git")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Git operations failed: {e}")
        print("Files saved locally but not committed to Git")
        return False
    except Exception as e:
        print(f"Unexpected error during git operations: {e}")
        print("Files saved locally but not committed to Git")
        return False

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
    
    # Save the file locally
    with open(filename, "w", encoding='utf-8') as f:
        f.write(content_html)
    
    print(f"Blog post saved locally: {filename}")
    
    return filename

def ensure_placeholder_exists():
    """Ensure the BLOG-ENTRIES placeholder exists in the index file"""
    if not Path(INDEX_FILE).exists():
        print(f"❌ {INDEX_FILE} not found. Cannot ensure placeholder.")
        return False

    with open(INDEX_FILE, "r", encoding='utf-8') as f:
        html = f.read()

    if "<!-- BLOG-ENTRIES -->" in html:
        print("✅ BLOG-ENTRIES placeholder found")
        return True
    else:
        print("⚠️ BLOG-ENTRIES placeholder missing. Adding it back...")
        
        # Find the "Coming Soon" card and add the placeholder before it
        coming_soon_pattern = '''                <div class="blog-card rounded-xl p-6 border border-gray-800 card-hover">
                    <div class="flex items-center mb-3">
                        <span class="text-gray-400 text-sm">Coming Soon</span>
                    </div>
                    <h3 class="text-xl font-bold text-primary mb-3">
                        🚀 More Blog Posts Coming Soon!
                    </h3>
                    <p class="text-gray-300 mb-4">
                        I'm working on more articles about cloud computing, serverless optimization, and distributed systems research. Stay tuned!
                    </p>
                    <div class="flex flex-wrap gap-2 mb-4">
                        <span class="tag">Coming Soon</span>
                        <span class="tag">Cloud Computing</span>
                        <span class="tag">Research</span>
                    </div>
                    <div class="flex items-center justify-between">
                        <span class="text-gray-400 text-sm">📖 More content soon</span>
                        <span class="text-gray-500">Stay tuned!</span>
                    </div>
                </div>'''
        
        # Add the placeholder before the Coming Soon card
        placeholder_html = '''                <!-- BLOG-ENTRIES -->
                <div class="blog-card rounded-xl p-6 border border-gray-800 card-hover">
                    <div class="flex items-center mb-3">
                        <span class="text-gray-400 text-sm">Coming Soon</span>
                    </div>
                    <h3 class="text-xl font-bold text-primary mb-3">
                        🚀 More Blog Posts Coming Soon!
                    </h3>
                    <p class="text-gray-300 mb-4">
                        I'm working on more articles about cloud computing, serverless optimization, and distributed systems research. Stay tuned!
                    </p>
                    <div class="flex flex-wrap gap-2 mb-4">
                        <span class="tag">Coming Soon</span>
                        <span class="tag">Cloud Computing</span>
                        <span class="tag">Research</span>
                    </div>
                    <div class="flex items-center justify-between">
                        <span class="text-gray-400 text-sm">📖 More content soon</span>
                        <span class="text-gray-500">Stay tuned!</span>
                    </div>
                </div>'''
        
        html = html.replace(coming_soon_pattern, placeholder_html)
        
        with open(INDEX_FILE, "w", encoding='utf-8') as f:
            f.write(html)
        
        print("✅ BLOG-ENTRIES placeholder restored")
        return True

def update_index(title, filename):
    """Update blog/index.html with new blog entry"""
    print(f"🔄 Updating blog index with: {title}")
    
    # Read the current index file
    with open(INDEX_FILE, "r", encoding='utf-8') as f:
        html = f.read()
    
    # Ensure the placeholder exists at the top of the grid
    ensure_placeholder_exists()
    
    # Generate the HTML for the new blog post
    current_date = datetime.datetime.now().strftime("%B %d, %Y")
    read_time = "5 min read"  # Default read time
    
    post_html = f'''                <div class="blog-card rounded-xl p-6 border border-gray-800 card-hover">
                    <div class="flex items-center mb-3">
                        <span class="text-gray-400 text-sm">{current_date}</span>
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
                </div>

                <!-- BLOG-ENTRIES -->'''

    # Check if the placeholder exists
    if "<!-- BLOG-ENTRIES -->" in html:
        print(f"🔍 Found BLOG-ENTRIES placeholder, replacing with new post...")
        # Replace the placeholder with new post + placeholder (preserving it for future posts)
        html = html.replace("<!-- BLOG-ENTRIES -->", post_html)
        
        # Write the updated HTML back to the file
        with open(INDEX_FILE, "w", encoding='utf-8') as f:
            f.write(html)
        
        print(f"✅ Updated {INDEX_FILE} with new blog entry: {title}")
        print(f"📝 Blog post added to index: {filename}")
        print(f"🔍 BLOG-ENTRIES placeholder preserved for future posts")
        
        # Verify the update worked
        with open(INDEX_FILE, "r", encoding='utf-8') as f:
            updated_html = f.read()
        if title in updated_html:
            print(f"✅ Verification: Title '{title}' found in updated index")
        else:
            print(f"❌ Warning: Title '{title}' not found in updated index")
            
    else:
        print(f"❌ Warning: '<!-- BLOG-ENTRIES -->' placeholder not found in {INDEX_FILE}")
        print("🔍 Looking for alternative insertion points...")
        
        # Try to find a good place to insert (before the "Coming Soon" card)
        if "Coming Soon" in html:
            # Insert before the "Coming Soon" card and add the placeholder back
            coming_soon_section = '''                <div class="blog-card rounded-xl p-6 border border-gray-800 card-hover">
                    <div class="flex items-center mb-3">
                        <span class="text-gray-400 text-sm">Coming Soon</span>
                    </div>
                    <h3 class="text-xl font-bold text-primary mb-3">
                        🚀 More Blog Posts Coming Soon!
                    </h3>
                    <p class="text-gray-300 mb-4">
                        I'm working on more articles about cloud computing, serverless optimization, and distributed systems research. Stay tuned!
                    </p>
                    <div class="flex flex-wrap gap-2 mb-4">
                        <span class="tag">Coming Soon</span>
                        <span class="tag">Cloud Computing</span>
                        <span class="tag">Research</span>
                    </div>
                    <div class="flex items-center justify-between">
                        <span class="text-gray-400 text-sm">📖 More content soon</span>
                        <span class="text-gray-500">Stay tuned!</span>
                    </div>
                </div>'''
            
            # Insert new post + placeholder before the Coming Soon section
            new_content = post_html + '\n' + coming_soon_section
            
            html = html.replace(
                coming_soon_section,
                new_content,
                1
            )
            
            with open(INDEX_FILE, "w", encoding='utf-8') as f:
                f.write(html)
            
            print(f"✅ Updated {INDEX_FILE} by inserting before 'Coming Soon' card")
            print(f"🔍 BLOG-ENTRIES placeholder added back for future posts")
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
        result = generate_blog_html(topic)
        
        if not result or result[0] is None:
            print("❌ Error: No blog content generated")
            exit(1)
        
        blog_html, actual_title = result
        print(f"✅ Content generated successfully. Length: {len(blog_html)} characters")
        print(f"📝 Blog title: {actual_title}")
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
            draft_file = save_blog_file(actual_title, blog_html)
            print(f"✅ Draft saved to: {draft_file}")
            
            # 4. Update topics.md
            print("\n🔄 Step 4: Updating topics file...")
            update_topics_file(remaining_topics)
            print("✅ Topics file updated")
            
            # 5. Update blog/index.html
            print("\n🔄 Step 5: Updating blog index...")
            update_index(actual_title, draft_file)
            print("✅ Blog index updated")
            
            # 6. Commit both blog post and updated index to Git
            print("\n🔄 Step 6: Committing blog post and updated index to Git...")
            if commit_blog_and_index(draft_file, INDEX_FILE, actual_title):
                print("✅ Both files committed and pushed successfully")
            else:
                print("⚠️ Warning: Git commit failed, files only saved locally")
            
            # 7. Verify placeholder is preserved
            print("\n🔄 Step 7: Verifying placeholder preservation...")
            if ensure_placeholder_exists():
                print("✅ BLOG-ENTRIES placeholder verified and preserved")
            else:
                print("⚠️ Warning: Could not verify placeholder preservation")
            
            print(f"\n🎉 Blog generation complete! New post: {draft_file}")
        else:
            print("❌ Skipping local save and index update as no blog content was generated.")

    except RuntimeError as e:
        print(f"❌ Critical error during blog generation: {e}")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        exit(1)