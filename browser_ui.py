import os
import sys
import time
import json
import logging
import traceback
import uuid
import glob
import logging.handlers
from queue import Queue
from datetime import datetime

# Configure logging
log_file = 'browser.log'
max_bytes = 10 * 1024 * 1024  # 10MB
backup_count = 5

# Ensure log directory exists
log_dir = os.path.dirname(log_file)
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)

# Get module logger
logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, QTimer, QUrl
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
        QLineEdit, QPushButton, QTextEdit, QLabel, QScrollArea,
        QApplication, QMessageBox
    )
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
except ImportError as e:
    logger.critical(f"Failed to import Qt dependencies: {str(e)}")
    logger.critical("Please install PySide6 and QtWebEngine: pip install PySide6 PySide6-QtWebEngine")
    sys.exit(1)

try:
    from gemini_integration import GeminiIntegration
except ImportError as e:
    logger.critical(f"Failed to import Gemini integration: {str(e)}")
    sys.exit(1)

class BrowserWindow(QMainWindow):
    def __init__(self):
        """Initialize the browser window."""
        super().__init__()
        
        try:
            # Initialize Gemini integration first
            self.gemini = GeminiIntegration()
            if not self.gemini:
                raise ValueError("Failed to initialize Gemini integration")
            
            # Initialize state variables
            self.action_queue = Queue()  # Use Queue instead of list
            self.action_in_progress = False
            self.page_load_complete = True
            self._is_navigating = False
            self.last_screenshot = None
            self.js_callbacks = {}
            self.chat_history = []
            self.model_actions = []
            
            # Initialize UI components
            self.init_ui()
            
            # Start with Google
            self.navigate_to_url("https://www.google.com")
            
            # Start action processing timer
            self.action_timer = QTimer()
            self.action_timer.timeout.connect(self.process_next_action)
            self.action_timer.start(100)  # Check queue every 100ms
            
            logger.info("Browser window initialized successfully")
            
        except Exception as e:
            logger.critical(f"Error initializing browser window: {str(e)}")
            logger.critical(f"Traceback: {traceback.format_exc()}")
            QMessageBox.critical(None, "Error", f"Failed to initialize browser: {str(e)}")
            raise

    def process_input(self, input_text):
        """Process user input and queue resulting actions."""
        try:
            logger.info(f"Processing input: {input_text}")
            
            # Take screenshot of current page
            screenshot_path = self.take_screenshot()
            
            # Get current page info
            current_url = self.web_view.url().toString()
            page_title = self.web_view.page().title()
            page_info = {
                'url': current_url,
                'title': page_title
            }
            logger.info(f"Current page info: {page_info}")
            
            # Generate actions using Gemini
            try:
                actions = self.gemini.generate_actions_with_gemini(
                    user_input=input_text,
                    current_url=current_url,
                    screenshot_path=screenshot_path
                )
                logger.info(f"Generated actions: {actions}")
            except Exception as e:
                logger.error(f"Error generating actions: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                actions = [{"action": "respond", "message": "I encountered an error while processing your request. Please try again."}]
            
            # Queue actions for processing
            for action in actions:
                self.action_queue.put(action)
            
            # Update display
            self.update_model_actions_display()
            
        except Exception as e:
            logger.error(f"Error processing input: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.display_message('System', f"Error processing input: {str(e)}")

    def process_next_action(self):
        """Process the next action in the queue if available."""
        try:
            if not self.action_in_progress and not self.action_queue.empty():
                action = self.action_queue.get()
                self.action_in_progress = True
                self.process_action(action)
        except Exception as e:
            logger.error(f"Error processing next action: {str(e)}")
            self.action_in_progress = False

    def update_model_actions_display(self):
        """Update the model actions text display."""
        try:
            # Format actions for display
            display_text = "Current Actions:\n\n"
            for i, action in enumerate(self.model_actions, 1):
                display_text += f"{i}. {json.dumps(action, indent=2)}\n\n"
            
            # Update display
            self.model_actions_display.setText(display_text)
            
            # Scroll to bottom
            scrollbar = self.model_actions_display.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
        except Exception as e:
            logger.error(f"Error updating model actions display: {e}")

    def init_ui(self):
        """Initialize the UI."""
        try:
            # Create central widget and layout
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            
            # Create main layout
            main_layout = QHBoxLayout(central_widget)
            
            # Create browser section
            browser_section = QVBoxLayout()
            
            # Initialize web engine profile
            self.profile = QWebEngineProfile()
            self.profile.setHttpUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Add web view
            self.web_view = QWebEngineView()
            page = QWebEnginePage(self.profile, self.web_view)
            self.web_view.setPage(page)
            self.web_view.setMinimumWidth(800)
            
            # Connect signals
            self.web_view.loadFinished.connect(self.handle_load_finished)
            self.web_view.page().loadFinished.connect(self.handle_page_load_finished)
            self.web_view.urlChanged.connect(self.url_changed)
            
            # Add URL input
            self.url_input = QLineEdit()
            self.url_input.returnPressed.connect(self._handle_url_input)
            self.url_input.setPlaceholderText("Enter URL or search query...")
            
            # Enable copy/paste and keyboard navigation
            self.url_input.setContextMenuPolicy(Qt.DefaultContextMenu)
            self.url_input.setClearButtonEnabled(True)  # Add clear button
            
            # Add navigation buttons
            nav_layout = QHBoxLayout()
            
            # Back button
            self.back_button = QPushButton("Back")
            self.back_button.setEnabled(False)  # Initially disabled
            self.back_button.clicked.connect(lambda: self.web_view.back() if self.web_view.history().canGoBack() else None)
            self.back_button.setToolTip("Go back to previous page")
            
            # Forward button
            self.forward_button = QPushButton("Forward")
            self.forward_button.setEnabled(False)  # Initially disabled
            self.forward_button.clicked.connect(lambda: self.web_view.forward() if self.web_view.history().canGoForward() else None)
            self.forward_button.setToolTip("Go forward to next page")
            
            # Refresh button
            self.refresh_button = QPushButton("Refresh")
            self.refresh_button.clicked.connect(lambda: self.web_view.reload())
            self.refresh_button.setToolTip("Reload current page")
            
            # Stop button
            self.stop_button = QPushButton("Stop")
            self.stop_button.clicked.connect(lambda: self.web_view.stop())
            self.stop_button.setToolTip("Stop loading page")
            self.stop_button.setEnabled(False)  # Initially disabled
            
            # Add buttons to layout
            nav_layout.addWidget(self.back_button)
            nav_layout.addWidget(self.forward_button)
            nav_layout.addWidget(self.refresh_button)
            nav_layout.addWidget(self.stop_button)
            nav_layout.addWidget(self.url_input)
            
            # Add to browser section
            browser_section.addLayout(nav_layout)
            browser_section.addWidget(self.web_view)
            
            # Create chat section
            chat_section = QVBoxLayout()
            
            # Model actions display
            actions_label = QLabel("Model Actions:")
            self.model_actions_display = QTextEdit()
            self.model_actions_display.setReadOnly(True)
            self.model_actions_display.setMinimumWidth(400)
            self.model_actions_display.setMaximumHeight(200)
            
            # Chat history display
            chat_label = QLabel("Chat History:")
            self.chat_display = QTextEdit()
            self.chat_display.setReadOnly(True)
            self.chat_display.setMinimumWidth(400)
            
            # Chat input
            class ChatInput(QTextEdit):
                def __init__(self, parent=None):
                    super().__init__(parent)
                    self.parent = parent
                    
                def keyPressEvent(self, event):
                    # Handle Enter key (without Shift) for sending
                    if (event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter) and not event.modifiers() & Qt.ShiftModifier:
                        text = self.toPlainText().strip()
                        if text:
                            self.parent.process_input(text)
                            self.clear()
                        event.accept()
                    # Handle Shift+Enter for new line
                    elif (event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter) and event.modifiers() & Qt.ShiftModifier:
                        cursor = self.textCursor()
                        cursor.insertText("\n")
                        event.accept()
                    # Handle all other keys normally
                    else:
                        super().keyPressEvent(event)
            
            self.chat_input = ChatInput(self)
            self.chat_input.setMinimumWidth(400)
            self.chat_input.setMaximumHeight(100)
            self.chat_input.setPlaceholderText("Type your message here... (Enter to send, Shift+Enter for new line)")
            
            # Add send button
            self.send_button = QPushButton("Send")
            self.send_button.clicked.connect(self._handle_send_click)
            
            # Create chat input layout
            chat_input_layout = QHBoxLayout()
            chat_input_layout.addWidget(self.chat_input)
            chat_input_layout.addWidget(self.send_button)
            
            # Add to chat section
            chat_section.addWidget(actions_label)
            chat_section.addWidget(self.model_actions_display)
            chat_section.addWidget(chat_label)
            chat_section.addWidget(self.chat_display)
            chat_section.addLayout(chat_input_layout)
            
            # Add sections to main layout
            main_layout.addLayout(browser_section, stretch=2)
            main_layout.addLayout(chat_section, stretch=1)
            
            # Set window properties
            self.setWindowTitle("Gemini Web Browser")
            self.setGeometry(100, 100, 1600, 900)
            self.show()
            
        except Exception as e:
            logger.error(f"Error in init_ui: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            QMessageBox.critical(self, "Error", f"Failed to initialize UI: {str(e)}")

    def stop_actions(self):
        """Stop all current actions."""
        try:
            logger.info("Stopping all actions")
            self.action_queue.queue.clear()
            self.action_in_progress = False
            self.page_load_complete = True
            self._is_navigating = False
            self.model_actions.append("Stopped all actions.")
            
        except Exception as e:
            logger.error(f"Error stopping actions: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def navigate_to_url(self, url=None):
        """Navigate to a URL."""
        try:
            if url is None:
                url = self.url_input.text().strip()
            
            if not url:
                return
                
            # Add http:// if no protocol specified
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                
            logger.info(f"Navigating to URL: {url}")
            
            # Create QUrl object
            qurl = QUrl(url)
            if not qurl.isValid():
                logger.error(f"Invalid URL: {url}")
                return
                
            # Update URL input
            self.url_input.setText(url)
            
            # Set URL and start navigation
            self._is_navigating = True
            self.page_load_complete = False
            self.web_view.setUrl(qurl)
            
            # Update navigation buttons
            if hasattr(self, 'back_button'):
                self.back_button.setEnabled(self.web_view.history().canGoBack())
            if hasattr(self, 'forward_button'):
                self.forward_button.setEnabled(self.web_view.history().canGoForward())
            
        except Exception as e:
            logger.error(f"Error navigating to URL: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self._is_navigating = False
            self.page_load_complete = True
            self.action_in_progress = False

    def handle_load_finished(self, ok):
        """Handle page load finished."""
        try:
            logger.info(f"Page load finished: {ok}")
            if ok:
                # Update navigation buttons
                self.back_button.setEnabled(self.web_view.history().canGoBack())
                self.forward_button.setEnabled(self.web_view.history().canGoForward())
                self.stop_button.setEnabled(False)
                self.refresh_button.setEnabled(True)
                
                # Update loading state
                self._is_navigating = False
                self.page_load_complete = True
                self.action_in_progress = False
            else:
                logger.error("Page failed to load")
                self.display_message("System", "Failed to load page")
                
        except Exception as e:
            logger.error(f"Error in handle_load_finished: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self._is_navigating = False
            self.page_load_complete = True
            self.action_in_progress = False

    def handle_page_load_finished(self, ok):
        """Handle page object load finished."""
        try:
            if ok:
                # Update navigation buttons
                self.back_button.setEnabled(self.web_view.history().canGoBack())
                self.forward_button.setEnabled(self.web_view.history().canGoForward())
                self.stop_button.setEnabled(False)
                self.refresh_button.setEnabled(True)
                
                # Update loading state
                self._is_navigating = False
                self.page_load_complete = True
                self.action_in_progress = False
            else:
                logger.error("Page object failed to load")
                
        except Exception as e:
            logger.error(f"Error in handle_page_load_finished: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self._is_navigating = False
            self.page_load_complete = True
            self.action_in_progress = False

    def url_changed(self, qurl):
        """Handle URL changes."""
        try:
            url_str = qurl.toString()
            logger.info(f"URL changed to: {url_str}")
            
            # Update URL input
            if hasattr(self, 'url_input'):
                self.url_input.setText(url_str)
                self.url_input.setCursorPosition(0)
                
            # Store last URL
            self.last_url = url_str
            
            # Update navigation buttons
            self.back_button.setEnabled(self.web_view.history().canGoBack())
            self.forward_button.setEnabled(self.web_view.history().canGoForward())
            self.stop_button.setEnabled(True)
            self.refresh_button.setEnabled(True)
            
        except Exception as e:
            logger.error(f"Error in url_changed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
    def handle_download(self, download):
        """Handle download requests."""
        try:
            download.cancel()  # For now, we cancel downloads
        except Exception as e:
            logger.error(f"Error handling download: {str(e)}")

    def take_screenshot(self):
        """Take a screenshot of the current page."""
        try:
            # Create screenshots directory if it doesn't exist
            screenshots_dir = os.path.join(os.path.dirname(__file__), 'screenshots')
            if not os.path.exists(screenshots_dir):
                os.makedirs(screenshots_dir)
                
            # Clean up old screenshots
            screenshots = glob.glob(os.path.join(screenshots_dir, '*.png'))
            if len(screenshots) > 10:  # Keep only 10 most recent
                screenshots.sort(key=os.path.getmtime)
                for old_screenshot in screenshots[:-10]:
                    try:
                        os.remove(old_screenshot)
                        logger.info(f"Deleted old screenshot: {old_screenshot}")
                    except Exception as e:
                        logger.warning(f"Failed to delete screenshot: {e}")
                        
            # Take new screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            screenshot_path = os.path.join(screenshots_dir, f"screenshot_{timestamp}_{unique_id}.png")
            
            if not self.web_view.grab().save(screenshot_path):
                raise Exception("Failed to save screenshot")
                
            logger.info(f"Screenshot saved: {screenshot_path}")
            return screenshot_path
            
        except Exception as e:
            logger.error(f"Error taking screenshot: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def process_action(self, action):
        """Process a single action."""
        try:
            if not isinstance(action, dict):
                logger.error(f"Invalid action format (not a dict): {action}")
                self.display_message('System', "Error: Invalid action format")
                self.action_in_progress = False
                return

            action_type = action.get('action')
            if not action_type:
                logger.error(f"Action missing 'action' field: {action}")
                self.display_message('System', "Error: Action missing type")
                self.action_in_progress = False
                return

            logger.info(f"Processing action: {action_type}")
            
            if action_type == 'navigate':
                url = action.get('url', '')
                if not url:
                    logger.error("Navigate action missing URL")
                    self.display_message('System', "Error: Navigate action missing URL")
                    self.action_in_progress = False
                    return
                    
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                self.navigate_to_url(url)
                
            elif action_type == 'back':
                self.web_view.back()
                
            elif action_type == 'forward':
                self.web_view.forward()
                
            elif action_type == 'reload':
                self.web_view.reload()
                
            elif action_type == 'click':
                selector = action.get('selector')
                text = action.get('text')
                element_type = action.get('element_type')
                
                if not any([selector, text]):
                    logger.error("Click action missing selector or text")
                    self.display_message('System', "Error: Click action missing selector or text")
                    self.action_in_progress = False
                    return
                    
                self.execute_click(selector=selector, text=text, element_type=element_type)
                
            elif action_type == 'type' or action_type == 'enter_text':
                text = action.get('text')
                if not text:
                    logger.error("Type action missing text")
                    self.display_message('System', "Error: Type action missing text")
                    self.action_in_progress = False
                    return
                    
                selector = action.get('selector')
                element_type = action.get('element_type')
                placeholder = action.get('placeholder')
                self.enter_text(text, selector, element_type, placeholder)
                
            elif action_type == 'scroll':
                direction = action.get('direction')
                if not direction:
                    logger.error("Scroll action missing direction")
                    self.display_message('System', "Error: Scroll action missing direction")
                    self.action_in_progress = False
                    return
                    
                amount = action.get('amount')
                self.scroll_page(direction, amount)
                
            elif action_type == 'respond':
                message = action.get('message')
                if not message:
                    logger.error("Respond action missing message")
                    self.display_message('System', "Error: Respond action missing message")
                    self.action_in_progress = False
                    return
                    
                self.display_message('Assistant', message)
                
            else:
                logger.warning(f"Unknown action type: {action_type}")
                self.display_message('System', f"Error: Unknown action type '{action_type}'")
                
            # Mark action as complete
            self.action_in_progress = False
            
        except Exception as e:
            logger.error(f"Error processing action: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.display_message('System', f"Error: {str(e)}")
            self.action_in_progress = False

    def enter_text(self, text, selector=None, element_type=None, placeholder=None):
        """Enter text into an input field."""
        try:
            logger.info(f"Entering text: '{text}' into selector: '{selector}', type: '{element_type}', placeholder: '{placeholder}'")
            
            # Escape quotes in parameters
            if selector:
                selector = selector.replace("'", "\\'")
            if text:
                text = text.replace("'", "\\'")
            if element_type:
                element_type = element_type.replace("'", "\\'")
            if placeholder:
                placeholder = placeholder.replace("'", "\\'")
            
            # Build JavaScript to find and enter text
            js = """
            (function() {
                try {
                    let element = null;
                    
                    if ('%s') {
                        element = document.querySelector('%s');
                    }
                    
                    if (!element && '%s') {
                        let elements = Array.from(document.getElementsByTagName('%s'));
                        element = elements.find(el => {
                            let isInput = el.tagName.toLowerCase() === 'input';
                            let hasPlaceholder = el.placeholder && el.placeholder.includes('%s');
                            return isInput && hasPlaceholder;
                        });
                    }
                    
                    if (!element) {
                        let inputs = Array.from(document.querySelectorAll('input[type="text"], input[type="search"], textarea'));
                        element = inputs[0];  // Use first input as fallback
                    }
                    
                    if (element) {
                        element.focus();
                        element.value = '%s';
                        element.dispatchEvent(new Event('input', { bubbles: true }));
                        element.dispatchEvent(new Event('change', { bubbles: true }));
                        return JSON.stringify({ success: true, element: element.tagName });
                    }
                    
                    return JSON.stringify({ success: false, error: 'No suitable input element found' });
                    
                } catch (error) {
                    return JSON.stringify({ success: false, error: error.toString() });
                }
            })();
            """ % (selector or '', selector or '', element_type or '', element_type or '', placeholder or '', text)
            
            # Run JavaScript with proper callback signature
            self.web_view.page().runJavaScript(js, 0, lambda result: self.handle_text_result(result))
            
        except Exception as e:
            error_msg = f"Error entering text: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.display_message('System', error_msg)
            self.action_in_progress = False

    def handle_text_result(self, result):
        """Handle the result of text entry."""
        try:
            logger.info(f"Text entry result: {result}")
            
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON result: {result}")
                    self.display_message('System', "Failed to parse text entry result")
                    self.action_in_progress = False
                    return
            
            if isinstance(result, dict):
                if result.get('success'):
                    logger.info(f"Text entry successful into {result.get('element', 'unknown')} element")
                else:
                    error = result.get('error', 'Unknown error')
                    logger.error(f"Text entry failed: {error}")
                    self.display_message('System', f"Failed to enter text: {error}")
            else:
                logger.warning(f"Unexpected text entry result type: {type(result)}")
            
            # Mark action as complete
            self.action_in_progress = False
                
        except Exception as e:
            error_msg = f"Error handling text entry result: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.display_message('System', error_msg)
            self.action_in_progress = False

    def execute_click(self, selector=None, text=None, element_type=None):
        """Execute a click action on an element."""
        try:
            logger.info(f"Executing click. Selector: {selector}, Text: {text}, Type: {element_type}")
            
            # Escape quotes in parameters
            if selector:
                selector = selector.replace('"', '\\"').replace("'", "\\'")
            if text:
                text = text.replace('"', '\\"').replace("'", "\\'")
            if element_type:
                element_type = element_type.replace('"', '\\"').replace("'", "\\'")
            
            # Build JavaScript to find and click element
            js = """
            (function() {
                try {
                    let element = null;
                    
                    // First try direct selector
                    if ('%s') {
                        element = document.querySelector('%s');
                    }
                    
                    // Then try by text content
                    if (!element && '%s') {
                        const elements = document.querySelectorAll('button, input[type="submit"], input[type="button"], a, input[type="search"]');
                        element = Array.from(elements).find(el => {
                            const text = (el.textContent || '').trim();
                            const value = (el.value || '').trim();
                            const placeholder = (el.placeholder || '').trim();
                            const ariaLabel = (el.getAttribute('aria-label') || '').trim();
                            const title = (el.title || '').trim();
                            return text === '%s' || 
                                   value === '%s' || 
                                   placeholder === '%s' ||
                                   ariaLabel === '%s' ||
                                   title === '%s' ||
                                   text.toLowerCase().includes('%s'.toLowerCase()) ||
                                   value.toLowerCase().includes('%s'.toLowerCase());
                        });
                    }
                    
                    // Finally try by element type
                    if (!element && '%s') {
                        const elements = document.getElementsByTagName('%s');
                        element = Array.from(elements).find(el => {
                            const text = (el.textContent || '').trim();
                            const value = (el.value || '').trim();
                            return text.includes('%s') || value.includes('%s');
                        });
                    }
                    
                    if (element) {
                        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        
                        // For forms, try to submit if clicking doesn't work
                        const submitForm = () => {
                            const form = element.form || element.closest('form');
                            if (form) {
                                form.submit();
                                return true;
                            }
                            return false;
                        };
                        
                        try {
                            element.click();
                            
                            // If it's a search button and clicking didn't work, try form submit
                            if (element.type === 'submit' || element.type === 'search') {
                                setTimeout(submitForm, 100);
                            }
                            
                            return JSON.stringify({
                                success: true,
                                element: element.tagName,
                                text: element.textContent?.trim() || element.value?.trim() || ''
                            });
                        } catch (error) {
                            // If click fails, try form submit as fallback
                            if (submitForm()) {
                                return JSON.stringify({
                                    success: true,
                                    element: 'FORM',
                                    text: 'form submit'
                                });
                            }
                            throw error;
                        }
                    }
                    
                    return JSON.stringify({
                        success: false,
                        error: 'Element not found'
                    });
                    
                } catch (error) {
                    return JSON.stringify({
                        success: false,
                        error: error.toString()
                    });
                }
            })();
            """ % (
                selector or '', selector or '',
                text or '', text or '', text or '', text or '', text or '', text or '', text or '', text or '',
                element_type or '', element_type or '', text or '', text or ''
            )
            
            # Execute JavaScript with proper signature
            self.web_view.page().runJavaScript(js, 0, self.handle_click_result)
            
        except Exception as e:
            error_msg = f"Error executing click: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.display_message('System', error_msg)
            self.action_in_progress = False

    def handle_click_result(self, result):
        """Handle the result of a click action."""
        try:
            logger.info(f"Click result: {result}")
            
            # Handle null result
            if result is None:
                logger.info("Click completed with null result")
                self.action_in_progress = False
                return
            
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON result: {result}")
                    logger.error(f"JSON parse error: {str(e)}")
                    self.display_message('System', "Failed to click element")
                    self.action_in_progress = False
                    return
            
            if isinstance(result, dict):
                if result.get('success'):
                    element = result.get('element', 'unknown')
                    text = result.get('text', '')
                    logger.info(f"Click successful on {element} element with text: {text}")
                else:
                    error = result.get('error', 'Unknown error')
                    logger.error(f"Click failed: {error}")
                    self.display_message('System', f"Failed to click: {error}")
            else:
                logger.warning(f"Unexpected click result type: {type(result)}")
            
            # Mark action as complete
            self.action_in_progress = False
                
        except Exception as e:
            error_msg = f"Error handling click result: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.display_message('System', error_msg)
            self.action_in_progress = False

    def scroll_page(self, direction, amount=None):
        """Scroll the page in the specified direction."""
        try:
            if direction == "up":
                amount = amount or -300
            elif direction == "down":
                amount = amount or 300
            else:
                raise ValueError("Direction must be 'up' or 'down'")

            js = f"""
                (function() {{
                    window.scrollBy(0, {amount});
                    return true;
                }})();
            """
            
            self.web_view.page().runJavaScript(js, self._handle_scroll_result)
            
        except Exception as e:
            logger.error(f"Error scrolling page: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def get_page_elements(self):
        """Get information about interactive elements on the page."""
        try:
            js = """
                (function() {
                    const elements = [];
                    
                    // Get all interactive elements
                    const interactiveElements = document.querySelectorAll('a, button, input, textarea, select');
                    
                    interactiveElements.forEach(el => {
                        // Get element properties
                        const rect = el.getBoundingClientRect();
                        const isVisible = rect.width > 0 && rect.height > 0 && 
                                        window.getComputedStyle(el).display !== 'none' &&
                                        window.getComputedStyle(el).visibility !== 'hidden';
                        
                        if (isVisible) {
                            elements.push({
                                tag: el.tagName.toLowerCase(),
                                type: el.type || null,
                                text: el.textContent.trim(),
                                value: el.value || null,
                                placeholder: el.placeholder || null,
                                href: el.href || null,
                                id: el.id || null,
                                className: el.className || null,
                                position: {
                                    top: rect.top,
                                    left: rect.left,
                                    bottom: rect.bottom,
                                    right: rect.right
                                }
                            });
                        }
                    });
                    
                    return JSON.stringify(elements);
                })();
            """
            
            self.web_view.page().runJavaScript(js, self._handle_elements_result)
            
        except Exception as e:
            logger.error(f"Error getting page elements: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _handle_elements_result(self, result):
        """Handle the result of getting page elements."""
        try:
            if result:
                elements = json.loads(result)
                logger.info(f"Found {len(elements)} interactive elements")
                return elements
            else:
                logger.error("Failed to get page elements")
                return None
                
        except Exception as e:
            logger.error(f"Error handling elements result: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def display_message(self, sender, message):
        """Display a message in the chat."""
        try:
            # Format timestamp
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # Format the message with proper spacing and contrast
            if sender == "You":
                formatted_msg = f'<div style="color: #2196F3; margin: 8px 0;"><b>{sender}</b> ({timestamp})<br>{message}</div>'
            elif sender == "System":
                formatted_msg = f'<div style="color: #F44336; margin: 8px 0;"><b>{sender}</b> ({timestamp})<br>{message}</div>'
            else:
                formatted_msg = f'<div style="color: #4CAF50; margin: 8px 0;"><b>{sender}</b> ({timestamp})<br>{message}</div>'
            
            # Add message to history
            self.chat_history.append(formatted_msg)
            
            # Update chat display
            self.chat_display.setHtml("".join(self.chat_history))
            
            # Scroll to bottom
            self.chat_display.verticalScrollBar().setValue(
                self.chat_display.verticalScrollBar().maximum()
            )
            
        except Exception as e:
            logger.error(f"Error displaying message: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
    def _handle_url_input(self):
        """Handle URL input from the address bar."""
        try:
            url = self.url_input.text().strip()
            if not url:
                return
                
            # Check if it's a URL or search query
            if not url.startswith(('http://', 'https://')):
                # Check if it looks like a URL
                if any(url.startswith(prefix) for prefix in ['www.', 'ftp.']) or \
                   any(url.endswith(tld) for tld in ['.com', '.org', '.net', '.edu', '.gov', '.io']):
                    # Add https:// to likely URLs
                    url = 'https://' + (url if not url.startswith('www.') else url[4:])
                else:
                    # Treat as search query
                    url = f'https://www.google.com/search?q={"+".join(url.split())}'
                    
            # URL encode any non-ASCII characters
            from urllib.parse import quote
            url = quote(url, safe=':/?#[]@!$&\'()*+,;=')
                    
            self.navigate_to_url(url)
            
        except Exception as e:
            logger.error(f"Error handling URL input: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
    def _handle_send_click(self):
        """Handle send button click."""
        try:
            text = self.chat_input.toPlainText().strip()
            if text:
                self.process_input(text)
                self.chat_input.clear()
                self.chat_input.setFocus()  # Keep focus on input
        except Exception as e:
            logger.error(f"Error handling send click: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def cleanup_resources(self):
        """Clean up resources before exit."""
        try:
            # Stop action timer
            if hasattr(self, 'action_timer'):
                self.action_timer.stop()
            
            # Clear web view
            if hasattr(self, 'web_view'):
                self.web_view.setPage(None)
                self.web_view.deleteLater()
            
            # Clear profile
            if hasattr(self, 'profile'):
                self.profile.deleteLater()
            
            # Clean up Gemini integration
            if hasattr(self, 'gemini'):
                del self.gemini
            
            # Clean up screenshots
            screenshots_dir = os.path.join(os.path.dirname(__file__), 'screenshots')
            if os.path.exists(screenshots_dir):
                try:
                    for file in os.listdir(screenshots_dir):
                        file_path = os.path.join(screenshots_dir, file)
                        try:
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                        except Exception as e:
                            logger.warning(f"Failed to delete file {file_path}: {e}")
                    os.rmdir(screenshots_dir)
                except Exception as e:
                    logger.warning(f"Failed to clean up screenshots directory: {e}")
            
            # Clean up any remaining resources
            self.deleteLater()
            
        except Exception as e:
            logger.error(f"Error in cleanup: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")

if __name__ == '__main__':
    try:
        logger.info("Starting Gemini Web Browser")
        
        # Check Python version
        if sys.version_info < (3, 8):
            logger.critical("Python 3.8 or higher is required")
            sys.exit(1)
            
        # Create Qt application
        app = QApplication(sys.argv)
        
        # Enable high DPI scaling
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
            
        # Set application style
        app.setStyle('Fusion')
        
        # Create and show browser window
        browser = None
        try:
            browser = BrowserWindow()
            browser.show()
        except Exception as e:
            logger.critical(f"Failed to create browser window: {str(e)}")
            logger.critical(f"Traceback: {traceback.format_exc()}")
            if browser:
                try:
                    browser.cleanup_resources()
                except:
                    pass
            sys.exit(1)
        
        # Set up exception handling
        sys._excepthook = sys.excepthook
        def exception_hook(exctype, value, traceback):
            logger.error("Uncaught exception:", exc_info=(exctype, value, traceback))
            sys._excepthook(exctype, value, traceback)
            
            # Show error dialog for uncaught exceptions
            error_msg = f"An unexpected error occurred:\n\n{str(value)}"
            QMessageBox.critical(None, "Error", error_msg)
            
        sys.excepthook = exception_hook
        
        # Run application
        logger.info("Starting application event loop")
        exit_code = app.exec_()
        
        # Cleanup
        logger.info("Application exiting, cleaning up resources")
        if browser and hasattr(browser, 'cleanup_resources'):
            try:
                browser.cleanup_resources()
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")
                
        # Close logging handlers
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)
            
        sys.exit(exit_code)
        
    except Exception as e:
        logger.critical(f"Fatal error in main: {str(e)}")
        logger.critical(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)