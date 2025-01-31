import os
import json
import logging
from flask import Flask, request, jsonify
from gemini_integration import GeminiIntegration
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize Gemini integration
load_dotenv()
gemini = None

def init_gemini():
    """Initialize Gemini integration with retries."""
    global gemini
    try:
        gemini = GeminiIntegration()
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Gemini: {e}")
        return False

@app.route('/execute_task', methods=['POST'])
def execute_task():
    """Execute a task using Gemini."""
    global gemini
    
    try:
        # Initialize Gemini if needed
        if gemini is None and not init_gemini():
            return jsonify({"error": "Failed to initialize Gemini"}), 500
            
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        task = data.get("task")
        screenshot_path = data.get("screenshot_path")
        page_info = data.get("page_info")
        
        if not all([task, screenshot_path, page_info]):
            return jsonify({"error": "Missing required fields"}), 400
            
        logger.info("\n=== New Task Execution Request ===")
        logger.info(f"Task: {task}")
        logger.info(f"URL: {page_info.get('url')}")
        logger.info(f"Title: {page_info.get('title')}")
        logger.info(f"Screenshot: {screenshot_path}")
        
        # Generate actions using Gemini
        actions = gemini.generate_actions_with_gemini(task, screenshot_path, page_info)
        
        if not actions:
            return jsonify({"error": "Failed to generate actions"}), 500
            
        # Include screenshot path in response
        response = {
            "actions": actions.get("actions", []),
            "screenshot_path": screenshot_path
        }
            
        return jsonify(response)
        
    except Exception as e:
        logger.exception("Error executing task")
        return jsonify({"error": str(e)}), 500

@app.route('/user_confirmation', methods=['POST'])
def user_confirmation():
    confirmation_id = request.json.get('confirmation_id')
    user_response = request.json.get('user_response')
    logger.info(f"Received user confirmation: ID={confirmation_id}, Response={user_response}")
    return jsonify({"status": "confirmation_received"}) # Placeholder response


@app.route('/get_current_page_state', methods=['GET'])
def get_current_page_state():
    return jsonify({"url": "placeholder_url", "title": "Placeholder Title - API needs to fetch from UI"})


@app.route('/process', methods=['POST'])
def process_request():
    """Process a request from the browser."""
    global gemini
    
    try:
        # Initialize Gemini if needed
        if gemini is None and not init_gemini():
            return jsonify({"error": "Failed to initialize Gemini"}), 500
            
        data = request.get_json()
        message = data.get('message')
        screenshot_path = data.get('screenshot')
        page_info = data.get('pageInfo')

        if not message:
            return jsonify({"error": "No message provided"}), 400

        # Process the message using GeminiIntegration
        actions = gemini.generate_actions_with_gemini(message, screenshot_path, page_info)
        
        return jsonify({"actions": actions})
        
    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/')
def root():
    """Health check endpoint."""
    logger.info("Health check request received")
    return "Browser API Server Running"

class GeminiIntegration:
    # ... existing code ...

    def click_element(self, selector=None, text=None, element_type=None):
        """Click an element on the page."""
        try:
            # Build JavaScript to find and click element
            js = """
            function findElement(selector, text, elementType) {
                let elements = [];
                
                // Try selector first if provided
                if (selector) {
                    try {
                        elements = Array.from(document.querySelectorAll(selector));
                    } catch (e) {
                        // If selector is invalid, ignore it
                        console.warn('Invalid selector:', selector);
                    }
                }
                
                // If no elements found by selector or no selector provided,
                // try finding by text content
                if (elements.length === 0 && text) {
                    const textLower = text.toLowerCase();
                    elements = Array.from(document.querySelectorAll('a, button, input[type="submit"], input[type="button"], [role="button"]'))
                        .filter(el => {
                            const content = (el.textContent || el.value || el.getAttribute('aria-label') || '').toLowerCase();
                            return content.includes(textLower);
                        });
                        
                    // If still no matches, try all elements
                    if (elements.length === 0) {
                        elements = Array.from(document.querySelectorAll('*'))
                            .filter(el => {
                                const content = (el.textContent || el.value || el.getAttribute('aria-label') || '').toLowerCase();
                                return content.includes(textLower);
                            });
                    }
                }
                
                // Filter by element type if provided
                if (elementType && elements.length > 0) {
                    const typeLower = elementType.toLowerCase();
                    elements = elements.filter(el => {
                        return el.tagName.toLowerCase() === typeLower ||
                               el.getAttribute('type')?.toLowerCase() === typeLower ||
                               el.getAttribute('role')?.toLowerCase() === typeLower;
                    });
                }
                
                // Find best match - prefer visible elements
                const visibleElements = elements.filter(el => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0 &&
                           style.display !== 'none' &&
                           style.visibility !== 'hidden' &&
                           style.opacity !== '0';
                });
                
                return visibleElements[0] || elements[0] || null;
            }
            
            // Find and click the element
            const element = findElement(arguments[0], arguments[1], arguments[2]);
            if (!element) {
                return {"success": false, "error": "Element not found"};
            }
            
            // Try multiple click methods
            try {
                // First try native click
                element.click();
            } catch (e1) {
                try {
                    // Try mouse event
                    const event = new MouseEvent('click', {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    });
                    element.dispatchEvent(event);
                } catch (e2) {
                    // If both methods fail, try form submit
                    const form = element.closest('form');
                    if (form) {
                        try {
                            form.submit();
                        } catch (e3) {
                            return {"success": false, "error": "Failed to click or submit"};
                        }
                    } else {
                        return {"success": false, "error": "Failed to click element"};
                    }
                }
            }
            
            return {
                "success": true,
                "element": element.tagName,
                "text": element.textContent || element.value || element.getAttribute('aria-label') || ''
            };
            """
            
            result = self.page.runJavaScript(js, selector, text, element_type)
            logger.info(f"Click result: {result}")
            
            if not result or not result.get('success'):
                error = result.get('error') if result else 'Unknown error'
                logger.error(f"Click failed: {error}")
                return False
                
            logger.info(f"Click successful on {result.get('element')} element")
            return True
            
        except Exception as e:
            logger.error(f"Error clicking element: {str(e)}")
            return False

if __name__ == '__main__':
    # Initialize Gemini on startup
    if not init_gemini():
        logger.error("Failed to initialize Gemini, but starting server anyway")
        
    app.run(port=5000)