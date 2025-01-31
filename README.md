# Gemini Web Browser Assistant

An intelligent web browser assistant powered by Google's Gemini AI model. This browser can understand natural language commands and perform complex web tasks automatically.

## Features

- Natural language command processing
- Automated web navigation
- Intelligent form filling and search
- Smart element interaction
- Multi-step task execution
- Screenshot capture capability

## Requirements

- Python 3.8+
- PyQt6
- Google Generative AI Python SDK
- Internet connection
- Gemini API key

## Setup

1. Clone the repository:
```bash
git clone <your-repository-url>
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create an api_key.txt file with your Gemini API key:
```bash
echo "your-api-key" > api_key.txt
```

4. Run the browser:
```bash
python browser_ui.py
```

## Usage

Simply type your request in natural language, and the browser will execute it. Examples:

- "Go to eBay and search for white rabbits"
- "Navigate to Craigslist and find Ford trucks"
- "Go to chat.com and send a message"

## Architecture

- `browser_ui.py`: Main browser UI and web interaction logic
- `gemini_integration.py`: Gemini AI integration and command processing

## License

MIT License
