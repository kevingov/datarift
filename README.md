# DataRift - QuickBooks Integration

A Flask application that connects to QuickBooks API to pull and analyze business data.

## Features

- 🔐 **Secure OAuth 2.0** authentication with QuickBooks
- 📊 **Real-time data** access to customers, invoices, payments, and items
- 🚀 **Production-ready** deployment on Railway
- 💻 **Modern UI** with Bootstrap for easy data visualization
- 🔄 **Live sync** capabilities for up-to-date information

## Quick Start

### Local Development

1. **Clone and setup**:
   ```bash
   git clone <your-repo>
   cd DataRift
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your QuickBooks API credentials
   ```

3. **Run locally**:
   ```bash
   python app.py
   ```

### Railway Deployment

1. **Install Railway CLI**:
   ```bash
   npm install -g @railway/cli
   ```

2. **Deploy to Railway**:
   ```bash
   railway login
   railway init
   railway up
   ```

3. **Set environment variables** in Railway dashboard:
   - `QB_CLIENT_ID` - Your QuickBooks Client ID
   - `QB_CLIENT_SECRET` - Your QuickBooks Client Secret
   - `QB_SANDBOX` - `False` for production
   - `SECRET_KEY` - Flask secret key
   - `QB_REDIRECT_URI` - `https://your-app.railway.app/callback`

4. **Update Intuit Developer Console**:
   - Add redirect URI: `https://your-app.railway.app/callback`
   - Switch to production mode

## API Endpoints

- `GET /` - Homepage
- `GET /auth` - Start QuickBooks OAuth flow
- `GET /callback` - OAuth callback handler
- `GET /dashboard` - Data dashboard
- `GET /api/customers` - Get customer data
- `GET /api/invoices` - Get invoice data
- `GET /api/payments` - Get payment data
- `GET /api/items` - Get item data
- `GET /api/sync` - Sync all data

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `QB_CLIENT_ID` | QuickBooks API Client ID | Yes |
| `QB_CLIENT_SECRET` | QuickBooks API Client Secret | Yes |
| `QB_REDIRECT_URI` | OAuth redirect URI | Yes |
| `QB_SANDBOX` | Use sandbox (True/False) | Yes |
| `SECRET_KEY` | Flask secret key | Yes |
| `FLASK_ENV` | Flask environment | No |

## Tech Stack

- **Backend**: Flask, Python
- **Frontend**: HTML, CSS, Bootstrap 5, JavaScript
- **API**: QuickBooks API v3
- **Deployment**: Railway
- **Authentication**: OAuth 2.0

## License

MIT License - see LICENSE file for details.
