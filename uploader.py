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

print("Step 1: Feed se latest video check ho rahi hai...")
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

# Step 3: Audio Library ke Asal Download Link se Full Audio nikalna
print("Step 3: Description se Asal Free Download Link nikaal rahe hain...")
all_links = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', description)

# Strictly match Hypeddit or direct download platforms
download_gate_url = None
for l in all_links:
    clean_l = l.rstrip('.,;)')
    # YouTube ke apne links ko ignore karein
    if "youtube.com" in clean_l or "youtu.be" in clean_l:
        continue
    if "hypeddit.com" in clean_l or "audiolibrary" in clean_l:
        download_gate_url = clean_l
        break

download_success = False

# Technique 1: Hypeddit page se audio stream capture
if download_gate_url:
    print(f"Hypeddit Download Gate Found: {download_gate_url}")
    try:
        s = requests.Session()
        s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        gate_res = s.get(download_gate_url, timeout=20)
        
        # Look for direct audio mp3 in page source or audio player tag
        soup = BeautifulSoup(gate_res.text, "html.parser")
        
        # Audio tags check
        audio_tags = soup.find_all("audio")
        for at in audio_tags:
            src = at.get("src") or (at.find("source") and at.find("source").get("src"))
            if src and ".mp3" in src:
                print(f"Direct stream URL extracted: {src}")
                with s.get(src, stream=True, timeout=60) as r_stream:
                    with open(audio_file, "wb") as f_out:
                        for chunk in r_stream.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f_out.write(chunk)
                if os.path.exists(audio_file) and os.path.getsize(audio_file) > 1000000:
                    download_success = True
                    break
        
        # Check script variables if audio tag not found directly
        if not download_success:
            mp3_matches = re.findall(r'https?://[^\s\'"]+\.mp3[^\s\'"]*', gate_res.text)
            for m_url in mp3_matches:
                print(f"Script MP3 URL found: {m_url}")
                with s.get(m_url, stream=True, timeout=60) as r_stream:
                    with open(audio_file, "wb") as f_out:
                        for chunk in r_stream.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f_out.write(chunk)
                if os.path.exists(audio_file) and os.path.getsize(audio_file) > 1000000:
                    download_success = True
                    break
    except Exception as e:
        print(f"Hypeddit fetch error: {e}")

# Technique 2: Dedicated public full-song stream API fallback
if not download_success:
    print("Technique 2: Secondary Audio Gate se full track resolve ho raha hai...")
    stream_resolvers = [
        f"https://yt-download.org/api/button/mp3/{latest_video_id}",
        f"https://loader.to/ajax/download.php?format=mp3&url=https://www.youtube.com/watch?v={latest_video_id}"
    ]
    for res_url in stream_resolvers:
        try:
            r = requests.get(res_url, timeout=15)
            if "download_url" in r.text or "href=" in r.text:
                matches = re.findall(r'https?://[^\s\'"]+\.mp3[^\s\'"]*', r.text)
                for dl_link in matches:
                    with requests.get(dl_link, stream=True, timeout=60) as audio_req:
                        with open(audio_file, "wb") as f_out:
                            for chunk in audio_req.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f_out.write(chunk)
                    if os.path.exists(audio_file) and os.path.getsize(audio_file) > 1000000:
                        download_success = True
                        break
            if download_success:
                break
        except Exception:
            continue

if not download_success or not os.path.exists(audio_file) or os.path.getsize(audio_file) < 800000:
    print("Error: Full audio download mukammal nahi ho saka. Adhoora audio upload nahi kiya jayega.")
    exit(1)

audio_mb = os.path.getsize(audio_file) / (1024 * 1024)
print(f"Complete Full Audio Downloaded! Size: {audio_mb:.2f} MB")

# Step 4: Full HD MP4 Video Render via FFmpeg
print("Step 4: Poori Video FFmpeg ke zariye render ho rahi hai...")
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
print(f"Video Tayar! Full Duration Video Size: {final_video_mb:.2f} MB")

# Step 5: Upload to YouTube as Private
print(f"Step 5: YouTube par mukammal video PRIVATE upload ho rahi hai: {title}")
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
