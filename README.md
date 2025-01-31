# Gemini Web Browser Assistant


***** THIS IS A LONG WAY FROM BEING READY TO DEPLOY BUT ITS A STARTING POINT ******


An intelligent web browser assistant powered by Google's Gemini AI model that enables natural language control of web browsing activities.

## Features
- **Natural Language Command Processing**: Control your browsing with simple English commands
- **Automated Web Navigation**: Smart URL handling and page navigation
- **Intelligent Search**: Enhanced search capabilities across various platforms
- **Advanced Element Interaction**: 
  - Smart element detection and clicking
  - Robust form filling
  - Platform-specific handling (e.g., TradingView, eBay)
- **Multi-step Task Execution**: Chain multiple actions together
- **Screenshot Capabilities**: Capture and save webpage screenshots
- **Error Handling**: Detailed logging and error reporting
- **Cross-Platform Support**: Works on Windows, macOS, and Linux

## Requirements
- Python 3.8+
- PyQt6
- Google Generative AI Python SDK
- Internet connection
- Gemini API key (version: gemini-2.0-flash-thinking-exp-01-21)

## Setup
1. Clone the repository:
```bash
git clone https://github.com/skyliftcoin/gemini-web-browser.git
cd gemini-web-browser
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `gemini key.txt` file with your Gemini API key:
```bash
echo "your-api-key" > "gemini key.txt"
```

4. Run the browser:
```bash
python browser_ui.py
```

## Usage Examples
Type natural language commands in the input box:

### Basic Navigation
- "Go to google.com"
- "Navigate to youtube.com"
- "Open tradingview.com"

### Search Operations
- "Search for 'Python programming' on Google"
- "Go to eBay and search for vintage cameras"
- "Find Bitcoin price on TradingView"

### Complex Tasks
- "Go to TradingView, search for AAPL, and click on the 1D timeframe"
- "Navigate to eBay, search for vintage watches, and sort by price"
- "Go to Hugging Face, find stable diffusion models, and sort by downloads"

## Architecture
The application consists of three main components:

### browser_ui.py
- Main browser window and UI components
- Web interaction logic
- JavaScript injection for element interaction
- Screenshot handling
- Event management

### browser_api.py
- API endpoint definitions
- Request handling
- Response processing
- Error management

### gemini_integration.py
- Gemini AI model integration
- Natural language processing
- Command parsing and execution
- Context management

## Security
- API keys are automatically excluded from git via .gitignore
- SSL certificate handling for secure connections
- Proper error handling and input validation
- Secure storage of sensitive information

## Contributing
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License
MIT License - see [LICENSE](LICENSE) for details

## Acknowledgments
- Google's Gemini AI model
- PyQt6 framework
- The open-source community

## Support
For support, please open an issue in the GitHub repository.
