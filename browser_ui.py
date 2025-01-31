# browser_ui.py
import os
import sys
import logging
import traceback
import json
from datetime import datetime
import codecs
import uuid
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTextEdit, QLabel, QSplitter
)
from PyQt6.QtCore import QUrl, QTimer, Qt
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings, QWebEnginePage
from PyQt6.QtGui import QPixmap, QTextCursor
from gemini_integration import GeminiIntegration
import requests
import glob

# Configure logging with proper encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gemini.log', 'a', 'utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CustomWebEnginePage(QWebEnginePage):
    """Custom QWebEnginePage class."""
    def __init__(self, profile, parent=None):
        try:
            logger.debug("Initializing CustomWebEnginePage")
            super().__init__(profile, parent)
            logger.debug("CustomWebEnginePage super() initialized")
            
            self.loadFinished.connect(self._on_load_finished)
            logger.debug("loadFinished signal connected")
            
            logger.info("CustomWebEnginePage initialization complete")
        except Exception as e:
            logger.error(f"Error in CustomWebEnginePage.__init__: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def _on_load_finished(self, ok):
        """Handle page load completion."""
        try:
            logger.debug(f"Page load finished: {ok}")
            if hasattr(self.parent(), '_page_loaded'):
                logger.debug("Calling parent._page_loaded")
                self.parent()._page_loaded(ok)
            else:
                logger.warning("Parent does not have _page_loaded method")
        except Exception as e:
            logger.error(f"Error in _on_load_finished: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def javaScriptConsoleMessage(self, level, message, line, source):
        """Handle JavaScript console messages."""
        try:
            level_str = {
                0: "INFO",
                1: "WARNING",
                2: "ERROR"
            }.get(level, "UNKNOWN")
            
            logger.debug(f"JS Console [{level_str}] {message} (line {line}, source: {source})")
            
            # Log errors to the chat history
            if level == 2:  # Error level
                self.chat_history.append(f"JavaScript Error: {message}")
                
        except Exception as e:
            logger.error(f"Error handling JavaScript console message: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def certificateError(self, error):
        """Handle SSL certificate errors."""
        try:
            logger.warning(f"Certificate error: {error.errorDescription()}")
            # Accept the certificate for now
            return True
        except Exception as e:
            logger.error(f"Error handling certificate error: {str(e)}")
            return False

    def javaScriptAlert(self, securityOrigin, msg):
        """Handle JavaScript alerts."""
        try:
            logger.info(f"JS Alert from {securityOrigin.toString()}: {msg}")
            return super().javaScriptAlert(securityOrigin, msg)
        except Exception as e:
            logger.error(f"Error handling JavaScript alert: {e}")
            return False

class BrowserApp(QMainWindow):
    """Main browser application window."""

    def __init__(self):
        """Initialize the browser application."""
        try:
            logger.debug("Initializing BrowserApp")
            super().__init__()
            
            # Set up Gemini integration
            logger.debug("Setting up Gemini integration")
            self.gemini = GeminiIntegration()
            logger.info("Gemini integration initialized")
            
            # Create main widget and layout
            logger.debug("Creating main widget and layout")
            main_widget = QWidget()
            self.setCentralWidget(main_widget)
            layout = QVBoxLayout(main_widget)
            
            # Create browser view
            logger.debug("Creating browser view")
            self.profile = QWebEngineProfile()
            self.profile.setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            
            self.browser = QWebEngineView()
            self.page = CustomWebEnginePage(self.profile, self)
            self.browser.setPage(self.page)
            
            # Create toolbar
            logger.debug("Creating toolbar")
            toolbar = QHBoxLayout()
            
            # Create navigation buttons with fixed actions
            logger.debug("Creating navigation buttons")
            back_btn = QPushButton("←")
            back_btn.setMaximumWidth(40)
            back_btn.clicked.connect(lambda: self.browser.page().triggerAction(QWebEnginePage.WebAction.Back))
            logger.debug("Back button created and connected")
            
            forward_btn = QPushButton("→")
            forward_btn.setMaximumWidth(40)
            forward_btn.clicked.connect(lambda: self.browser.page().triggerAction(QWebEnginePage.WebAction.Forward))
            logger.debug("Forward button created and connected")
            
            refresh_btn = QPushButton("⟳")
            refresh_btn.setMaximumWidth(40)
            refresh_btn.clicked.connect(lambda: self.browser.page().triggerAction(QWebEnginePage.WebAction.Reload))
            logger.debug("Refresh button created and connected")
            
            # Create URL bar
            logger.debug("Creating URL bar")
            self.url_bar = QLineEdit()
            self.url_bar.returnPressed.connect(self._navigate_to_url)
            logger.debug("URL bar created and connected")
            
            # Add items to toolbar
            toolbar.addWidget(back_btn)
            toolbar.addWidget(forward_btn)
            toolbar.addWidget(refresh_btn)
            toolbar.addWidget(self.url_bar)
            logger.debug("Toolbar items added")
            
            # Create chat interface
            logger.debug("Creating chat interface")
            chat_layout = QVBoxLayout()
            
            # Chat history
            self.chat_history = QTextEdit()
            self.chat_history.setReadOnly(True)
            chat_layout.addWidget(self.chat_history)
            
            # Screenshot display
            self.screenshot_label = QLabel()
            self.screenshot_label.setMaximumHeight(200)
            self.screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chat_layout.addWidget(self.screenshot_label)
            
            # Input field
            self.input_field = QLineEdit()
            self.input_field.returnPressed.connect(self._handle_user_input)
            chat_layout.addWidget(self.input_field)
            
            # Create splitter for browser and chat
            logger.debug("Creating splitter")
            splitter = QSplitter(Qt.Orientation.Horizontal)
            
            # Add browser container (with toolbar) to splitter
            browser_container = QWidget()
            browser_layout = QVBoxLayout(browser_container)
            browser_layout.addLayout(toolbar)
            browser_layout.addWidget(self.browser)
            splitter.addWidget(browser_container)
            
            # Add chat container to splitter
            chat_container = QWidget()
            chat_container.setLayout(chat_layout)
            splitter.addWidget(chat_container)
            
            # Set initial splitter sizes
            splitter.setSizes([600, 300])
            
            # Add splitter to main layout
            layout.addWidget(splitter)
            
            # Set window properties
            self.setWindowTitle("Gemini Web Browser")
            self.setGeometry(100, 100, 1024, 768)
            
            # Navigate to default page
            self.browser.setUrl(QUrl("https://www.google.com"))
            
            logger.info("BrowserApp initialization complete")
            
        except Exception as e:
            logger.error(f"Error in BrowserApp.__init__: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def _page_loaded(self, ok):
        """Handle page load completion."""
        try:
            logger.info(f"Page loaded: {ok}")
            if ok:
                # Wait a bit for JavaScript to initialize
                QTimer.singleShot(1000, self._check_pending_actions)
        except Exception as e:
            logger.error(f"Error in _page_loaded: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _check_pending_actions(self):
        """Check and execute any pending actions."""
        try:
            if hasattr(self, 'pending_search') and self.pending_search:
                logger.info(f"Executing pending search: {self.pending_search}")
                self._execute_search()
        except Exception as e:
            logger.error(f"Error checking pending actions: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _navigate_to_url(self):
        """Navigate to the URL entered in the URL bar."""
        try:
            url = self.url_bar.text()
            logger.debug(f"Navigating to URL: {url}")
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                logger.debug(f"Added https:// prefix: {url}")
            self.browser.setUrl(QUrl(url))
        except Exception as e:
            logger.error(f"Error in _navigate_to_url: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _handle_user_input(self):
        """Handle user input from the chat interface."""
        try:
            user_input = self.input_field.text()
            logger.debug(f"Handling user input: {user_input}")
            self.input_field.clear()
            self.chat_history.append(f"You: {user_input}")
            
            # Take screenshot before processing
            screenshot = self._take_screenshot()
            
            # Process the input
            if user_input.strip():
                try:
                    current_url = self.browser.url().toString()
                    response = self.gemini.process_request(user_input, current_url, screenshot)
                    if response:
                        self._handle_response(response)
                except Exception as e:
                    logger.error(f"Error processing request: {str(e)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    self.chat_history.append(f"Error: Failed to process request - {str(e)}")
            
        except Exception as e:
            logger.error(f"Error in _handle_user_input: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _handle_response(self, response):
        """Handle the response from Gemini."""
        try:
            if isinstance(response, dict):
                # Handle message
                if 'message' in response:
                    self.chat_history.append(f"Assistant: {response['message']}")
                
                # Handle actions
                if 'actions' in response:
                    for action in response['actions']:
                        action_type = action.get('action')
                        
                        if action_type == 'navigate':
                            url = action.get('url')
                            if url:
                                self.navigate_to(url)
                                
                        elif action_type == 'search':
                            value = action.get('value')
                            selector = action.get('selector')
                            if value:
                                self.perform_search(value, selector)
                                
                        elif action_type == 'click':
                            selector = action.get('selector')
                            if selector:
                                self.click_element(selector)
                                
                        elif action_type == 'respond':
                            message = action.get('message')
                            if message:
                                self.chat_history.append(f"Assistant: {message}")
                                
            else:
                # If response is just a string, display it
                self.chat_history.append(f"Assistant: {response}")
                
        except Exception as e:
            logger.error(f"Error handling response: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.chat_history.append(f"Error: {str(e)}")

    def navigate_to(self, url):
        """Navigate to a URL."""
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            logger.info(f"Navigating to: {url}")
            self.url_bar.setText(url)
            self.browser.setUrl(QUrl(url))
            self.browser.page().loadFinished.connect(lambda ok: 
                logger.info(f"Page load {'succeeded' if ok else 'failed'}: {url}"))
        except Exception as e:
            logger.error(f"Error navigating to {url}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.chat_history.append(f"Error navigating to {url}: {str(e)}")

    def perform_search(self, value, selector=None):
        """Perform a search using the specified value and selector."""
        try:
            if not selector:
                selector = "input[name='q']"  # Default to Google search
            
            logger.info(f"Performing search with value: {value}, selector: {selector}")
            
            # Store the search value for use after page load
            self.pending_search = value
            self.search_selector = selector
            
            # Execute search
            self._execute_search()
            
        except Exception as e:
            logger.error(f"Error performing search: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.chat_history.append(f"Error performing search: {str(e)}")

    def _execute_search(self):
        """Execute the pending search."""
        try:
            if not hasattr(self, 'pending_search') or not self.pending_search:
                logger.warning("No pending search to execute")
                return
            
            if not hasattr(self, 'search_selector'):
                logger.warning("No search selector available")
                return
                
            logger.info(f"Executing search with value: {self.pending_search}, selector: {self.search_selector}")
            
            js_code = """
            (function() {
                function findInteractiveElements() {
                    // Find all potentially interactive elements
                    const elements = {
                        inputs: Array.from(document.querySelectorAll('input[type="text"], input[type="search"], input:not([type]), textarea')),
                        searchForms: Array.from(document.querySelectorAll('form')).filter(form => {
                            const action = form.getAttribute('action') || '';
                            const inputs = form.querySelectorAll('input');
                            return action.includes('search') || 
                                   Array.from(inputs).some(input => input.name && input.name.includes('search') || 
                                   input.id && input.id.includes('search'));
                        }),
                        searchButtons: Array.from(document.querySelectorAll('button, input[type="submit"]')).filter(btn => {
                            const text = (btn.textContent || btn.value || '').toLowerCase();
                            return text.includes('search') || text.includes('find') || text.includes('go');
                        })
                    };
                    console.log('Found elements:', elements);
                    return elements;
                }

                function findBestInput(selector, elements) {
                    // First try the exact selector
                    let input = document.querySelector(selector);
                    if (input && input.offsetParent !== null) {
                        console.log('Found input with exact selector:', selector);
                        return input;
                    }

                    // Try to find the most relevant input
                    const allInputs = elements.inputs;
                    const visibleInputs = allInputs.filter(el => el.offsetParent !== null);
                    
                    if (!visibleInputs.length) {
                        console.error('No visible input elements found');
                        return null;
                    }

                    // Prioritize search inputs
                    const searchInputs = visibleInputs.filter(input => {
                        const attrs = [input.id, input.name, input.placeholder, input.className].map(a => (a || '').toLowerCase());
                        return attrs.some(attr => attr.includes('search') || attr.includes('query') || attr.includes('q'));
                    });

                    if (searchInputs.length) {
                        console.log('Found search input:', searchInputs[0]);
                        return searchInputs[0];
                    }

                    // Fall back to the first visible input
                    console.log('Using first visible input:', visibleInputs[0]);
                    return visibleInputs[0];
                }

                function findSubmitButton(input, elements) {
                    // First check if input is in a form
                    const form = input.form;
                    if (form) {
                        // Look for submit button in the form
                        const formButton = form.querySelector('button[type="submit"], input[type="submit"]');
                        if (formButton) {
                            console.log('Found submit button in form:', formButton);
                            return formButton;
                        }
                    }

                    // Look for nearby buttons
                    const searchButtons = elements.searchButtons;
                    if (searchButtons.length) {
                        console.log('Found search button:', searchButtons[0]);
                        return searchButtons[0];
                    }

                    return null;
                }

                function submitSearch(input, button) {
                    if (button) {
                        console.log('Clicking submit button');
                        button.click();
                    } else if (input.form) {
                        console.log('Submitting form');
                        input.form.submit();
                    } else {
                        console.log('Simulating Enter key');
                        input.dispatchEvent(new KeyboardEvent('keydown', {
                            key: 'Enter',
                            code: 'Enter',
                            keyCode: 13,
                            which: 13,
                            bubbles: true,
                            cancelable: true
                        }));
                    }
                }

                async function fillAndSubmit(selector, value) {
                    const elements = findInteractiveElements();
                    const input = findBestInput(selector, elements);
                    
                    if (!input) {
                        console.error('Could not find suitable input');
                        return false;
                    }

                    // Focus and fill the input
                    input.focus();
                    input.value = value;

                    // Dispatch events
                    ['input', 'change'].forEach(eventType => {
                        input.dispatchEvent(new Event(eventType, { bubbles: true }));
                    });

                    // Find and click submit button
                    const button = findSubmitButton(input, elements);
                    submitSearch(input, button);

                    return true;
                }

                return fillAndSubmit(%s, %s);
            })();
            """
            
            # Format the JavaScript code with the selector and value
            formatted_js = js_code % (json.dumps(self.search_selector), json.dumps(self.pending_search))
            
            # Execute the search
            self.browser.page().runJavaScript(formatted_js, self._handle_search_result)
            
        except Exception as e:
            logger.error(f"Error executing search: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.chat_history.append(f"Error executing search: {str(e)}")

    def _handle_search_result(self, result):
        """Handle the result of a search action."""
        try:
            if result:
                logger.info("Search executed successfully")
                self.pending_search = None
                self.search_selector = None
            else:
                logger.error("Failed to execute search")
                self.chat_history.append("Could not find search input")
                self.pending_search = None
                self.search_selector = None
        except Exception as e:
            logger.error(f"Error handling search result: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def navigate_to(self, url):
        """Navigate to a URL."""
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            logger.info(f"Navigating to: {url}")
            self.url_bar.setText(url)
            self.browser.setUrl(QUrl(url))
            self.browser.page().loadFinished.connect(lambda ok: 
                logger.info(f"Page load {'succeeded' if ok else 'failed'}: {url}"))
        except Exception as e:
            logger.error(f"Error navigating to {url}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.chat_history.append(f"Error navigating to {url}: {str(e)}")

    def click_element(self, selector):
        """Click an element using the specified selector."""
        try:
            logger.info(f"Clicking element with selector: {selector}")
            
            js_code = """
            (function() {
                function findElement(selector) {
                    return document.querySelector(selector);
                }

                function clickElement(element) {
                    // Focus the element
                    element.focus();
                    
                    // Create and dispatch events
                    const events = [
                        new MouseEvent('mouseover', { bubbles: true }),
                        new MouseEvent('mousedown', { bubbles: true }),
                        new MouseEvent('mouseup', { bubbles: true }),
                        new MouseEvent('click', { bubbles: true })
                    ];
                    
                    events.forEach(event => element.dispatchEvent(event));
                    
                    // If it's a link, navigate
                    if (element.tagName === 'A' && element.href) {
                        window.location.href = element.href;
                    }
                    
                    return true;
                }

                const element = findElement(%s);
                if (!element) {
                    console.error('Element not found');
                    return false;
                }
                
                if (!element.offsetParent) {
                    console.error('Element is not visible');
                    return false;
                }
                
                return clickElement(element);
            })();
            """
            
            # Execute the click
            self.browser.page().runJavaScript(js_code % json.dumps(selector), self._handle_click_result)
            
        except Exception as e:
            logger.error(f"Error clicking element: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.chat_history.append(f"Error clicking element: {str(e)}")

    def _handle_click_result(self, result):
        """Handle the result of a click action."""
        try:
            if result:
                logger.info("Click executed successfully")
            else:
                logger.error("Failed to execute click")
                self.chat_history.append("Could not find or click element")
        except Exception as e:
            logger.error(f"Error handling click result: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

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
            logger.error(traceback.format_exc())

    def closeEvent(self, event):
        """Handle application close."""
        try:
            logger.info("Closing application")
            event.accept()
        except Exception as e:
            logger.exception("Error closing application")
            logger.error(f"Traceback: {traceback.format_exc()}")
            event.accept()

    def _take_screenshot(self):
        """Take a screenshot of the browser view."""
        try:
            # Create screenshots directory if it doesn't exist
            if not os.path.exists('screenshots'):
                os.makedirs('screenshots')
                
            # Clean up old screenshots
            self._cleanup_screenshots()
                
            # Take new screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            screenshot_path = f"screenshots/screenshot_{timestamp}_{unique_id}.png"
            
            self.browser.grab().save(screenshot_path)
            logger.info(f"Screenshot saved: {screenshot_path}")
            return screenshot_path
            
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _cleanup_screenshots(self):
        """Clean up old screenshots."""
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
            logger.error(f"Traceback: {traceback.format_exc()}")

if __name__ == '__main__':
    try:
        logger.debug("Starting main application")
        app = QApplication(sys.argv)
        logger.debug("QApplication created")
        
        logger.debug("Creating BrowserApp instance")
        browser = BrowserApp()
        logger.debug("BrowserApp instance created")
        
        logger.debug("Showing browser window")
        browser.show()
        logger.debug("Browser window shown")
        
        logger.debug("Entering application event loop")
        sys.exit(app.exec())
    except Exception as e:
        logger.error(f"Error in main application: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)