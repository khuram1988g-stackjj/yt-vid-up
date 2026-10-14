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

# Pichla 6-second wala test hata kar nayi full video allow karne ke liye:
# uploaded_ids check
if latest_video_id in uploaded_ids:
    print("Notice: Video pehle se tracker mein thi, lekin fresh complete upload ke liye proceed kiya ja raha hai...")

audio_file = "full_track.mp3"
image_file = "cover.jpg"
output_video = "rendered_video.mp4"

for f in [audio_file, image_file, output_video]:
    if os.path.exists(f):
        os.remove(f)

# Step 2: High quality cover thumbnail download
print("Step 2: HD Thumbnail download ho raha hai...")
thumb_res = requests.get(f"https://i.ytimg.com/vi/{latest_video_id}/maxresdefault.jpg")
if thumb_res.status_code != 200 or len(thumb_res.content) < 5000:
    thumb_res = requests.get(f"https://i.ytimg.com/vi/{latest_video_id}/hqdefault.jpg")

with open(image_file, "wb") as f:
    f.write(thumb_res.content)

# Step 3: Description se direct download link dhoond kar full song lena
print("Step 3: Description se direct official download link scan ho raha hai...")
urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', description)

download_url = None
for u in urls:
    clean_u = u.rstrip('.,;)')
    if any(k in clean_u.lower() for k in ["hypeddit.com", "audiolibrary", "drive.google.com", "bit.ly", "tinyurl"]):
        download_url = clean_u
        break

download_success = False

# Method A: Direct link scraper
if download_url:
    print(f"Official download link mila: {download_url}")
    try:
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        page = session.get(download_url, timeout=20, allow_redirects=True)
        
        # Check direct audio
        if "audio" in page.headers.get("Content-Type", "") or page.url.endswith((".mp3", ".wav", ".m4a")):
            with open(audio_file, "wb") as f:
                f.write(page.content)
            download_success = True
        else:
            soup = BeautifulSoup(page.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if ".mp3" in href.lower() or "download" in a.text.lower():
                    dl_target = href if href.startswith("http") else requests.compat.urljoin(page.url, href)
                    with session.get(dl_target, stream=True, timeout=60) as r:
                        r.raise_for_status()
                        with open(audio_file, "wb") as f:
                            for chunk in r.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                    if os.path.exists(audio_file) and os.path.getsize(audio_file) > 1000000:
                        download_success = True
                        break
    except Exception as e:
        print(f"Direct link resolution fail: {e}")

# Method B: Dedicated MP3 stream mirrors for full duration
if not download_success:
    print("Method B: Audio stream mirror se full song download ho raha hai...")
    apis = [
        f"https://api.vevioz.com/api/button/mp3/{latest_video_id}",
        f"https://ytstream.nocopyright.workers.dev/?id={latest_video_id}"
    ]
    for api in apis:
        try:
            r = requests.get(api, timeout=20)
            if r.status_code == 200:
                match = re.search(r'href=[\'"](https?://[^\'"]+\.mp3[^\'"]*)[\'"]', r.text)
                if match:
                    mp3_stream = match.group(1)
                    with requests.get(mp3_stream, stream=True, timeout=60) as dl:
                        with open(audio_file, "wb") as f:
                            for chunk in dl.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                    if os.path.exists(audio_file) and os.path.getsize(audio_file) > 1000000:
                        download_success = True
                        break
        except Exception:
            continue

if not download_success or not os.path.exists(audio_file) or os.path.getsize(audio_file) < 500000:
    print("Full audio file abhi fetch nahi ho saki. 5-second placeholder upload nahi kiya jayega.")
    exit(1)

audio_size_mb = os.path.getsize(audio_file) / (1024 * 1024)
print(f"Full Audio Downloaded Successfully! Size: {audio_size_mb:.2f} MB")

# Step 4: Full HD MP4 Video Render via FFmpeg
print("Step 4: Poore gaane ki Full HD Video render ki ja rahi hai...")
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

final_size_mb = os.path.getsize(output_video) / (1024 * 1024)
print(f"Mukammal Video Rendered! Final Video Size: {final_size_mb:.2f} MB")

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
print(f"Success! Mukammal Video Upload Ho Gayi. Video ID: {new_id}")

uploaded_ids.add(latest_video_id)
with open(TRACKER_FILE, "w") as f:
    json.dump(list(uploaded_ids), f, indent=2)

for f in [audio_file, image_file, output_video]:
    if os.path.exists(f):
        os.remove(f)
