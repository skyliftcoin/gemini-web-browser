import os
import json
import time
import logging
import logging.handlers
import google.generativeai as genai
from dotenv import load_dotenv
import re
import concurrent.futures
from functools import partial
import traceback
from PIL import Image

# Configure logging
logger = logging.getLogger(__name__)

class GeminiIntegration:
    def __init__(self):
        """Initialize the Gemini integration."""
        try:
            # Load environment variables
            load_dotenv()
            
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable not set")
                
            genai.configure(api_key=api_key)
            
            # Initialize model with minimal config
            self.model = genai.GenerativeModel(
                model_name="gemini-2.0-flash-thinking-exp-01-21",# never change this model
                generation_config={
                    "temperature": 0.1,
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 2048,
                }
            )
            logger.info("Gemini integration initialized successfully")
            
        except Exception as e:
            logger.critical(f"Failed to initialize Gemini: {str(e)}")
            logger.critical(f"Traceback: {traceback.format_exc()}")
            raise

    def generate_actions_with_gemini(self, user_input, current_url, screenshot_path=None):
        """Generate browser actions using Gemini."""
        try:
            # Build the prompt
            prompt = f"""You are a web browser assistant. Generate actions to help accomplish this task:

{user_input}

Return ONLY a JSON array of actions in this format:
[
    {{"action": "navigate", "url": "..."}},
    {{"action": "click", "selector": "...", "text": "...", "element_type": "..."}},
    {{"action": "type", "selector": "...", "text": "..."}},
    {{"action": "scroll", "direction": "up/down", "amount": "..."}},
    {{"action": "respond", "message": "..."}}
]

Current URL: {current_url}
A screenshot of the current page is attached.

Rules:
1. Return ONLY the JSON array, no other text
2. Use only these action types: navigate, click, type, scroll, respond
3. For selectors, use ONLY standard CSS selectors like:
   - Tag names: "button", "a", "input"
   - IDs: "#search-button"
   - Classes: ".search-input"
   - Attributes: "[type='submit']", "[aria-label='Search']"
   - Combinations: "button.primary", "input[type='text']"
   DO NOT use jQuery selectors like :contains() or :visible
4. For click/type actions, prefer using the text parameter over complex selectors
5. Ensure all JSON is properly formatted with double quotes"""

            logger.info(f"Sending prompt to Gemini: {prompt}")
            
            # Generate content with retries
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    # Generate response
                    if screenshot_path and os.path.exists(screenshot_path):
                        response = self.model.generate_content(
                            [prompt, Image.open(screenshot_path)],
                            generation_config={"temperature": 0.1}
                        )
                    else:
                        response = self.model.generate_content(
                            prompt,
                            generation_config={"temperature": 0.1}
                        )
                    
                    # Extract JSON from response
                    text = response.text.strip()
                    if text.startswith('```'):
                        text = text[text.find('['):text.rfind(']')+1]
                    
                    # Parse JSON and validate selectors
                    try:
                        actions = json.loads(text)
                        
                        # Validate and clean up selectors
                        for action in actions:
                            if 'selector' in action:
                                # Remove any jQuery-style selectors
                                selector = action['selector']
                                if ':contains(' in selector or ':visible' in selector:
                                    # If selector is invalid, rely on text matching instead
                                    action['selector'] = action.get('element_type', 'button')
                                    if 'text' not in action and ':contains(' in selector:
                                        # Extract text from :contains() selector
                                        text = re.search(r':contains\([\'"](.+?)[\'"]\)', selector)
                                        if text:
                                            action['text'] = text.group(1)
                        
                        logger.info(f"Generated valid actions: {actions}")
                        return actions
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON parse error: {str(e)}")
                        logger.error(f"Attempted to parse: {text}")
                        raise
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing actions: {str(e)}")
                    logger.error(f"Raw response was: {response.text}")
                    if attempt < max_attempts - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                        continue
                    else:
                        logger.error(f"All attempts failed: {str(e)}")
                        return [{"action": "respond", "message": f"I encountered an error: {str(e)}"}]
                        
                except Exception as e:
                    logger.error(f"Error generating actions: {str(e)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    return [{"action": "respond", "message": f"I encountered an error: {str(e)}"}]
            
        except Exception as e:
            logger.error(f"Error in generate_actions: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return [{"action": "respond", "message": f"I encountered an error: {str(e)}"}]

    def _prepare_prompt(self, task, screenshot_path=None, page_info=None):
        """Prepare the prompt for Gemini."""
        try:
            prompt = f"""You are a web browser assistant. Generate actions to help accomplish this task:

{task}

Return ONLY a JSON array of actions in this format:
[
    {{"action": "navigate", "url": "..."}},
    {{"action": "click", "selector": "...", "text": "...", "element_type": "..."}},
    {{"action": "type", "selector": "...", "text": "..."}},
    {{"action": "scroll", "direction": "up/down", "amount": "..."}},
    {{"action": "respond", "message": "..."}}
]"""

            if page_info and 'url' in page_info:
                prompt += f"\n\nCurrent URL: {page_info['url']}"

            if screenshot_path:
                prompt += "\nA screenshot of the current page is attached."

            prompt += "\n\nRules:\n1. Return ONLY the JSON array, no other text\n2. Use only these action types: navigate, click, type, scroll, respond\n3. Make actions as specific as possible with CSS selectors\n4. Ensure all JSON is properly formatted with double quotes"

            return prompt
            
        except Exception as e:
            logger.error(f"Error preparing prompt: {str(e)}")
            raise

    def _parse_actions(self, response_text):
        """Parse actions from model response."""
        try:
            # Clean up the response text
            cleaned_text = response_text.strip()
            
            # If the text starts with a markdown code block, extract it
            if cleaned_text.startswith('```'):
                match = re.search(r'```(?:json)?\s*(.*?)```', cleaned_text, re.DOTALL)
                if match:
                    cleaned_text = match.group(1).strip()
            
            # Find JSON array in response
            match = re.search(r'\[\s*{.*?}\s*\]', cleaned_text, re.DOTALL)
            if not match:
                raise ValueError("No JSON array found in response")
                
            actions_json = match.group(0)
            
            # Fix common JSON formatting issues
            actions_json = actions_json.replace("'", '"')  # Replace single quotes with double quotes
            actions_json = re.sub(r'(\w+):', r'"\1":', actions_json)  # Add quotes around property names
            actions_json = re.sub(r',\s*]', ']', actions_json)  # Remove trailing commas
            actions_json = re.sub(r',\s*}', '}', actions_json)  # Remove trailing commas in objects
            actions_json = re.sub(r'"([^"]*)":\s*""([^"]*)""', r'"\1":"\2"', actions_json)  # Fix double quoted values
            actions_json = re.sub(r'""([^"]*)""\s*:', r'"\1":', actions_json)  # Fix double quoted keys
            
            logger.debug(f"Cleaned JSON: {actions_json}")
            
            # Parse JSON
            try:
                actions = json.loads(actions_json)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error: {e}")
                logger.error(f"Attempted to parse: {actions_json}")
                raise
            
            if not isinstance(actions, list):
                raise ValueError("Parsed JSON is not a list")
                
            return actions
            
        except Exception as e:
            logger.error(f"Error parsing actions: {str(e)}")
            logger.error(f"Raw response was: {response_text}")
            raise
