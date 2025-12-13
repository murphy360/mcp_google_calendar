#!/usr/bin/env python3
"""Local OAuth authentication script for Google Calendar API.

Run this on a machine with a browser to get token.json, then copy to server.
"""

import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events'
]

def main():
    credentials_dir = Path(__file__).parent / "credentials"
    client_secrets = credentials_dir / "client_secrets.json"
    token_file = credentials_dir / "token.json"
    
    if not client_secrets.exists():
        print(f"Error: {client_secrets} not found!")
        return
    
    print("Starting OAuth flow...")
    print("A browser window will open for you to authorize.")
    
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secrets), 
        SCOPES
    )
    
    credentials = flow.run_local_server(
        port=8080, 
        prompt='consent', 
        access_type='offline'
    )
    
    # Save token in the format expected by google-auth
    token_data = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': list(credentials.scopes),
        'universe_domain': 'googleapis.com',
        'account': ''
    }
    
    with open(token_file, 'w') as f:
        json.dump(token_data, f, indent=2)
    
    print(f"\n✅ Token saved to {token_file}")
    print("\nNow copy this file to your server:")
    print(f"  scp {token_file} murphy360@192.168.68.82:~/Software/mcp_google_calendar/credentials/")

if __name__ == "__main__":
    main()
