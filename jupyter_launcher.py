#!/usr/bin/env python3
"""
Jupyter Notebook Server for Railway

This script starts a Jupyter notebook server that can be deployed to Railway.
"""

import os
import subprocess
import sys
from jupyter_server.auth import passwd

def setup_jupyter():
    """Set up Jupyter configuration for Railway deployment"""
    
    # Create Jupyter config directory
    config_dir = os.path.expanduser('~/.jupyter')
    os.makedirs(config_dir, exist_ok=True)
    
    # Set password from environment variable or use default
    password = os.getenv('JUPYTER_PASSWORD', 'quickbooks123')
    hashed_password = passwd(password)
    
    # Create Jupyter config
    config_content = f"""
c.ServerApp.ip = '0.0.0.0'
c.ServerApp.port = {os.getenv('PORT', 8888)}
c.ServerApp.open_browser = False
c.ServerApp.password = '{hashed_password}'
c.ServerApp.allow_root = True
c.ServerApp.allow_origin = '*'
c.ServerApp.disable_check_xsrf = True
c.ServerApp.notebook_dir = '/app'
c.ServerApp.token = ''
"""
    
    config_path = os.path.join(config_dir, 'jupyter_server_config.py')
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    print(f"✅ Jupyter configured")
    print(f"   Password: {password}")
    print(f"   Port: {os.getenv('PORT', 8888)}")
    
    return config_path

def start_jupyter():
    """Start Jupyter notebook server"""
    
    # Set up configuration
    config_path = setup_jupyter()
    
    # Start Jupyter
    cmd = [
        sys.executable, '-m', 'jupyter', 'lab',
        '--config', config_path,
        '--no-browser',
        '--allow-root'
    ]
    
    print("🚀 Starting Jupyter Lab...")
    print(f"   Command: {' '.join(cmd)}")
    
    # Run Jupyter
    subprocess.run(cmd)

if __name__ == '__main__':
    start_jupyter() 