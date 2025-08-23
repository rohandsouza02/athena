# 🤖 Athena Meeting Bot

Production-grade automated standup system that integrates with Google Meet using the Vexa API to create seamless daily standups with AI-powered transcription.

## ✨ Features

- **🗓️ Automated Meeting Creation**: Creates daily standup meetings in Google Calendar with Google Meet links
- **🤖 AI Bot Integration**: Athena bot joins meetings automatically using Vexa API  
- **📝 Real-time Transcription**: Live transcript capture during meetings with speaker identification
- **🔗 Webhook Delivery**: Post-meeting transcript delivery to configured webhooks
- **🛡️ Production Ready**: Comprehensive error handling, logging, and retry mechanisms
- **⚙️ Flexible Scheduling**: Configurable meeting times, duration, and attendees
- **🔒 Secure**: Webhook signature verification and proper credential management

## 🚀 Quick Start

### 1. Install Dependencies

Since you're using Poetry:

```bash
# Install all dependencies
poetry install

# Or install with dev dependencies
poetry install --with dev
```

### 2. Get Required API Keys

#### Vexa AI API Key
1. Visit [vexa.ai](https://vexa.ai)
2. Sign up for an account
3. Get your API key from the dashboard

#### Google Calendar API Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google Calendar API
4. Create credentials (OAuth 2.0 Client IDs)
5. Download the credentials as `credentials.json`

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your API keys
nano .env
```

Required environment variables:
```bash
VEXA_API_KEY=your_vexa_api_key_here
WEBHOOK_URL=http://localhost:8080/transcript
GOOGLE_CREDENTIALS_PATH=credentials.json
```

### 4. Configure Meeting Settings

Edit `athena_config.json`:

```json
{
  "meeting": {
    "standup_time": "09:00",
    "attendees": ["team@yourcompany.com", "manager@yourcompany.com"],
    "timezone": "America/New_York"
  },
  "webhook": {
    "url": "http://localhost:8080/transcript"
  }
}
```

### 5. Test Setup

```bash
# Test your configuration
python3 test_athena.py
```

### 6. Start Webhook Server (for testing)

```bash
# In one terminal, start the webhook server
python3 webhook_server.py
```

### 7. Run Athena Bot

```bash
# In another terminal, run the bot
python3 athena_meet_bot.py --mode scheduler
```

## 🔧 Usage Modes

### Scheduled Mode (Production)
Runs daily automated standups:
```bash
python3 athena_meet_bot.py --mode scheduler
```

### Create Single Meeting
Creates one standup meeting immediately:
```bash
python3 athena_meet_bot.py --mode create
```

### Test Mode
Tests with an existing Google Meet URL:
```bash
python3 athena_meet_bot.py --mode test --meeting-url "https://meet.google.com/abc-defg-hij"
```

## 📡 Webhook Integration

Athena delivers transcripts via HTTP POST to your configured webhook:

```json
{
  "meeting_id": "uuid-string",
  "google_meet_url": "https://meet.google.com/abc-defg-hij",
  "start_time": "2024-01-15T09:00:00",
  "end_time": "2024-01-15T09:30:00",
  "transcript": "Complete meeting transcript with speaker identification...",
  "bot_name": "Athena",
  "status": "completed",
  "timestamp": "2024-01-15T09:35:00"
}
```

### Webhook Security

Include `X-Webhook-Secret` header for authentication:

```python
import hmac
import hashlib

def verify_webhook(payload, signature, secret):
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────┐
│   Scheduler     │───▶│ Google Cal   │───▶│ Meet Event  │
│   (Daily 9AM)   │    │   API        │    │  Created    │
└─────────────────┘    └──────────────┘    └─────────────┘
                                                   │
┌─────────────────┐    ┌──────────────┐           │
│   Athena Bot    │◀───│  Vexa API    │◀──────────┘
│   (Joins Meet)  │    │  Integration │
└─────────────────┘    └──────────────┘
         │                      │
         │                      ▼
         │              ┌──────────────┐
         │              │ Real-time    │
         │              │ Transcript   │
         │              │ Monitoring   │
         │              └──────────────┘
         ▼                      │
┌─────────────────┐            │
│  Meeting End    │            │
│   Detection     │            │
└─────────────────┘            │
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌──────────────┐
│   Final         │───▶│   Webhook    │
│   Transcript    │    │   Delivery   │
│   Retrieval     │    │   + Retry    │
└─────────────────┘    └──────────────┘
```

## 🐳 Production Deployment

### Docker
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --no-dev

# Copy application code
COPY . .

# Run the application
CMD ["poetry", "run", "python", "athena_meet_bot.py", "--mode", "scheduler"]
```

### Systemd Service
```ini
# /etc/systemd/system/athena-bot.service
[Unit]
Description=Athena Meeting Bot
After=network.target

[Service]
Type=simple
User=athena
WorkingDirectory=/opt/athena-bot
ExecStart=/usr/bin/python3 athena_meet_bot.py --mode scheduler
Restart=always
RestartSec=10
Environment=PATH=/opt/athena-bot/.venv/bin

[Install]
WantedBy=multi-user.target
```

## 🔍 Troubleshooting

### Common Issues

1. **"Missing required configuration"**
   ```bash
   # Set environment variables
   export VEXA_API_KEY=your_key_here
   export WEBHOOK_URL=http://localhost:8080/transcript
   ```

2. **"Google credentials file not found"**
   - Download credentials from Google Cloud Console
   - Save as `credentials.json` in project root
   - Ensure Calendar API is enabled

3. **"Vexa bot failed to join"**
   - Check API key is correct
   - Ensure meeting URL is accessible
   - Verify meeting is not restricted

4. **"Webhook delivery failed"**
   - Check webhook URL is accessible
   - Verify SSL certificate if using HTTPS
   - Check firewall/network settings

### Debug Mode

Enable debug logging in `athena_config.json`:
```json
{
  "logging": {
    "level": "DEBUG"
  }
}
```

## 📊 Monitoring

- Logs are automatically rotated (10MB max, 5 backups)
- All API calls are logged with timestamps
- Session status tracking available
- Webhook delivery status monitoring

## 🧪 Development

### Run Tests
```bash
poetry run pytest tests/
```

### Code Formatting
```bash
poetry run black athena_meet_bot.py
poetry run flake8 athena_meet_bot.py
```

### Development Dependencies
```bash
# Install dev dependencies
poetry install --with dev
```

## 📝 API Reference

### Manual Bot Control

```python
import asyncio
from athena_meet_bot import AthenaMeetBot, MeetingSession, MeetingStatus

async def join_existing_meeting():
    bot = AthenaMeetBot()
    
    session = MeetingSession(
        meeting_id="custom-id",
        google_meet_url="https://meet.google.com/your-meet-id",
        google_meet_id="your-meet-id", 
        start_time=datetime.now(),
        status=MeetingStatus.CREATED
    )
    
    await bot.join_meeting_with_athena(session)

# Run the async function
asyncio.run(join_existing_meeting())
```

### Custom Webhook Handler

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/transcript', methods=['POST'])
def handle_transcript():
    data = request.json
    
    meeting_id = data['meeting_id']
    transcript = data['transcript']
    
    # Process transcript (send to Slack, save to DB, etc.)
    print(f"Received transcript for {meeting_id}")
    
    return jsonify({"status": "success"})

app.run(host='0.0.0.0', port=8080)
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run formatting and tests
6. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

- Check the troubleshooting section above
- Review logs in `athena_bot.log`
- Ensure all environment variables are set
- Verify API keys are valid and have proper permissions

---

**Made with ❤️ for seamless team standups**