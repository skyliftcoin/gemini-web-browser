# browser_ui.py
import os
import sys
import logging
import traceback
import json
from datetime import datetime
import codecs
import uuid
from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineScript
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTextEdit, QLabel, QSplitter
)
from PyQt6.QtGui import QPixmap, QTextCursor
from gemini_integration import GeminiIntegration
import requests
import glob
import tempfile
import time

# Configure logging with proper encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('browser.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CustomWebEnginePage(QWebEnginePage):
    """Custom web engine page with additional functionality."""
    
    def __init__(self, parent=None):
        super().__init__(QWebEngineProfile.defaultProfile(), parent)
        self._parent = parent  # Store parent reference

    def javaScriptConsoleMessage(self, level, message, line, source):
        """Handle JavaScript console messages."""
        logger.info(f"JS Console: {message}")
        if hasattr(self._parent, 'js_console_log'):
            self._parent.js_console_log(message)

    def certificateError(self, error):
        """Handle SSL certificate errors."""
        logger.warning(f"Certificate error: {error.errorDescription()}")
        return True  # Accept all certificates for now

    def javaScriptAlert(self, securityOrigin, msg):
        """Handle JavaScript alerts."""
        try:
            logger.info(f"JavaScript alert: {msg}")
            if hasattr(self._parent, 'chat_history'):
                self._parent.chat_history.append(f"Alert: {msg}")
            return True
        except Exception as e:
            logger.error(f"Error handling JavaScript alert: {e}")
            return False

class BrowserWindow(QMainWindow):
    """Main browser window."""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        """Initialize the UI."""
        try:
            # Set window properties
            self.setWindowTitle('Web Browser Assistant')
            self.setGeometry(100, 100, 1200, 800)
            
            # Create main layout
            main_layout = QVBoxLayout()
            
            # Create navigation toolbar
            nav_toolbar = QHBoxLayout()
            
            # Create browser view first
            self.browser = QWebEngineView()
            self.page = CustomWebEnginePage(self.browser)
            self.browser.setPage(self.page)
            
            # Connect signals
            self.browser.urlChanged.connect(self.update_url)
            self.page.loadFinished.connect(self.handle_load_finished)
            
            # Set default homepage
            self.default_url = 'https://www.google.com'
            self.browser.setUrl(QUrl(self.default_url))
            
            # Back button
            self.back_button = QPushButton('←')
            self.back_button.clicked.connect(self.browser.back)
            nav_toolbar.addWidget(self.back_button)
            
            # Forward button
            self.forward_button = QPushButton('→')
            self.forward_button.clicked.connect(self.browser.forward)
            nav_toolbar.addWidget(self.forward_button)
            
            # Refresh button
            self.refresh_button = QPushButton('↻')
            self.refresh_button.clicked.connect(self.browser.reload)
            nav_toolbar.addWidget(self.refresh_button)
            
            # Home button
            self.home_button = QPushButton('🏠')
            self.home_button.clicked.connect(self.reset_to_homepage)
            nav_toolbar.addWidget(self.home_button)
            
            # URL bar
            self.url_bar = QLineEdit()
            self.url_bar.returnPressed.connect(self.navigate_to_url)
            nav_toolbar.addWidget(self.url_bar)
            
            # Add navigation toolbar to main layout
            main_layout.addLayout(nav_toolbar)
            
            # Add browser to layout
            main_layout.addWidget(self.browser, stretch=1)
            
            # Create chat interface
            chat_layout = QHBoxLayout()
            
            # Chat history
            self.chat_history = QTextEdit()
            self.chat_history.setReadOnly(True)
            chat_layout.addWidget(self.chat_history)
            
            # Chat input
            input_layout = QVBoxLayout()
            self.chat_input = QLineEdit()
            self.chat_input.returnPressed.connect(self.send_message)
            input_layout.addWidget(self.chat_input)
            
            # Send button
            self.send_button = QPushButton('Send')
            self.send_button.clicked.connect(self.send_message)
            input_layout.addWidget(self.send_button)
            
            chat_layout.addLayout(input_layout)
            
            # Add chat interface to main layout
            main_layout.addLayout(chat_layout)
            
            # Create central widget and set layout
            central_widget = QWidget()
            central_widget.setLayout(main_layout)
            self.setCentralWidget(central_widget)
            
            # Initialize Gemini integration
            self.gemini = GeminiIntegration()
            logger.info("Gemini integration initialized")
            
            # Initialize action queue
            self.action_queue = []
            self.action_in_progress = False
            self.page_load_complete = True
            
            # Action timer
            self.action_timer = QTimer()
            self.action_timer.timeout.connect(self._process_action_queue)
            
        except Exception as e:
            logger.error(f"Error in BrowserWindow.init_ui: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
    def navigate_to_url(self, url=None):
        """Navigate to a URL"""
        try:
            if url is None:
                url = self.url_bar.text()
            
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            logger.info(f"Navigating to: {url}")
            self.browser.setUrl(QUrl(url))
            
        except Exception as e:
            logger.error(f"Error in navigate_to_url: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.chat_history.append(f"Error navigating to URL: {str(e)}")

    def update_url(self, url):
        """Update URL bar with current URL"""
        try:
            if hasattr(self, 'url_bar'):
                self.url_bar.setText(url.toString())
                self.url_bar.setCursorPosition(0)
        except Exception as e:
            logger.error(f"Error in update_url: {str(e)}")

    def send_message(self):
        """Send a message to Gemini."""
        try:
            # Get message from input
            message = self.chat_input.text().strip()
            if not message:
                return
                
            # Clear input
            self.chat_input.clear()
            
            # Add to chat history
            self.chat_history.append(f"You: {message}")
            
            # Get current URL
            current_url = self.browser.url().toString()
            
            # Take screenshot
            screenshot = None
            if current_url:
                screenshot = self.capture_screenshot()
            
            # Process with Gemini
            response = self.gemini.process_request(message, current_url, screenshot)
            
            # Handle response
            if isinstance(response, str):
                self.chat_history.append(f"Assistant: {response}")
            elif isinstance(response, dict):
                # First handle any message
                if 'message' in response:
                    # Parse JSON strings in message
                    try:
                        message_lines = response['message'].strip().split('\n')
                        for line in message_lines:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                # Try to parse as JSON
                                action = json.loads(line)
                                if isinstance(action, dict) and 'action' in action:
                                    self.queue_action(action)
                                else:
                                    self.chat_history.append(f"Assistant: {line}")
                            except json.JSONDecodeError:
                                # Not JSON, treat as normal message
                                self.chat_history.append(f"Assistant: {line}")
                    except Exception as e:
                        logger.error(f"Error parsing message: {e}")
                        self.chat_history.append(f"Assistant: {response['message']}")
                
                # Then handle any explicit actions
                if 'actions' in response and isinstance(response['actions'], list):
                    for action in response['actions']:
                        if isinstance(action, dict) and 'action' in action:
                            self.queue_action(action)
            else:
                logger.warning(f"Invalid response type: {type(response)}")
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.chat_history.append(f"Error: {str(e)}")

    def queue_action(self, action_data):
        """Add an action to the queue for processing."""
        try:
            if not isinstance(action_data, dict):
                logger.error(f"Invalid action data type: {type(action_data)}")
                return False
                
            action_type = action_data.get('action')
            if not action_type:
                logger.error("No action type specified")
                return False
                
            logger.info(f"Queueing action: {action_data}")
            self.action_queue.append(action_data)
            
            # Start processing if not already running
            if not self.action_timer.isActive():
                self.action_timer.start()
            
            return True
            
        except Exception as e:
            logger.error(f"Error queueing action: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def _process_action_queue(self):
        """Process the next action in the queue if possible."""
        try:
            if self.action_in_progress or not self.page_load_complete:
                return
                
            if not self.action_queue:
                logger.info("No actions in queue")
                self.action_timer.stop()
                return
                
            self.action_in_progress = True
            
            # Get next action
            action = self.action_queue.pop(0)
            logger.info(f"Processing next action: {action}")
            
            # Process action
            success = self.process_action(action)
            if not success:
                logger.error(f"Failed to process action: {action}")
                self.chat_history.append("Error: Failed to execute action")
            
            # Reset action state
            self.action_in_progress = False
            
            # Process next action if available
            if self.action_queue:
                self.action_timer.start()
                
        except Exception as e:
            logger.error(f"Error processing action queue: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.action_in_progress = False
            self.action_timer.stop()

    def process_action(self, action_data):
        """Process a single action from the model."""
        try:
            logger.info(f"Processing action: {action_data}")
            
            if not isinstance(action_data, dict):
                logger.error(f"Invalid action data type: {type(action_data)}")
                return False
            
            action_type = action_data.get('action')
            if not action_type:
                logger.error("No action type specified")
                return False
            
            if action_type == 'navigate':
                url = action_data.get('url', '')
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                self.navigate_to_url(url)
                return True
                
            elif action_type == 'search':
                value = action_data.get('value', '')
                
                # Run JavaScript to fill input and submit
                js_code = f"""
                (function() {{
                    // Try common search input selectors
                    const selectors = [
                        'input[type="search"]',
                        'input[type="text"]',
                        'input[name="q"]',
                        'input[name="query"]',
                        'input[name="search"]',
                        'input[aria-label*="search" i]',
                        'input[placeholder*="search" i]',
                        'input'
                    ];
                    
                    let input = null;
                    for (const selector of selectors) {{
                        const inputs = Array.from(document.querySelectorAll(selector));
                        const visibleInputs = inputs.filter(el => {{
                            const style = window.getComputedStyle(el);
                            return style.display !== 'none' && style.visibility !== 'hidden' && el.offsetParent !== null;
                        }});
                        if (visibleInputs.length > 0) {{
                            input = visibleInputs[0];
                            break;
                        }}
                    }}
                    
                    if (!input) {{
                        console.log('No search input found');
                        return false;
                    }}
                    
                    // Focus and fill the input
                    input.focus();
                    input.value = "{value}";
                    
                    // Trigger events
                    input.dispatchEvent(new Event('focus'));
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    
                    // Try to find and click a submit button
                    let submitted = false;
                    
                    // First try the closest form
                    const form = input.closest('form');
                    if (form) {{
                        const submitButton = form.querySelector('button[type="submit"], input[type="submit"]');
                        if (submitButton) {{
                            submitButton.click();
                            submitted = true;
                        }} else {{
                            // If no submit button, try submitting the form directly
                            form.submit();
                            submitted = true;
                        }}
                    }}
                    
                    // If no form submission worked, try to find a search button near the input
                    if (!submitted) {{
                        const searchButtons = Array.from(document.querySelectorAll('button')).filter(button => {{
                            const text = button.textContent.toLowerCase();
                            return text.includes('search') || text.includes('go') || text.includes('find');
                        }});
                        
                        if (searchButtons.length > 0) {{
                            searchButtons[0].click();
                            submitted = true;
                        }}
                    }}
                    
                    // If still no submission, try pressing Enter
                    if (!submitted) {{
                        input.dispatchEvent(new KeyboardEvent('keypress', {{ key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }}));
                    }}
                    
                    return true;
                }})();
                """
                
                def handle_search_result(result):
                    if result:
                        logger.info(f"Successfully executed search for: {value}")
                    else:
                        logger.warning(f"Failed to execute search for: {value}")
                        self.chat_history.append("Error: Could not find search input")
                
                self.page.runJavaScript(js_code, handle_search_result)
                return True
                
            elif action_type == 'click':
                value = action_data.get('value', '')
                
                # Run JavaScript to find and click element
                js_code = f"""
                (function() {{
                    // Find all clickable elements
                    const elements = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"], a'));
                    
                    // Filter for visible elements
                    const visibleElements = elements.filter(el => {{
                        const style = window.getComputedStyle(el);
                        return style.display !== 'none' && style.visibility !== 'hidden' && el.offsetParent !== null;
                    }});
                    
                    // Try to find element with matching text
                    const targetElement = visibleElements.find(el => {{
                        const text = (el.textContent || el.value || '').toLowerCase();
                        return text.includes("{value}".toLowerCase());
                    }});
                    
                    if (targetElement) {{
                        targetElement.click();
                        return true;
                    }}
                    
                    return false;
                }})();
                """
                
                def handle_click_result(result):
                    if result:
                        logger.info(f"Successfully clicked element with text: {value}")
                    else:
                        logger.warning(f"Could not find clickable element with text: {value}")
                        self.chat_history.append("Error: Could not find element to click")
                
                self.page.runJavaScript(js_code, handle_click_result)
                return True
                
            elif action_type == 'respond':
                message = action_data.get('message', '')
                if message:
                    self.chat_history.append(f"Assistant: {message}")
                return True
                
            else:
                logger.error(f"Unknown action type: {action_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing action: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def js_console_log(self, message):
        """Handle console.log messages from JavaScript."""
        logger.info(f"JS Console: {message}")

    def handle_js_result(self, result):
        """Handle the result of JavaScript execution."""
        try:
            if result is None:
                # Still trying, do nothing
                pass
            elif result:
                logger.info("JavaScript execution successful")
                if hasattr(self, 'pending_search'):
                    self.pending_search = None
                    self.search_selector = None
            else:
                logger.warning("JavaScript execution failed")
                if hasattr(self, 'pending_search'):
                    self.chat_history.append("Could not find search input")
                    self.pending_search = None
                    self.search_selector = None
        except Exception as e:
            logger.error(f"Error handling JavaScript result: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def handle_load_finished(self, ok):
        """Handle page load finished event."""
        try:
            if ok:
                logger.info("Page loaded successfully")
                self.page_load_complete = True
                self.capture_and_send_screenshot()
                
                # Continue processing actions
                QTimer.singleShot(1000, self._process_action_queue)
            else:
                logger.error("Page failed to load")
                self.chat_history.append("Error: Page failed to load")
                self.page_load_complete = True
                
        except Exception as e:
            logger.error(f"Error in handle_load_finished: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.page_load_complete = True

    def _take_screenshot(self):
        """Take a screenshot of the browser view."""
        try:
            # Create screenshots directory if it doesn't exist
            if not os.path.exists('screenshots'):
                os.makedirs('screenshots')
            
            # Clean up old screenshots
            self._cleanup_old_screenshots()
            
            # Take new screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            screenshot_path = f"screenshots/screenshot_{timestamp}_{unique_id}.png"
            
            # Take screenshot of browser view
            self.browser.grab().save(screenshot_path)
            logger.info(f"Screenshot saved: {screenshot_path}")
            return screenshot_path
            
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _cleanup_old_screenshots(self):
        """Clean up old screenshot files"""
        try:
            if not os.path.exists('screenshots'):
                return
            
            # Get list of screenshots
            screenshots = glob.glob('screenshots/*.png')
            
            # Sort by modification time
            screenshots.sort(key=os.path.getmtime)
            
            # Keep only the 10 most recent screenshots
            max_screenshots = 10
            if len(screenshots) > max_screenshots:
                for screenshot in screenshots[:-max_screenshots]:
                    try:
                        os.remove(screenshot)
                        logger.info(f"Deleted old screenshot: {screenshot}")
                    except Exception as e:
                        logger.warning(f"Failed to delete screenshot {screenshot}: {e}")
            
        except Exception as e:
            logger.error(f"Error cleaning up screenshots: {e}")

    def capture_and_send_screenshot(self):
        """Capture screenshot and send to chat history"""
        try:
            screenshot_path = self._take_screenshot()
            if screenshot_path and os.path.exists(screenshot_path):
                self.chat_history.append(f"\nScreenshot saved: {screenshot_path}")
                logger.info(f"Screenshot captured and saved to {screenshot_path}")
            else:
                logger.warning("Failed to capture screenshot")
                
        except Exception as e:
            logger.error(f"Error capturing screenshot: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
    def capture_screenshot(self):
        """Capture screenshot"""
        try:
            # Create screenshots directory if it doesn't exist
            if not os.path.exists('screenshots'):
                os.makedirs('screenshots')
            
            # Clean up old screenshots
            self._cleanup_old_screenshots()
            
            # Take new screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            screenshot_path = f"screenshots/screenshot_{timestamp}_{unique_id}.png"
            
            # Take screenshot of browser view
            self.browser.grab().save(screenshot_path)
            logger.info(f"Screenshot saved: {screenshot_path}")
            return screenshot_path
            
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def reset_to_homepage(self):
        """Reset to homepage"""
        try:
            self.browser.setUrl(QUrl(self.default_url))
        except Exception as e:
            logger.error(f"Error resetting to homepage: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def closeEvent(self, event):
        """Handle application close."""
        try:
            logger.info("Closing application")
            event.accept()
        except Exception as e:
            logger.exception("Error closing application")
            logger.error(f"Traceback: {traceback.format_exc()}")
            event.accept()

if __name__ == '__main__':
    try:
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('browser.log'),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger(__name__)
        
        # Create application
        logger.debug("Starting main application")
        app = QApplication(sys.argv)
        
        # Create and show browser window
        logger.debug("Creating browser window")
        browser = BrowserWindow()
        browser.show()
        
        # Enter event loop
        logger.debug("Entering application event loop")
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)