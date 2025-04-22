import time
import requests
import base64
from django.conf import settings
from django.contrib import messages

def generate_zoom_access_token():
    """Generate an OAuth access token for Zoom API."""
    # Encode Client ID and Secret for Basic Auth
    credentials = f"{settings.ZOOM_CLIENT_ID}:{settings.ZOOM_CLIENT_SECRET}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "grant_type": "account_credentials",
        "account_id": settings.ZOOM_ACCOUNT_ID
    }

    response = requests.post(
        "https://zoom.us/oauth/token",
        headers=headers,
        data=payload
    )

    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Failed to generate access token: {response.text}")

def create_zoom_meeting(event_title, event_date, event_time, duration=60):
    """Create a Zoom meeting and return the join URL."""
    token = generate_zoom_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    start_time = f"{event_date}T{event_time}:00Z"
    
    payload = {
        "topic": event_title,
        "type": 2,  # Scheduled meeting
        "start_time": start_time,
        "duration": duration,
        "timezone": "UTC",
        "settings": {
            "host_video": True,
            "participant_video": True,
            "join_before_host": True,
            "mute_upon_entry": False,
            "watermark": False,
            "use_pmi": False,
            "approval_type": 2,
            "audio": "both",
            "auto_recording": "none"
        }
    }
    
    response = requests.post(
        f"https://api.zoom.us/v2/users/me/meetings",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 201:
        meeting_data = response.json()
        return meeting_data["join_url"], meeting_data["id"]  # Return join_url and meeting ID
    else:
        raise Exception(f"Failed to create Zoom meeting: {response.text}")

def update_zoom_meeting(meeting_id, event_title, event_date, event_time, duration=60):
    """Update an existing Zoom meeting."""
    token = generate_zoom_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    start_time = f"{event_date}T{event_time}:00Z"
    
    payload = {
        "topic": event_title,
        "start_time": start_time,
        "duration": duration,
        "timezone": "UTC"
    }
    
    response = requests.patch(
        f"https://api.zoom.us/v2/meetings/{meeting_id}",
        headers=headers,
        json=payload
    )
    
    if response.status_code != 204:
        raise Exception(f"Failed to update Zoom meeting: {response.text}")

def delete_zoom_meeting(meeting_id):
    """Delete a Zoom meeting."""
    token = generate_zoom_access_token()
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.delete(
        f"https://api.zoom.us/v2/meetings/{meeting_id}",
        headers=headers
    )
    
    if response.status_code not in [204, 404]:
        raise Exception(f"Failed to delete Zoom meeting: {response.text}")
    
