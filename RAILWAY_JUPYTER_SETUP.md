# Railway Jupyter Setup Guide

## Overview
This Flask app includes an integrated Jupyter Lab server that runs alongside your main web application.

## Railway Deployment Notes

### Port Configuration
- **Flask App**: Runs on Railway's assigned `PORT` (usually 5000 locally, dynamic on Railway)
- **Jupyter Lab**: Runs on port `8888` (configurable via `JUPYTER_PORT` env var)

### Environment Variables
Set these in your Railway dashboard:

```bash
JUPYTER_PASSWORD=your-secure-token-here
JUPYTER_PORT=8888  # Optional, defaults to 8888
```

### Accessing Jupyter on Railway

Railway may handle multi-port applications differently. Here are the access methods:

1. **Primary Method**: Use the Flask route `/jupyter-lab/` which provides smart URL detection
2. **Direct Access**: If Railway exposes port 8888, use `https://your-app.railway.app:8888/?token=your-token`
3. **Subdomain**: Railway might create a subdomain like `https://jupyter-your-app.railway.app/?token=your-token`

### Railway Configuration Options

#### Option 1: Single Service (Current Setup)
- Both Flask and Jupyter run in the same container
- Jupyter accessible via Flask proxy routes
- Simpler deployment, single Railway service

#### Option 2: Multiple Services (Advanced)
If you need separate services:
1. Create two Railway services
2. Deploy Flask app to one service
3. Deploy Jupyter-only setup to another service
4. Update URLs to point to the Jupyter service

### Troubleshooting

#### Jupyter Not Accessible
1. Check Railway logs for Jupyter startup messages
2. Verify `JUPYTER_PORT` environment variable
3. Check if Railway exposes the Jupyter port
4. Use the Flask management interface at `/jupyter` to start/stop Jupyter

#### Port Issues
- Railway assigns ports dynamically
- Jupyter may need Railway's port configuration
- Check Railway dashboard for exposed ports

### Security Notes
- Change the default token (`quickbooks123`) in production
- Use Railway's environment variables for the token
- Consider IP restrictions if needed

### Local Development
- Flask: `http://localhost:5000`
- Jupyter: `http://localhost:8888/?token=quickbooks123`

### Production URLs
- Flask: `https://your-app.railway.app`
- Jupyter: Access via `/jupyter-lab/` route for smart URL detection
