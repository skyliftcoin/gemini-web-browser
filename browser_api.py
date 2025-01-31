# browser_api.py
from flask import Flask, request, jsonify
import random
import gemini_integration
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Set up file handler with rotation
file_handler = RotatingFileHandler(
    'browser_api.log',
    maxBytes=5*1024*1024,  # 5MB
    backupCount=3,
    delay=True  # Don't open the file until first write
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Get the root logger and add the file handler
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize Gemini integration
gemini = gemini_integration.GeminiIntegration()

@app.route('/execute_task', methods=['POST'])
def execute_task():
    """Execute a task using Gemini."""
    try:
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
    """Process a request using Gemini."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        message = data.get("message")
        if not message:
            return jsonify({"error": "No message provided"}), 400
            
        logger.info("\n=== New Process Request ===")
        logger.info(f"Message: {message}")
        
        # Process with Gemini
        try:
            response = gemini.process_message(message)
            return jsonify({"message": response})
        except Exception as e:
            logger.exception("Error processing with Gemini")
            return jsonify({"error": f"Gemini processing error: {str(e)}"}), 500
            
    except Exception as e:
        logger.exception("Error processing request")
        return jsonify({"error": str(e)}), 500


@app.route('/')
def root():
    """Health check endpoint."""
    logger.info("Health check request received")
    return "Browser API Server Running"

if __name__ == '__main__':
    logger.info("\n=== Starting Browser API Server ===")
    app.run(debug=True, port=5000)