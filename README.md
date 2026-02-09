# BCParks Campsite Tracker

A self-hosted notification system for monitoring BC Parks campsite availability. Get notified via SMS or email when your desired campsite becomes available.

## Features

- 🏕️ **Multi-Site Monitoring**: Track multiple campgrounds and specific campsites
- 📱 **SMS & Email Alerts**: Get notified through your preferred method
- ⚙️ **Configurable Scanning**: Adjust check intervals through admin UI
- 🔐 **User Management**: Multi-user support with admin controls
- 🐳 **Docker Ready**: Easy deployment with Docker Compose
- 📊 **Usage Tracking**: Optional SMS limits to control costs

## Quick Start

### Prerequisites

- Docker and Docker Compose
- (Optional) Twilio account for SMS notifications
- (Optional) SendGrid or SMTP server for email notifications

### Installation

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd BCParks-Campsite-Tracker
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your preferred settings
   ```

3. **Start the application**:
   ```bash
   docker-compose up -d
   ```

4. **Access the web interface**:
   - Open http://localhost:5000
   - Login with default credentials: `admin` / `admin`
   - **IMPORTANT**: Change the admin password immediately!

## Configuration

### Docker Environment (.env)

The `.env` file controls infrastructure settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `5000` | Web server port |
| `WORKERS` | `4` | Gunicorn worker processes |
| `DEFAULT_ADMIN_USERNAME` | `admin` | Initial admin username |
| `DEFAULT_ADMIN_PASSWORD` | `admin` | Initial admin password |
| `SKIP_DEFAULT_ADMIN` | `false` | Skip auto-creating admin user |
| `SECRET_KEY` | `dev` | Flask secret key (change for production!) |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

> [!WARNING]
> **Production Security**: Always generate a secure `SECRET_KEY` for production:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

### Application Settings (Admin UI)

Navigate to **Admin Settings** in the web interface to configure:

- **Scan Interval**: How often to check for availability (minutes)
- **Twilio Settings**: SMS notification credentials
- **Email Settings**: SMTP or SendGrid configuration
- **SMS Limits**: Optional per-user message caps
- **Feature Flags**: Enable/disable registration and password resets

## Setting Up Notifications

### Twilio (SMS)

1. Create a [Twilio account](https://www.twilio.com)
2. Get your Account SID, Auth Token, and phone number
3. Create a [Verify Service](https://www.twilio.com/console/verify/services)
4. Add credentials in **Admin Settings**

### SendGrid (Email)

1. Create a [SendGrid account](https://sendgrid.com)
2. Generate an API key
3. Configure in **Admin Settings** → Choose "SendGrid" as provider

### SMTP (Email Alternative)

Use any SMTP server (Gmail, Outlook, etc.):
1. Get SMTP host, port, and credentials
2. Configure in **Admin Settings** → Choose "SMTP" as provider

## Usage

1. **Add Contact Methods**:
   - Go to Settings
   - Add email or phone number
   - Verify phone numbers via SMS code

2. **Create Alert**:
   - Click "Create New Alert"
   - Select campground and dates
   - Optionally select specific campsites
   - Set minimum consecutive nights

3. **Monitor**:
   - Alerts run automatically based on scan interval
   - Notifications sent when new availability detected
   - View last scan time on home page

## User Management

### Adding Users (Admin)

- Navigate to **Admin → Users**
- Create accounts with username and PIN (4-6 digits)
- Optionally grant admin privileges

### Public Registration

Enable/disable in **Admin Settings** → "Allow Registration"

## Database Backup

Administrators can export/import the SQLite database:
- **Export**: Admin Settings → "Export Database"
- **Import**: Admin Settings → Upload `.sqlite3` file
  - Admin credentials are preserved during import

### Volume Persistence

The `instance/` directory (database) is automatically persisted via Docker volume.

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Test thoroughly with Docker
4. Submit a pull request

## License

[Add your license here]

## Support

For issues and questions:
- GitHub Issues: [Add your GitHub repo link]
- Documentation: See `/docs/` in the web interface for Twilio and SMTP setup guides

---

**Disclaimer**: This project is not affiliated with BC Parks. Use responsibly and in accordance with BC Parks terms of service.
