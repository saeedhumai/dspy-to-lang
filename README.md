# Ayla Agent Chat Interface

Real-time chat interface for Ayla Agent with WebSocket support.

## Quick Start

1. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Setup Environment**
   Create `.env`:

   ```env
   OPENAI_API_KEY=your_key
   MONGODB_URL=your_mongodb_url
   ```

3. **Run Backend**

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 5001 --reload --log-level debug
   ```

4. **Launch Frontend**
   - Open `tests/index.html` in browser
   - Or run: `python -m http.server 8000`
   - Visit: `http://localhost:8000/index.html`

## Features

- Auto-generated conversation IDs
- Real-time messaging
- Session persistence
- Error handling

## Troubleshooting

- Verify backend is running on port 5001
- Check MongoDB connection
- Validate OpenAI API key
- Check server logs for errors
- Enable browser console (F12) to see detailed error messages

## Common Fixes

- Clear browser cache and localStorage
- Try using direct WebSocket transport
- Verify model name matches backend configuration
- Check CORS settings if running on different ports

Requirements: Python 3.8+, MongoDB
