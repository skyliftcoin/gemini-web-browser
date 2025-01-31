# gemini_integration.py
import os
import base64
import logging
import json
import re
from datetime import datetime
import uuid
import google.generativeai as genai
from PIL import Image
import time
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gemini.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GeminiIntegration:
    """Integration with Google's Gemini API."""

    def __init__(self):
        """Initialize the Gemini integration."""
        try:
            logger.info("=== Setting up Gemini API ===")
            
            # Get API key
            api_key = self._get_api_key()
            if not api_key:
                raise Exception("No API key found")
            logger.info("Found API key")
            
            # Configure genai
            genai.configure(api_key=api_key)
            logger.info("Configured genai with API key")
            
            # Create model
            logger.info("Creating model instance: gemini-2.0-flash-thinking-exp-01-21")
            self.model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp-01-21')
            
            # List available models
            for model in genai.list_models():
                logger.info(f"Available model: {model.name}")
            
            # Create chat session
            self.chat = self.model.start_chat()
            logger.info("Created model instance and chat session")
            
            # Add rate limiting
            self.last_request_time = 0
            self.min_request_interval = 2  # Minimum seconds between requests
            
            # Test the connection
            test_response = self.chat.send_message("Hello!")
            if test_response:
                # Clean the response text for logging
                clean_text = ''.join(c for c in test_response.text if c.isascii())
                logger.info(f"Test response: {clean_text}")
            
            logger.info("Gemini API setup complete")
            
        except Exception as e:
            logger.error(f"Error initializing Gemini: {e}")
            raise

    def _get_api_key(self):
        """Get the Gemini API key from the environment or file."""
        try:
            # First try environment variable
            api_key = os.getenv('GEMINI_API_KEY')
            if api_key:
                return api_key

            # Then try file
            key_file = 'gemini key.txt'
            if os.path.exists(key_file):
                with open(key_file, 'r') as f:
                    api_key = f.read().strip()
                if api_key:
                    return api_key

            logger.error("No API key found in environment or key file")
            return None

        except Exception as e:
            logger.error(f"Error getting API key: {e}")
            return None

    def process_request(self, user_input, current_url=None, screenshot=None):
        """Process a request from the user."""
        try:
            # Prepare the message
            message = self._prepare_message(user_input, current_url, screenshot)
            if not message:
                return {"action": "respond", "message": "Error preparing message"}

            # Add rate limiting
            current_time = time.time()
            if hasattr(self, 'last_request_time'):
                time_since_last = current_time - self.last_request_time
                if time_since_last < self.min_request_interval:
                    wait_time = self.min_request_interval - time_since_last
                    logger.info(f"Rate limiting: waiting {wait_time:.2f} seconds")
                    time.sleep(wait_time)
            self.last_request_time = current_time

            # Send request to Gemini with retries
            max_retries = 3
            retry_delay = 2
            
            for attempt in range(max_retries):
                try:
                    logger.info("Sending request to Gemini...")
                    response = self.chat.send_message(message)
                    
                    # Clean up screenshot after successful send
                    if screenshot and os.path.exists(screenshot):
                        try:
                            os.remove(screenshot)
                            logger.info(f"Deleted used screenshot: {screenshot}")
                        except Exception as e:
                            logger.warning(f"Failed to delete screenshot {screenshot}: {e}")
                    
                    if response:
                        # Return the raw response text without wrapping it in another JSON object
                        return self._process_response(response.text)
                    return "No response from Gemini"
                    
                except Exception as e:
                    if "429" in str(e) and attempt < max_retries - 1:
                        wait_time = retry_delay * (attempt + 1)
                        logger.warning(f"Rate limit hit, waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        continue
                    raise

        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return f"Error: {str(e)}"

    def _prepare_message(self, user_input, current_url, screenshot):
        """Prepare the message for Gemini."""
        try:
            # Prepare message parts
            parts = [{"text": f"""
            Current page: {current_url or 'No page loaded'}
            User request: {user_input}

            You are an intelligent browser automation assistant that helps users accomplish complex tasks.
            Think and act like a human researcher/assistant would.

            Core Capabilities:
            1. Task Planning and Execution
               - Break down complex tasks into logical steps
               - Chain multiple actions together to accomplish goals
               - Maintain context across multiple steps
               - Handle errors and unexpected situations gracefully

            2. Web Navigation and Research
               - Navigate to any website
               - Perform searches using site-specific search functionality
               - Fill out forms and interact with elements
               - Extract and analyze information
               - Make informed decisions

            3. User Interaction
               - Keep users informed of your progress
               - Explain your reasoning and decisions
               - Ask for clarification when needed
               - Provide clear summaries and recommendations

            Available Actions:

            1. Navigate:
               {{"action": "navigate", "url": "https://example.com"}}
               - Use this to navigate to any website
               - ALWAYS include the full URL with https://
               - Example: {{"action": "navigate", "url": "https://www.craigslist.org"}}

            2. Search:
               {{"action": "search", "value": "search terms", "selector": "css_selector"}}
               - Use this to search or enter text into any input field
               - The browser will automatically find the best matching input field if the selector is not exact
               - Examples:
                 * Generic search: {{"action": "search", "value": "ford trucks", "selector": "input[type='search']"}}
                 * Form input: {{"action": "search", "value": "Hello", "selector": "textarea"}}

            3. Click:
               {{"action": "click", "selector": "css_selector"}}
               - Use this to click any clickable element (buttons, links, etc)
               - Example: {{"action": "click", "selector": "button[type='submit']"}}

            4. Think/Respond:
               {{"action": "respond", "message": "your message"}}
               - Use this to:
                 * Share your findings
                 * Explain your next steps
                 * Ask for user input
                 * Provide recommendations

            Important Rules:
            1. ALWAYS use the exact JSON format shown above for actions
            2. ALWAYS include https:// in URLs
            3. ONE action per line
            4. Actions must be on their own line
            5. No other content on action lines
            6. For complex tasks, break them down into multiple steps
               Example: "go to craigslist and find ford trucks" becomes:
               {{"action": "respond", "message": "I'll help you find Ford trucks on Craigslist. First, I'll navigate to Craigslist."}}
               {{"action": "navigate", "url": "https://www.craigslist.org"}}
               {{"action": "search", "value": "ford trucks", "selector": "input#query"}}

            Now, help the user with their request: {user_input}
            """}]

            # Add screenshot if available
            if screenshot and os.path.exists(screenshot):
                try:
                    with open(screenshot, 'rb') as img_file:
                        image_data = img_file.read()
                        parts.append({
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": base64.b64encode(image_data).decode('utf-8')
                            }
                        })
                    logger.info(f"Added screenshot: {screenshot}")
                except Exception as e:
                    logger.warning(f"Error processing screenshot: {e}")

            return parts[0]['text']

        except Exception as e:
            logger.error(f"Error preparing message: {e}")
            return None

    def send_request(self, user_input=None, current_url=None, content=None):
        """Send a request to Gemini."""
        try:
            # Don't send automatic follow-up requests when waiting for user input
            if not user_input and not content:
                return None

            # Prepare the message
            if user_input:
                message = user_input
            elif content:
                message = self.process_content(content)
            else:
                return None

            # Add rate limiting
            current_time = time.time()
            if current_time - self.last_request_time < self.min_request_interval:
                logger.info(f"Rate limiting: waiting {self.min_request_interval} seconds")
                time.sleep(self.min_request_interval - (current_time - self.last_request_time))
            self.last_request_time = current_time

            # Send request to Gemini
            response = self.chat.send_message(message)
            if not response:
                logger.error("No response from Gemini")
                return {"action": "respond", "message": "I didn't get a response. Please try again."}

            return self._process_response(response.text)

        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return {"action": "respond", "message": f"Error: {str(e)}"}

    def _process_response(self, response_text):
        """Process the response from Gemini and extract actions."""
        try:
            # Look for JSON-formatted actions in the response
            actions = []
            lines = response_text.split('\n')
            
            # First check if it's a JSON response
            if '```json' in response_text:
                # Extract JSON
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                if json_end != -1:
                    try:
                        json_str = response_text[json_start:json_end].strip()
                        json_data = json.loads(json_str)
                        if isinstance(json_data, dict) and 'action' in json_data:
                            actions.append(json_data)
                    except json.JSONDecodeError:
                        pass

            # Look for inline JSON actions
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Look for JSON action patterns
                if '"action":' in line:
                    try:
                        # Try to parse the entire line as JSON
                        action_dict = json.loads(line)
                        if isinstance(action_dict, dict) and 'action' in action_dict:
                            actions.append(action_dict)
                            continue
                    except json.JSONDecodeError:
                        pass
                        
                    # If that fails, try to extract JSON from within the line
                    start_idx = line.find('{')
                    end_idx = line.rfind('}')
                    if start_idx >= 0 and end_idx > start_idx:
                        try:
                            json_str = line[start_idx:end_idx + 1]
                            action_dict = json.loads(json_str)
                            if isinstance(action_dict, dict) and 'action' in action_dict:
                                actions.append(action_dict)
                        except json.JSONDecodeError:
                            pass
            
            # If we found actions, return them along with any message
            if actions:
                return {
                    'message': response_text,
                    'actions': actions
                }
            
            # If no actions found, treat the entire response as a message
            return {
                'message': response_text,
                'actions': []
            }
            
        except Exception as e:
            logger.error(f"Error processing response: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'message': f"Error processing response: {str(e)}",
                'actions': []
            }

    def process_content(self, content):
        """Process extracted content using Gemini."""
        prompt = f"""
        Content: {content}

        Task: {self.current_task}

        Based on the task:
        1. If summarizing, provide a concise summary
        2. If analyzing, extract key information
        3. If finding specific items (like emails), identify and list them
        4. If processing data, provide insights

        Keep the response focused and relevant to the task.
        """

        response = self.chat.send_message(prompt)
        return response.text if hasattr(response, 'text') else str(response)

    def _plan_new_task(self, message, current_url, screenshot_path):
        """Plan out steps for a new task."""
        # First check if this is a news search
        if "news" in message.lower() or "latest" in message.lower():
            return {
                "task": "Search for latest news",
                "steps": [
                    {
                        "action": "fill",
                        "details": "input[name='q']",
                        "value": "latest news",
                        "why": "enter search query"
                    },
                    {
                        "action": "click",
                        "details": "a[href*='tbm=nws']",
                        "why": "go to news section"
                    }
                ]
            }

        prompt = f"""
        User Request: {message}
        Current URL: {current_url}

        Create a task plan using SPECIFIC selectors for the current page. Common selectors:

        Google Search:
        - Search box: input[name='q']
        - Search button: input[name='btnK']
        - News tab: a[href*='tbm=nws']
        - Images tab: a[href*='tbm=isch']

        Break this task into steps using these actions:
        1. NAVIGATION: {{"action": "navigate", "details": "exact_url", "why": "reason"}}
        2. CLICKING: {{"action": "click", "details": "exact_selector", "why": "reason"}}
        3. FORM FILLING: {{"action": "fill", "details": "input[name='q']", "value": "text", "why": "reason"}}

        Format response as JSON:
        {{
            "task": "description",
            "steps": [
                // List of steps with EXACT selectors
            ]
        }}

        IMPORTANT: 
        - Use EXACT selectors that exist on the page
        - NEVER use placeholder text like 'css_selector'
        - Include ALL necessary steps

        Respond ONLY with the JSON task plan.
        """

        # Load screenshot
        try:
            with open(screenshot_path, 'rb') as img_file:
                image_data = img_file.read()

            parts = [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": base64.b64encode(image_data).decode('utf-8')
                    }
                }
            ]

            response = self.chat.send_message(parts[0]['text'])
            text = response.text if hasattr(response, 'text') else str(response)
            logger.info(f"Generated task plan: {text}")

            try:
                text = text.strip()
                if text.startswith('```json'):
                    text = text[7:]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()

                plan = json.loads(text)
                self.current_task = plan['task']
                self.task_steps = plan['steps']
                self.current_step = 0

                return self._execute_next_step(message, current_url, screenshot_path)

            except json.JSONDecodeError as e:
                logger.exception("Error parsing task plan JSON")
                return {"action": "respond", "message": "I couldn't understand the task plan. Please try again."}
            except Exception as e:
                logger.exception("Error parsing task plan")
                return {"action": "respond", "message": "I understand you want to perform a task, but I'm having trouble planning the steps. Could you be more specific about what you'd like to do?"}

        except FileNotFoundError:
            logger.error(f"Screenshot file not found: {screenshot_path}")
            return {"action": "respond", "message": "Screenshot not found. Cannot plan the task."}
        except Exception as e:
            logger.exception("Unexpected error in planning new task")
            return {"action": "respond", "message": f"An error occurred while planning the task: {str(e)}"}

    def _execute_next_step(self, message, current_url, screenshot_path):
        """Execute the next step in the current task."""
        if not self.task_steps or self.current_step >= len(self.task_steps):
            self.current_task = None
            self.task_steps = []
            self.current_step = 0
            return {"action": "respond", "message": "Task completed! What would you like to do next?"}

        step = self.task_steps[self.current_step]
        self.current_step += 1

        action = step['action']

        if action == 'navigate':
            return {"action": "navigate", "url": step['details']}

        elif action == 'click':
            return {"action": "click", "selector": step['details']}

        elif action == 'fill':
            return {"action": "fill", "selector": step['details'], "value": step['value']}

        elif action == 'extract':
            script = f"""
            function extractText() {{
                const elements = document.querySelectorAll('{step["details"]}');
                return Array.from(elements).map(el => el.textContent).join('\\n');
            }}
            extractText();
            """
            return {"action": "respond", "message": "Extracting content...", "script": script}

        elif action == 'execute':
            return {"action": "respond", "message": "Executing custom code...", "script": step['script']}

        elif action == 'summarize':
            script = f"""
            function getContent() {{
                const element = document.querySelector('{step["details"]}');
                return element ? element.textContent : null;
            }}
            getContent();
            """
            return {"action": "respond", "message": "Analyzing content...", "script": script}

        elif action == 'code':
            if step['language'] == 'javascript':
                return {"action": "respond", "message": "Running code...", "script": step['code']}
            else:
                return {"action": "fill", "selector": ".code-cell", "value": step['code']}

        else:
            return {"action": "respond", "message": step.get('details', 'Moving to next step...')}

    def _add_to_chat(self, message):
        """Add a message to the chat history."""
        self.chat_history.append(message)

    def _show_error(self, message):
        """Show an error message in the chat."""
        self._add_to_chat(f"Error: {message}")

    def _take_screenshot(self):
        """Take a screenshot of the browser view."""
        try:
            # Create screenshots directory if needed
            os.makedirs("screenshots", exist_ok=True)

            # Create a unique filename using timestamp and UUID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = uuid.uuid4().hex[:8]
            filename = os.path.join("screenshots", f"screenshot_{timestamp}_{unique_id}.png")

            # Take screenshot
            pixmap = self.browser.grab()
            pixmap.save(filename)

            # Display in chat interface
            scaled_pixmap = pixmap.scaledToHeight(200, Qt.TransformationMode.SmoothTransformation)
            self.screenshot_label.setPixmap(scaled_pixmap)

            logger.info(f"Screenshot saved: {filename}")
            return filename

        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return None

    def closeEvent(self, event):
        """Handle application close."""
        try:
            logger.info("Closing application")
            event.accept()
        except Exception as e:
            logger.exception("Error closing application")
            event.accept()
