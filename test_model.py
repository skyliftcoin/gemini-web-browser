import os
import google.generativeai as genai
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get API key from environment
api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    raise ValueError("GOOGLE_API_KEY environment variable not set")

# Initialize Gemini
genai.configure(api_key=api_key)

# Test both available models
models = ["gemini-2.0-flash-thinking-exp-01-21", "gemini-pro"]

for model_name in models:
    try:
        logger.info(f"\nTesting model: {model_name}")
        model = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content("Hello, are you operational?")
        logger.info(f"Response: {response.text}")
    except Exception as e:
        logger.error(f"Error with {model_name}: {str(e)}")
