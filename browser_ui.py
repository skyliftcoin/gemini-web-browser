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
            self.page_load_complete = False  # Reset page load state
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
                    try:
                        message_lines = response['message'].strip().split('\n')
                        processed_actions = set()  # Track processed actions
                        for line in message_lines:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                # Try to parse as JSON
                                action = json.loads(line)
                                if isinstance(action, dict) and 'action' in action:
                                    # Create unique key for action
                                    action_key = f"{action['action']}:{action.get('value', '')}:{action.get('url', '')}"
                                    if action_key not in processed_actions:
                                        self.queue_action(action)
                                        processed_actions.add(action_key)
                                else:
                                    self.chat_history.append(f"Assistant: {line}")
                            except json.JSONDecodeError:
                                # Not JSON, treat as normal message
                                self.chat_history.append(f"Assistant: {line}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        self.chat_history.append(f"Error processing message: {str(e)}")
        except Exception as e:
            logger.error(f"Error in send_message: {e}")
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
            if self.action_in_progress:
                logger.debug("Action in progress, waiting...")
                return
                
            if not self.page_load_complete:
                logger.debug("Page still loading, waiting...")
                return
                
            if not self.action_queue:
                logger.info("No actions in queue")
                self.action_timer.stop()
                return
                
            self.action_in_progress = True
            
            # Get next action
            action = self.action_queue[0]  # Peek at next action without removing
            logger.info(f"Processing next action: {action}")
            
            # Process action
            success = self.process_action(action)
            if success:
                self.action_queue.pop(0)  # Only remove if successful
                logger.info("Action processed successfully")
            else:
                logger.error(f"Failed to process action: {action}")
                self.chat_history.append("Error: Failed to execute action")
                self.action_queue.pop(0)  # Remove failed action to prevent blocking
        
            # Reset action state
            self.action_in_progress = False
            
            # Process next action if available
            if self.action_queue:
                QTimer.singleShot(500, self._process_action_queue)  # Schedule next action with delay
            
        except Exception as e:
            logger.error(f"Error processing action queue: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.action_in_progress = False
            if self.action_queue:
                self.action_queue.pop(0)  # Remove problematic action

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
                (async function() {{
                    try {{
                        // Enhanced element finder with more selectors
                        function findSearchInput() {{
                            // Common search input selectors
                            const searchSelectors = [
                                // Standard search inputs
                                'input[type="search"]',
                                'input[type="text"]',
                                'input[name="q"]',
                                'input[name="query"]',
                                'input[name="search"]',
                                'input[name="symbol"]', // For trading platforms
                                'input[name="ticker"]', // For trading platforms
                                
                                // Inputs with search-related attributes
                                'input[placeholder*="search" i]',
                                'input[placeholder*="symbol" i]',
                                'input[placeholder*="ticker" i]',
                                'input[aria-label*="search" i]',
                                'input[title*="search" i]',
                                
                                // Trading platform specific
                                '.tv-search-row__input input',  // TradingView
                                '.js-search-input',             // Common class
                                '#symbol-search',               // Common ID
                                
                                // Common e-commerce search
                                '#gh-ac',                       // eBay
                                '#twotabsearchtextbox',         // Amazon
                                'input[name="st"]',             // Common store search
                                
                                // Fallbacks
                                'textarea[placeholder*="search" i]',
                                'input[role="searchbox"]',
                                'input[role="combobox"]',
                                '[contenteditable="true"]',
                                'input'
                            ];
                            
                            // Try each selector
                            for (const selector of searchSelectors) {{
                                const elements = document.querySelectorAll(selector);
                                for (const el of elements) {{
                                    const style = window.getComputedStyle(el);
                                    const rect = el.getBoundingClientRect();
                                    const isVisible = style.display !== 'none' && 
                                                   style.visibility !== 'hidden' && 
                                                   el.offsetParent !== null &&
                                                   rect.width > 0 &&
                                                   rect.height > 0;
                                    
                                    if (isVisible) {{
                                        console.log('Found search input:', el);
                                        return el;
                                    }}
                                }}
                            }}
                            return null;
                        }}

                        // Find search input
                        const searchInput = findSearchInput();
                        if (!searchInput) {{
                            throw new Error('No search input found');
                        }}

                        // Focus and fill the input
                        searchInput.focus();
                        searchInput.value = "{value}";
                        searchInput.dispatchEvent(new Event('input', {{ bubbles: true }}));

                        // Try to find and click a search button
                        const searchButtonSelectors = [
                            'button[type="submit"]',
                            'input[type="submit"]',
                            'button[aria-label*="search" i]',
                            'button[title*="search" i]',
                            '.search-button',
                            '.searchButton',
                            '#search-button',
                            '[role="search"] button'
                        ];

                        let searchButton = null;
                        for (const selector of searchButtonSelectors) {{
                            const button = document.querySelector(selector);
                            if (button) {{
                                const style = window.getComputedStyle(button);
                                if (style.display !== 'none' && style.visibility !== 'hidden') {{
                                    searchButton = button;
                                    break;
                                }}
                            }}
                        }}

                        // Click the search button if found, otherwise submit the form
                        if (searchButton) {{
                            searchButton.click();
                        }} else {{
                            const form = searchInput.closest('form');
                            if (form) {{
                                form.submit();
                            }} else {{
                                searchInput.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }}));
                            }}
                        }}

                        return {{
                            success: true,
                            message: `Successfully filled search input with: {value}`,
                            details: {{
                                inputType: searchInput.type,
                                inputName: searchInput.name,
                                inputId: searchInput.id
                            }}
                        }};
                    }} catch (error) {{
                        console.error('Search error:', error);
                        return {{
                            success: false,
                            error: error.toString(),
                            details: {{ message: error.message }}
                        }};
                    }}
                }})();
                """

                def handle_search_result(result):
                    if isinstance(result, dict):
                        if result.get('success'):
                            logger.info(f"Search successful: {result.get('message', '')}")
                            logger.info(f"Input details: {result.get('details', {})}")
                        else:
                            error = result.get('error', 'Unknown error')
                            details = result.get('details', {})
                            logger.error(f"Search failed: {error}")
                            logger.error(f"Error details: {details}")
                            self.chat_history.append(f"Error: {error}")
                    else:
                        logger.error(f"Unexpected result type: {type(result)}")
                        self.chat_history.append("Error: Unexpected response type")

                self.page.runJavaScript(js_code, handle_search_result)
                return True
                
            elif action_type == 'click':
                value = action_data.get('value', '')
                
                # Run JavaScript to find and click element
                js_code = f"""
                (async function() {{
                    try {{
                        // Platform-specific selectors for TradingView
                        const tradingViewSelectors = [
                            '.tv-symbol-price-quote__name',  // Symbol name
                            '.tv-category-header__title',    // Section headers
                            '.tv-symbol-header__text',       // Symbol header
                            '.tv-screener__symbol',          // Screener symbols
                            '.tv-chart-view__title',         // Chart title
                            '.tv-dialog__title',             // Dialog titles
                            '.tv-market-status__label',      // Market status
                            '.js-button-text',               // Button text
                            '.tv-control-input__input'       // Input controls
                        ];
                        
                        // Common clickable elements
                        const commonSelectors = [
                            'a', 'button', 'input[type="submit"]', 'input[type="button"]',
                            '[role="button"]', '[tabindex]', '[role="link"]', '[role="tab"]',
                            '[role="menuitem"]'
                        ];
                        
                        // Combine all selectors
                        const allSelectors = [...tradingViewSelectors, ...commonSelectors];
                        
                        // Find all potential elements
                        const elements = Array.from(document.querySelectorAll(allSelectors.join(',')));
                        let targetElement = null;
                        
                        // Find visible element with matching text
                        for (const el of elements) {{
                            const style = window.getComputedStyle(el);
                            const rect = el.getBoundingClientRect();
                            const isVisible = style.display !== 'none' && 
                                           style.visibility !== 'hidden' && 
                                           el.offsetParent !== null &&
                                           rect.width > 0 &&
                                           rect.height > 0;
                            
                            if (!isVisible) continue;
                            
                            // Check text content and attributes
                            const elementText = (
                                el.textContent?.trim() ||
                                el.value?.trim() ||
                                el.getAttribute('aria-label')?.trim() ||
                                el.getAttribute('title')?.trim() ||
                                el.getAttribute('alt')?.trim() ||
                                el.getAttribute('data-symbol')?.trim() || // For TradingView symbols
                                el.getAttribute('data-name')?.trim() ||   // For TradingView elements
                                ''
                            ).toLowerCase();
                            
                            const searchText = "{value}".toLowerCase();
                            if (elementText.includes(searchText)) {{
                                targetElement = el;
                                break;
                            }}
                        }}
                        
                        if (!targetElement) {{
                            throw new Error(`No clickable element found with text: {value}`);
                        }}
                        
                        // Scroll element into view
                        targetElement.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        await new Promise(resolve => setTimeout(resolve, 500));
                        
                        // Click the element
                        targetElement.focus();
                        targetElement.click();
                        
                        // For TradingView, also try to trigger a custom event
                        if (window.TradingView) {{
                            targetElement.dispatchEvent(new CustomEvent('tv-action'));
                        }}
                        
                        return {{ 
                            success: true, 
                            message: `Successfully clicked element with text: {value}`,
                            details: {{
                                tagName: targetElement.tagName,
                                className: targetElement.className,
                                id: targetElement.id
                            }}
                        }};
                    }} catch (error) {{
                        console.error('Click error:', error);
                        return {{ 
                            success: false, 
                            error: error.toString(),
                            details: {{ message: error.message }}
                        }};
                    }}
                }})();
                """
                
                def handle_click_result(result):
                    if isinstance(result, dict):
                        if result.get('success'):
                            logger.info(f"Click successful: {result.get('message', '')}")
                            logger.info(f"Clicked element details: {result.get('details', {})}")
                        else:
                            error = result.get('error', 'Unknown error')
                            details = result.get('details', {})
                            logger.error(f"Click failed: {error}")
                            logger.error(f"Error details: {details}")
                            self.chat_history.append(f"Error: {error}")
                    else:
                        logger.error(f"Unexpected result type: {type(result)}")
                        self.chat_history.append("Error: Unexpected response type")
                
                self.page.runJavaScript(js_code, handle_click_result)
                return True
                
            elif action_type == 'respond':
                message = action_data.get('message', '')
                if message:
                    self.chat_history.append(f"Assistant: {message}")
                return True
                
            elif action_type == 'fill':
                # Fill a form field by label or placeholder
                field = action_data.get('field', '')
                value = action_data.get('value', '')
                
                js_code = f"""
                (async function() {{
                    try {{
                        // Find form field by label or placeholder
                        const field = document.evaluate(
                            `//input[@placeholder[contains(., "{field}")] or @aria-label[contains(., "{field}")]] | 
                             //textarea[@placeholder[contains(., "{field}")] or @aria-label[contains(., "{field}")]] |
                             //label[contains(text(), "{field}")]/following::input[1] |
                             //label[contains(text(), "{field}")]/following::textarea[1]`,
                            document,
                            null,
                            XPathResult.FIRST_ORDERED_NODE_TYPE,
                            null
                        ).singleNodeValue;
                        
                        if (!field) {{
                            return {{ success: false, error: `Could not find field: {field}` }};
                        }}
                        
                        // Focus and fill the field
                        field.focus();
                        field.value = "{value}";
                        field.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        field.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        
                        return {{ success: true }};
                    }} catch (error) {{
                        console.error('Error:', error);
                        return {{ success: false, error: error.toString() }};
                    }}
                }})();
                """
                
                def handle_fill_result(result):
                    try:
                        if isinstance(result, dict):
                            if result.get('success'):
                                logger.info(f"Successfully filled field '{field}' with value: {value}")
                            else:
                                error = result.get('error', 'Unknown error')
                                logger.warning(f"Failed to fill field: {error}")
                                self.chat_history.append(f"Error: {error}")
                        else:
                            logger.warning(f"Unexpected result type: {type(result)}")
                            self.chat_history.append("Error: Unexpected response from page")
                    except Exception as e:
                        logger.error(f"Error in handle_fill_result: {e}")
                        self.chat_history.append(f"Error processing result: {str(e)}")
                
                self.page.runJavaScript(js_code, handle_fill_result)
                return True

            elif action_type == 'select':
                # Select an option from a dropdown
                field = action_data.get('field', '')
                value = action_data.get('value', '')
                
                js_code = f"""
                (async function() {{
                    try {{
                        // Find select element by label or name
                        const select = document.evaluate(
                            `//select[@name[contains(., "{field}")] or @aria-label[contains(., "{field}")]] |
                             //label[contains(text(), "{field}")]/following::select[1]`,
                            document,
                            null,
                            XPathResult.FIRST_ORDERED_NODE_TYPE,
                            null
                        ).singleNodeValue;
                        
                        if (!select) {{
                            return {{ success: false, error: `Could not find dropdown: {field}` }};
                        }}
                        
                        // Find matching option
                        const options = Array.from(select.options);
                        const option = options.find(opt => 
                            opt.text.toLowerCase().includes("{value}".toLowerCase()) ||
                            opt.value.toLowerCase().includes("{value}".toLowerCase())
                        );
                        
                        if (!option) {{
                            return {{ success: false, error: `Could not find option: {value}` }};
                        }}
                        
                        // Select the option
                        select.value = option.value;
                        select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        
                        return {{ success: true }};
                    }} catch (error) {{
                        console.error('Error:', error);
                        return {{ success: false, error: error.toString() }};
                    }}
                }})();
                """
                
                def handle_select_result(result):
                    try:
                        if isinstance(result, dict):
                            if result.get('success'):
                                logger.info(f"Successfully selected '{value}' in dropdown '{field}'")
                            else:
                                error = result.get('error', 'Unknown error')
                                logger.warning(f"Failed to select option: {error}")
                                self.chat_history.append(f"Error: {error}")
                        else:
                            logger.warning(f"Unexpected result type: {type(result)}")
                            self.chat_history.append("Error: Unexpected response from page")
                    except Exception as e:
                        logger.error(f"Error in handle_select_result: {e}")
                        self.chat_history.append(f"Error processing result: {str(e)}")
                
                self.page.runJavaScript(js_code, handle_select_result)
                return True

            elif action_type == 'hover':
                # Hover over an element
                selector = action_data.get('selector', '')
                
                js_code = f"""
                (async function() {{
                    try {{
                        const element = document.querySelector('{selector}');
                        if (!element) {{
                            return {{ success: false, error: `Could not find element: {selector}` }};
                        }}
                        
                        // Trigger hover events
                        element.dispatchEvent(new MouseEvent('mouseover', {{ bubbles: true }}));
                        element.dispatchEvent(new MouseEvent('mouseenter', {{ bubbles: true }}));
                        
                        return {{ success: true }};
                    }} catch (error) {{
                        console.error('Error:', error);
                        return {{ success: false, error: error.toString() }};
                    }}
                }})();
                """
                
                def handle_hover_result(result):
                    try:
                        if isinstance(result, dict):
                            if result.get('success'):
                                logger.info(f"Successfully hovered over element: {selector}")
                            else:
                                error = result.get('error', 'Unknown error')
                                logger.warning(f"Failed to hover: {error}")
                                self.chat_history.append(f"Error: {error}")
                        else:
                            logger.warning(f"Unexpected result type: {type(result)}")
                            self.chat_history.append("Error: Unexpected response from page")
                    except Exception as e:
                        logger.error(f"Error in handle_hover_result: {e}")
                        self.chat_history.append(f"Error processing result: {str(e)}")
                
                self.page.runJavaScript(js_code, handle_hover_result)
                return True

            elif action_type == 'wait':
                # Wait for an element to appear
                selector = action_data.get('selector', '')
                timeout = action_data.get('timeout', 10)  # Default 10 seconds
                
                js_code = f"""
                (async function() {{
                    try {{
                        function waitForElement(selector, timeout) {{
                            return new Promise((resolve, reject) => {{
                                const startTime = Date.now();
                                
                                function checkElement() {{
                                    const element = document.querySelector(selector);
                                    if (element) {{
                                        resolve(element);
                                    }} else if (Date.now() - startTime > timeout * 1000) {{
                                        reject(new Error(`Timeout waiting for element: ${{selector}}`));
                                    }} else {{
                                        setTimeout(checkElement, 100);
                                    }}
                                }}
                                
                                checkElement();
                            }});
                        }}
                        
                        await waitForElement('{selector}', {timeout});
                        return {{ success: true }};
                    }} catch (error) {{
                        console.error('Error:', error);
                        return {{ success: false, error: error.toString() }};
                    }}
                }})();
                """
                
                def handle_wait_result(result):
                    try:
                        if isinstance(result, dict):
                            if result.get('success'):
                                logger.info(f"Successfully waited for element: {selector}")
                            else:
                                error = result.get('error', 'Unknown error')
                                logger.warning(f"Wait failed: {error}")
                                self.chat_history.append(f"Error: {error}")
                        else:
                            logger.warning(f"Unexpected result type: {type(result)}")
                            self.chat_history.append("Error: Unexpected response from page")
                    except Exception as e:
                        logger.error(f"Error in handle_wait_result: {e}")
                        self.chat_history.append(f"Error processing result: {str(e)}")
                
                self.page.runJavaScript(js_code, handle_wait_result)
                return True

            elif action_type == 'extract':
                # Extract text content from elements
                selector = action_data.get('selector', '')
                attribute = action_data.get('attribute', 'textContent')  # Default to text content
                
                js_code = f"""
                (async function() {{
                    try {{
                        const elements = Array.from(document.querySelectorAll('{selector}'));
                        if (elements.length === 0) {{
                            return {{ success: false, error: `No elements found matching: {selector}` }};
                        }}
                        
                        const results = elements.map(el => {{
                            if ('{attribute}' === 'textContent') {{
                                return el.textContent.trim();
                            }} else {{
                                return el.getAttribute('{attribute}');
                            }}
                        }}).filter(Boolean);
                        
                        return {{ success: true, data: results }};
                    }} catch (error) {{
                        console.error('Error:', error);
                        return {{ success: false, error: error.toString() }};
                    }}
                }})();
                """
                
                def handle_extract_result(result):
                    try:
                        if isinstance(result, dict):
                            if result.get('success'):
                                data = result.get('data', [])
                                logger.info(f"Successfully extracted {len(data)} items")
                                self.chat_history.append(f"Extracted content: {data}")
                            else:
                                error = result.get('error', 'Unknown error')
                                logger.warning(f"Extraction failed: {error}")
                                self.chat_history.append(f"Error: {error}")
                        else:
                            logger.warning(f"Unexpected result type: {type(result)}")
                            self.chat_history.append("Error: Unexpected response from page")
                    except Exception as e:
                        logger.error(f"Error in handle_extract_result: {e}")
                        self.chat_history.append(f"Error processing result: {str(e)}")
                
                self.page.runJavaScript(js_code, handle_extract_result)
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
                logger.info("Page load complete")
                self.page_load_complete = True
                
                # Take a screenshot after load
                self.capture_and_send_screenshot()
                
                # Process next action after a short delay to let the page settle
                QTimer.singleShot(1000, self._process_action_queue)
            else:
                logger.error("Page load failed")
                self.page_load_complete = True  # Still mark as complete to allow further actions
                self.chat_history.append("Error: Page failed to load")
        except Exception as e:
            logger.error(f"Error in handle_load_finished: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

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