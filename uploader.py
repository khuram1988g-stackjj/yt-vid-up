import os
import json
import xml.etree.ElementTree as ET
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

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

print("Step 1: Feed se latest video check ki ja rahi hai...")
feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
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
    print("Video nahi mili.")
    exit(1)

latest_video_id = entry.find('yt:videoId', ns).text
title = entry.find('atom:title', ns).text
desc_elem = entry.find('.//media:description', ns)
description = desc_elem.text if desc_elem is not None else f"{title}\n\nAudio Library Music"

print(f"Target Video: {title} (ID: {latest_video_id})")

if latest_video_id in uploaded_ids:
    print("Yeh video pehle hi upload ho chuki hai. Process exit.")
    exit(0)

video_file = "downloaded_video.mp4"
if os.path.exists(video_file):
    os.remove(video_file)

print("Step 2: Active API Mirrors se direct MP4 stream dhoondi ja rahi hai...")

# Active Invidious & Piped backend instances
active_mirrors = [
    "https://invidious.jing.rocks",
    "https://inv.nadeko.net",
    "https://yt.drgnz.club",
    "https://invidious.private.coffee",
    "https://pipedapi.kavin.rocks"
]

download_success = False

for mirror in active_mirrors:
    print(f"Connecting to mirror: {mirror}...")
    try:
        # Route 1: Invidious API
        if "piped" not in mirror:
            api_url = f"{mirror}/api/v1/videos/{latest_video_id}"
            r = requests.get(api_url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                streams = data.get("formatStreams", [])
                
                # Best MP4 format dhoondna
                selected_url = None
                for s in streams:
                    if "video/mp4" in s.get("type", ""):
                        selected_url = s.get("url")
                        break
                
                if not selected_url and streams:
                    selected_url = streams[-1].get("url")
                
                if selected_url:
                    print(f"Stream link acquired from {mirror}! Downloading video...")
                    with requests.get(selected_url, stream=True, timeout=90) as stream_req:
                        stream_req.raise_for_status()
                        with open(video_file, "wb") as f:
                            for chunk in stream_req.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                    if os.path.exists(video_file) and os.path.getsize(video_file) > 1000000:
                        download_success = True
                        break
        # Route 2: Piped API
        else:
            api_url = f"{mirror}/streams/{latest_video_id}"
            r = requests.get(api_url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                v_streams = data.get("videoStreams", [])
                mp4_streams = [s for s in v_streams if s.get("format") == "MPEG_4" and not s.get("videoOnly")]
                if mp4_streams:
                    stream_url = mp4_streams[0].get("url")
                    print(f"Stream link acquired from Piped! Downloading...")
                    with requests.get(stream_url, stream=True, timeout=90) as stream_req:
                        stream_req.raise_for_status()
                        with open(video_file, "wb") as f:
                            for chunk in stream_req.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                    if os.path.exists(video_file) and os.path.getsize(video_file) > 1000000:
                        download_success = True
                        break
    except Exception as e:
        print(f"Mirror {mirror} failed ({e}), moving to next...")
        continue

if not download_success or not os.path.exists(video_file) or os.path.getsize(video_file) < 500000:
    print("Direct video download mukammal nahi ho saka.")
    exit(1)

file_size_mb = os.path.getsize(video_file) / (1024 * 1024)
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

media = MediaFileUpload(video_file, chunksize=-1, resumable=True, mimetype='video/mp4')
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

if os.path.exists(video_file):
    os.remove(video_file)
