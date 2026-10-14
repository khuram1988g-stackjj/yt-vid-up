import os
import json
import subprocess
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

print("Step 1: Feed se latest video details check ho rahi hain...")
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
    print("Yeh video pehle se uploaded hai! No action needed.")
    exit(0)

# Files cleanup
audio_file = "downloaded_audio.m4a"
image_file = "thumbnail.jpg"
output_video = "final_output.mp4"

for f in [audio_file, image_file, output_video]:
    if os.path.exists(f):
        os.remove(f)

# Step 2: Download Thumbnail
print("Step 2: High quality thumbnail download ho raha hai...")
thumb_urls = [
    f"https://i.ytimg.com/vi/{latest_video_id}/maxresdefault.jpg",
    f"https://i.ytimg.com/vi/{latest_video_id}/hqdefault.jpg"
]
for t_url in thumb_urls:
    t_resp = requests.get(t_url)
    if t_resp.status_code == 200 and len(t_resp.content) > 5000:
        with open(image_file, "wb") as f:
            f.write(t_resp.content)
        break

# Step 3: Download Clean Audio Stream
print("Step 3: Direct Audio stream download ho rahi hai...")
dl_cmd = [
    "yt-dlp",
    "--extractor-args", "youtube:player_client=android_music,mweb",
    "-f", "ba/ba*",
    "-o", audio_file,
    target_url
]
subprocess.run(dl_cmd, check=True)

# Step 4: Render to MP4 via FFmpeg
print("Step 4: FFmpeg se audio aur thumbnail merge karke video banayi ja rahi hai...")
ffmpeg_cmd = [
    "ffmpeg", "-y",
    "-loop", "1", "-i", image_file,
    "-i", audio_file,
    "-c:v", "libx264", "-tune", "stillimage",
    "-c:a", "aac", "-b:a", "192k",
    "-pix_fmt", "yuv420p",
    "-shortest",
    output_video
]
subprocess.run(ffmpeg_cmd, check=True)

file_size_mb = os.path.getsize(output_video) / (1024 * 1024)
print(f"Video Tayar! Size: {file_size_mb:.2f} MB")

# Step 5: Upload to YouTube as Private
print(f"Step 5: YouTube par PRIVATE upload ho rahi hai: {title}")
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

media = MediaFileUpload(output_video, chunksize=-1, resumable=True, mimetype='video/mp4')
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

# Cleanup
for f in [audio_file, image_file, output_video]:
    if os.path.exists(f):
        os.remove(f)
