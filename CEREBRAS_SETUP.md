# Cerebras AI Chatbot Setup Guide

## Quick Start

### 1. Environment Setup

Set your Cerebras API key in your environment:

#### Option A: Local Development (Windows PowerShell)
```powershell
# Activate virtual environment first
.\venv\Scripts\Activate.ps1

# Set environment variable
$env:CEREBRAS_API_KEY = "csk-8wn62ectvvdcvewfmjmf8ycw29eerpyhwnp3n3fj496wdty8"

# Verify it's set
echo $env:CEREBRAS_API_KEY
```

#### Option B: .env File (Recommended for local dev)
Create or edit `.env` file in your project root:
```
CEREBRAS_API_KEY=csk-8wn62ectvvdcvewfmjmf8ycw29eerpyhwnp3n3fj496wdty8
```

#### Option C: Permanent (Windows System Environment)
1. Open **Environment Variables**:
   - Press `Win + X` → Select **System** → **Advanced system settings**
   - Click **Environment Variables** button
   - Under "User variables", click **New...**
   - Variable name: `CEREBRAS_API_KEY`
   - Variable value: `csk-8wn62ectvvdcvewfmjmf8ycw29eerpyhwnp3n3fj496wdty8`
   - Click **OK** twice
   - Restart PowerShell/IDE

### 2. Verify Installation

```bash
# Activate venv if not already done
.\venv\Scripts\Activate.ps1

# Run verification script
python verify_cerebras.py
```

Expected output:
```
✓ Django setup successful
✓ cerebras_proxy view imported successfully
✓ Cerebras SDK imported successfully
✓ CEREBRAS_API_KEY is configured

✅ All integrations verified successfully!
```

### 3. Start Django Server

```bash
# Activate venv
.\venv\Scripts\Activate.ps1

# Run development server
python manage.py runserver

# Should show: "Starting development server at http://127.0.0.1:8000/"
```

### 4. Test the Chatbot

1. Open browser: `http://127.0.0.1:8000`
2. Login to your account
3. Navigate to: `/profile/ai-companion/`
4. Start chatting!

## What's Changed

### Backend Integration
- ✅ `users/views.py`: Added `cerebras_proxy()` endpoint
- ✅ `users/urls.py`: Added route `/api/v1/cerebras_proxy/`
- ✅ `myuganda/settings.py`: Added `CEREBRAS_API_KEY` configuration
- ✅ `requirements.txt`: Added `cerebras-cloud-sdk` dependency

### Frontend Updates
- ✅ `profile_ai.html`: Changed to WhatsApp-like theme
  - Color scheme: Dark (#0a1419) with green accents (#25D366)
  - Updated fetch endpoint to use `cerebras_proxy`
  - Enhanced UI with proper styling

### Model Used
- **Model**: `llama3.1-8b`
- **Speed**: Optimized for real-time chat
- **Cost**: $0.10 per 1M tokens (input + output)
- **Context**: Maintains full chat history with personalization

## Troubleshooting

### Error: "ModuleNotFoundError: No module named 'cerebras'"
**Solution**: Make sure you're using the virtual environment
```bash
# Activate venv first
.\venv\Scripts\Activate.ps1

# Then install
python -m pip install cerebras-cloud-sdk
```

### Error: "Cerebras API Key missing"
**Solution**: Set environment variable
```powershell
$env:CEREBRAS_API_KEY = "your-api-key-here"

# Restart Django server after setting
```

### Chatbot returns "System Error: Connection failed"
1. Check browser console (F12 → Console tab) for errors
2. Check Django server logs in terminal
3. Verify API key is set correctly
4. Ensure you're logged in to the site

### CSRF Token Error
- Make sure cookies are enabled in browser
- Try clearing cache and reloading page
- Check that `X-CSRFToken` header is being sent

## Features

✨ **Personalized AI**
- Tailored responses based on user profile
- Considers skills, experience, and headline
- Addresses user by name

🔗 **Smart Search Links**
- Automatic job search recommendations
- Product discovery links
- Market research capabilities

💬 **Session Management**
- Chat history stored in localStorage
- Multiple conversation threads
- Persistent session tracking

🎨 **WhatsApp-Inspired UI**
- Dark theme optimized for eyes
- Green accent color (#25D366)
- Smooth animations and transitions
- Mobile responsive design

## API Details

### Endpoint
- **URL**: `/api/v1/cerebras_proxy/`
- **Method**: `POST`
- **Auth**: Login required
- **CSRF**: Required

### Request Format
```json
{
  "contents": [
    {"role": "user", "text": "What is a good career path?"},
    {"role": "ai", "text": "...response..."}
  ]
}
```

### Response Format
```json
{
  "text": "Response text here...",
  "model_used": "llama3.1-8b"
}
```

## Production Deployment

1. Update `.env` or environment variables on your hosting platform
2. Run: `pip install -r requirements.txt`
3. Ensure Cerebras API key is set before deploying
4. Test the endpoint after deployment

## Support

For issues with:
- **Cerebras API**: https://console.cerebras.ai
- **Django**: Check `python manage.py runserver` output
- **Your deployment**: Check server logs

## Next Steps

- [ ] Verify installation with `verify_cerebras.py`
- [ ] Set `CEREBRAS_API_KEY` environment variable
- [ ] Start Django development server
- [ ] Test chatbot at `/profile/ai-companion/`
- [ ] Deploy to production
