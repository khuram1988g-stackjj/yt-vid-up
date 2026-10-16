import os
import re
import json
import time
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# OAuth Credentials
CLIENT_ID = "720341227533-" + "fk5ds2vsb14aekek3th6aft3i98a0j9g" + ".apps.googleusercontent.com"
CLIENT_SECRET = "GOCSPX-" + "uvFVhhCnqg1mbUoXevKvHjr86A9k"
REFRESH_TOKEN = "1//05PFTTurtAsbKCgYIARAAGAUSNwF-" + "L9Ir1nzgU8Iy5TL8_PmlI9uuOS8UI_DXBBuNSz-AIGj9x8ZjMOiJiJuCX81YR18PR4Qb8kY"

TRACKER_FILE = "uploaded_music.json"
CHANNEL_HANDLE = "audiolibrary_"

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

print("Step 1: Audio Library channel ki latest video fetch ho rahi hai...")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
channel_url = f"https://www.youtube.com/@{CHANNEL_HANDLE}/videos"
r = requests.get(channel_url, headers=headers, timeout=25)

video_ids = re.findall(r'\"videoId\":\"([a-zA-Z0-9_-]{11})\"', r.text)
if not video_ids:
    print("Channel se video list nahi mil saki.")
    exit(1)

latest_video_id = video_ids[0]
target_url = f"https://www.youtube.com/watch?v={latest_video_id}"

if latest_video_id in uploaded_ids:
    print(f"Yeh video (ID: {latest_video_id}) pehle se upload ho chuki hai. Process exit.")
    exit(0)

print(f"Latest video ID mili: {latest_video_id}. Full metadata extract ho raha hai...")

# Video page se exact Title, Description aur Tags nikaalna
vid_page = requests.get(target_url, headers=headers, timeout=25).text

# 1. Asli Title
title_match = re.search(r'<meta name="title" content="(.*?)">', vid_page)
if not title_match:
    title_match = re.search(r'\"title\":\{\"runs\":\[\{\"text\":\"(.*?)\"\}\]', vid_page)
title = title_match.group(1) if title_match else "Audio Library Music Track"

# 2. Asli Description
desc_match = re.search(r'\"shortDescription\":\"(.*?)\"', vid_page)
if desc_match:
    # Escape characters (\n, \", etc.) ko theek karna
    raw_desc = desc_match.group(1)
    description = raw_desc.encode('utf-8').decode('unicode-escape')
else:
    description = f"{title}\n\nProvided by Audio Library Automation.\n#music #audiolibrary"

# 3. Asli Tags / Keywords
tags = []
keywords_match = re.search(r'<meta name="keywords" content="(.*?)">', vid_page)
if keywords_match:
    tags = [t.strip() for t in keywords_match.group(1).split(",") if t.strip()]

if not tags:
    tags = ["music", "audio library", "no copyright music", "free music"]

print(f"Title: {title}")
print(f"Total Tags extracted: {len(tags)}")

output_video = "downloaded_track.mp4"
if os.path.exists(output_video):
    os.remove(output_video)

# Step 2: Multi-Server API Download Engine
print("Step 2: Video stream download ho rahi hai...")

api_endpoints = [
    {"type": "cobalt", "url": "https://capi.oak.li/"},
    {"type": "cobalt", "url": "https://api.co.rooot.gay/"},
    {"type": "cobalt", "url": "https://cobalt-api.hyper.lol/"},
    {"type": "cobalt", "url": "https://cobalt.synzr.space/"},
    {"type": "loader", "url": "https://loader.to/ajax/download.php"}
]

download_success = False

for ep in api_endpoints:
    ep_url = ep["url"]
    ep_type = ep["type"]
    print(f"Testing server: {ep_url}")
    
    try:
        if ep_type == "cobalt":
            c_headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
            payload = {
                "url": target_url,
                "videoQuality": "720",
                "vQuality": "720",
                "filenamePattern": "basic"
            }
            resp = requests.post(ep_url, json=payload, headers=c_headers, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                stream_url = data.get("url")
                if stream_url:
                    print("Direct stream URL mil gaya! Downloading file...")
                    with requests.get(stream_url, stream=True, timeout=120) as dl:
                        dl.raise_for_status()
                        with open(output_video, 'wb') as f:
                            for chunk in dl.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                    if os.path.exists(output_video) and os.path.getsize(output_video) > 500000:
                        download_success = True
                        break

        elif ep_type == "loader":
            l_resp = requests.get(f"{ep_url}?format=720&url={target_url}", timeout=15)
            if l_resp.status_code == 200:
                task_id = l_resp.json().get("id")
                if task_id:
                    for _ in range(12):
                        time.sleep(2)
                        p_check = requests.get(f"https://loader.to/ajax/progress.php?id={task_id}", timeout=10).json()
                        if p_check.get("success") == 1 and p_check.get("download_url"):
                            stream_url = p_check.get("download_url")
                            with requests.get(stream_url, stream=True, timeout=120) as dl:
                                dl.raise_for_status()
                                with open(output_video, 'wb') as f:
                                    for chunk in dl.iter_content(chunk_size=1024 * 1024):
                                        if chunk:
                                            f.write(chunk)
                            if os.path.exists(output_video) and os.path.getsize(output_video) > 500000:
                                download_success = True
                            break
                    if download_success:
                        break
    except Exception as err:
        print(f"Server {ep_url} notice: {err}, switching to next...")
        continue

if not download_success or not os.path.exists(output_video) or os.path.getsize(output_video) < 500000:
    print("Download fail ho gaya. Streams unavailable.")
    exit(1)

file_size_mb = os.path.getsize(output_video) / (1024 * 1024)
print(f"Video Download Complete! Size: {file_size_mb:.2f} MB")

# Step 3: YouTube par PRIVATE upload with Full Metadata
print(f"Step 3: YouTube par PRIVATE upload shuru...")
body = {
    'snippet': {
        'title': title[:100],               # Max 100 characters allowed by YouTube
        'description': description[:5000],   # Max 5000 characters allowed by YouTube
        'tags': tags[:50],                  # Original extracted tags
        'categoryId': '10'                  # Music category
    },
    'status': {
        'privacyStatus': 'private'
    }
}

media = MediaFileUpload(output_video, chunksize=-1, resumable=True, mimetype='video/mp4')
upload_req = youtube.videos().insert(
    part=','.join(body.keys()),
    body=body,
    media_body=media
)
upload_resp = upload_req.execute()
new_id = upload_resp.get("id")
print(f"Success! Video Private Upload Ho Gayi. Video ID: {new_id}")

# State Tracker update
uploaded_ids.add(latest_video_id)
with open(TRACKER_FILE, "w") as f:
    json.dump(list(uploaded_ids), f, indent=2)

if os.path.exists(output_video):
    os.remove(output_video)
