import os
import re
import json
import subprocess
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
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
    print("Yeh video pehle hi upload ho chuki hai. No action needed.")
    exit(0)

audio_file = "full_audio.mp3"
image_file = "cover.jpg"
output_video = "rendered_video.mp4"

for f in [audio_file, image_file, output_video]:
    if os.path.exists(f):
        os.remove(f)

# Step 2: High quality thumbnail download
print("Step 2: HD Thumbnail download ho raha hai...")
thumb_res = requests.get(f"https://i.ytimg.com/vi/{latest_video_id}/maxresdefault.jpg")
if thumb_res.status_code != 200 or len(thumb_res.content) < 5000:
    thumb_res = requests.get(f"https://i.ytimg.com/vi/{latest_video_id}/hqdefault.jpg")

with open(image_file, "wb") as f:
    f.write(thumb_res.content)

# Step 3: Audio source dhoondna aur aria2c se download karwana
print("Step 3: Direct audio stream resolve ho raha hai...")

all_links = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', description)
direct_stream_url = None

# Filter out social / generic YouTube links
candidate_links = []
for l in all_links:
    clean_l = l.rstrip('.,;)')
    lower_l = clean_l.lower()
    if any(skip in lower_l for skip in ["youtube.com", "youtu.be", "instagram.com", "facebook.com", "twitter.com", "t.me"]):
        continue
    candidate_links.append(clean_l)

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

# Route A: Candidate landing pages se .mp3 stream nikalna
for gate_url in candidate_links:
    try:
        print(f"Checking gate link: {gate_url}")
        gate_res = session.get(gate_url, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(gate_res.text, "html.parser")
        
        # Audio tag check
        for at in soup.find_all("audio"):
            src = at.get("src") or (at.find("source") and at.find("source").get("src"))
            if src and ".mp3" in src:
                direct_stream_url = src
                break
        
        # In-page script MP3 links check
        if not direct_stream_url:
            mp3_matches = re.findall(r'https?://[^\s\'"]+\.mp3[^\s\'"]*', gate_res.text)
            if mp3_matches:
                direct_stream_url = mp3_matches[0]
                
        if direct_stream_url:
            break
    except Exception as e:
        print(f"Gate check failed for {gate_url}: {e}")

# Route B: Fallback REST audio extractors (agar description mein koi direct download link na ho)
if not direct_stream_url:
    print("Direct landing link nahi mila, public audio resolvers try ho rahe hain...")
    api_resolvers = [
        f"https://api.vevioz.com/api/button/mp3/{latest_video_id}",
        f"https://yt-download.org/api/button/mp3/{latest_video_id}"
    ]
    for api_url in api_resolvers:
        try:
            r = session.get(api_url, timeout=15)
            if r.status_code == 200:
                matches = re.findall(r'href=[\'"](https?://[^\'"]+\.mp3[^\'"]*)[\'"]', r.text)
                if matches:
                    direct_stream_url = matches[0]
                    break
        except Exception:
            continue

# Step 4: aria2c download engine execution
download_complete = False
if direct_stream_url:
    print(f"Direct stream link mil gaya: {direct_stream_url}")
    print("Download software (aria2c) se high-speed stream download shuru...")
    aria_cmd = [
        "aria2c",
        "-x", "8",
        "-s", "8",
        "-k", "1M",
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "-o", audio_file,
        direct_stream_url
    ]
    res = subprocess.run(aria_cmd)
    if res.returncode == 0 and os.path.exists(audio_file) and os.path.getsize(audio_file) > 500000:
        download_complete = True

if not download_complete:
    print("Audio download mukammal nahi ho saka.")
    exit(1)

audio_mb = os.path.getsize(audio_file) / (1024 * 1024)
print(f"Complete Audio Downloaded! File Size: {audio_mb:.2f} MB")

# Step 5: Full HD MP4 Video Render via FFmpeg
print("Step 5: FFmpeg se full video render ho rahi hai...")
subprocess.run([
    "ffmpeg", "-y",
    "-loop", "1", "-i", image_file,
    "-i", audio_file,
    "-c:v", "libx264", "-tune", "stillimage",
    "-c:a", "aac", "-b:a", "192k",
    "-pix_fmt", "yuv420p",
    "-shortest",
    output_video
], check=True)

final_video_mb = os.path.getsize(output_video) / (1024 * 1024)
print(f"Video Tayar! Final Video Size: {final_video_mb:.2f} MB")

# Step 6: YouTube par upload as Private
print(f"Step 6: YouTube par mukammal video PRIVATE upload ho rahi hai: {title}")
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
print(f"Success! Mukammal Full-Length Video Upload Ho Gayi. Video ID: {new_id}")

uploaded_ids.add(latest_video_id)
with open(TRACKER_FILE, "w") as f:
    json.dump(list(uploaded_ids), f, indent=2)

for f in [audio_file, image_file, output_video]:
    if os.path.exists(f):
        os.remove(f)
