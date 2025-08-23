# Google Calendar Setup for Athena Bot

## Option 1: Service Account (Recommended for Bots)

1. **Create Service Account:**
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - IAM & Admin → Service Accounts
   - Click "Create Service Account"
   - Name: "Athena Bot"
   - Role: No role needed for calendar access

2. **Download Key:**
   - Click on the created service account
   - Keys tab → Add Key → Create new key
   - Choose JSON format
   - Save as `service_account.json` in project folder

3. **Share Calendar:**
   - Open Google Calendar
   - Settings → Add people
   - Add the service account email (found in the JSON file)
   - Give "Make changes to events" permission

## Option 2: OAuth (for Personal Use)

1. **Add Test User:**
   - Google Cloud Console → APIs & Services → OAuth consent screen
   - Under "Test users" → Add users
   - Add your email address

2. **Run Auth Setup:**
   ```bash
   python3 setup_calendar_auth.py
   ```
   - This will open browser for OAuth flow
   - Creates `token.json` file

## Verification

Run the bot test:
```bash
python3 test_athena.py
```

The bot will now try these auth methods in order:
1. `service_account.json` (preferred)
2. `token.json` (OAuth)
3. Configured credentials file

## Testing

Test manual meeting creation:
```bash
python3 athena_meet_bot.py --mode create
```