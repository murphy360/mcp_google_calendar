#!/usr/bin/env python3
"""Manual OAuth authentication script for Google Calendar API.

This script doesn't require a local server - you manually copy the auth code.
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
    
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secrets), 
        SCOPES
    )
    
    # Use OOB-style flow but with localhost redirect
    # This generates a URL you can visit, then paste the code from the redirect URL
    flow.redirect_uri = 'http://localhost:8080/'
    
    auth_url, _ = flow.authorization_url(
        prompt='consent',
        access_type='offline'
    )
    
    print("\n" + "=" * 70)
    print("STEP 1: Open this URL in your browser:")
    print("=" * 70)
    print(f"\n{auth_url}\n")
    print("=" * 70)
    print("\nSTEP 2: After authorizing, you'll be redirected to a page that")
    print("        may show an error. That's OK! Look at the URL bar.")
    print("\nSTEP 3: Copy the 'code' parameter from the URL.")
    print("        It looks like: http://localhost:8080/?...&code=4/0ATX87l...")
    print("        Copy everything after 'code=' until the next '&'")
    print("=" * 70)
    
    code = input("\nPaste the authorization code here: ").strip()
    
    # Exchange the code for credentials
    flow.fetch_token(code=code)
    credentials = flow.credentials
    
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
