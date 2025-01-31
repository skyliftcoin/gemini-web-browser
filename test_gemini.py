import os
import logging
import google.generativeai as genai
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_gemini():
    """Test basic Gemini functionality."""
    try:
        # Load and check API key
        load_dotenv()
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set")
            
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Initialize model
        model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp-01-21')
        
        # Test with simple prompt
        response = model.generate_content("Say 'Hello, I am working!' if you can receive this message.")
        
        if response and response.text:
            print(f"\nResponse: {response.text}")
            return True
            
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_gemini()
    print(f"\nTest {'succeeded' if success else 'failed'}!")
