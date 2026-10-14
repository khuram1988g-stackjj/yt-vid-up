import os
import json
import xml.etree.ElementTree as ET
import requests
from pytube import YouTube
from pytube.innertube import InnerTube
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# InnerTube client ko Android client par force karna (Bot detection bypass)
InnerTube.client_name = "ANDROID_MUSIC"

CLIENT_ID = "720341227533-" + "fk5ds2vsb14aekek3th6aft3i98a0j9g" + ".apps.googleusercontent.com"
CLIENT_SECRET = "GOCSPX-" + "uvFVhhCnqg1mbUoXevKvHjr86A9k"
REFRESH_TOKEN = "1//05PFTTurtAsbKCgYIARAAGAUSNwF-" + "L9Ir1nzgU8Iy5TL8_PmlI9uuOS8UI_DXBBuNSz-AIGj9x8ZjMOiJiJuCX81YR18PR4Qb8kY"

TRACKER_FILE = "uploaded_music.json"
CHANNEL_ID = "UCht8qITGkBvXKsR1Byln-wA"

creds = Credentials(
    None,
    refresh_token=REFRESH_TOKEN,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    scopes=["https://www.googleapis.com/auth/youtube.upload"]
)
youtube = build('youtube', 'v3', credentials=creds)

if os.path.exists(TRACKER_FILE):
    try:
        with open(TRACKER_FILE, "r") as f:
            uploaded_ids = set(json.load(f))
    except Exception:
        uploaded_ids = set()
else:
    uploaded_ids = set()

print("Step 1: Feed se latest video details fetch ho rahi hain...")
feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
headers = {"User-Agent": "Mozilla/5.0"}
resp = requests.get(feed_url, headers=headers, timeout=20)

if resp.status_code != 200:
    print(f"Feed error: {resp.status_code}")
    exit(1)

root = ET.fromstring(resp.content)
ns = {
    'atom': 'http://www.w3.org/2005/Atom',
    'yt': 'http://www.youtube.com/xml/schemas/2015',
    'media': 'http://search.yahoo.com/mrss/'
}

entry = root.find('atom:entry', ns)
if entry is None:
    print("Channel feed mein video nahi mili.")
    exit(1)

latest_video_id = entry.find('yt:videoId', ns).text
title = entry.find('atom:title', ns).text
desc_elem = entry.find('.//media:description', ns)
description = desc_elem.text if desc_elem is not None else f"{title}\n\nAudio Library Music"

target_url = f"https://www.youtube.com/watch?v={latest_video_id}"
print(f"Target Video: {title}")
print(f"Target URL: {target_url}")

if latest_video_id in uploaded_ids:
    print("Yeh video pehle hi upload ho chuki hai. No action needed.")
    exit(0)

local_video_file = "downloaded_track.mp4"
if os.path.exists(local_video_file):
    os.remove(local_video_file)

print("Step 2: pytube (Android Client) ke zariye direct download shuru...")

# pytube stream download
yt = YouTube(target_url, use_oauth=False, allow_oauth_cache=False)
stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()

if not stream:
    # Fallback to adaptive mp4 stream
    stream = yt.streams.filter(file_extension='mp4').first()

if not stream:
    print("Stream nahi mil saki.")
    exit(1)

print(f"Stream selected: {stream.resolution} ({stream.mime_type}). Downloading...")
stream.download(filename=local_video_file)

file_size_mb = os.path.getsize(local_video_file) / (1024 * 1024)
print(f"Downloaded Successfully! File Size: {file_size_mb:.2f} MB")

print(f"Step 3: YouTube par PRIVATE upload ho rahi hai: {title}")
body = {
    'snippet': {
        'title': title,
        'description': description,
        'tags': ["music", "audio library", "no copyright", "free music"],
        'categoryId': '10'
    },
    'status': {
        'privacyStatus': 'private'
    }
}

media = MediaFileUpload(local_video_file, chunksize=-1, resumable=True, mimetype='video/mp4')
upload_req = youtube.videos().insert(
    part=','.join(body.keys()),
    body=body,
    media_body=media
)
upload_resp = upload_req.execute()
new_id = upload_resp.get("id")
print(f"Success! Video Private Upload Ho Gayi. Video ID: {new_id}")

uploaded_ids.add(latest_video_id)
with open(TRACKER_FILE, "w") as f:
    json.dump(list(uploaded_ids), f, indent=2)

if os.path.exists(local_video_file):
    os.remove(local_video_file)
