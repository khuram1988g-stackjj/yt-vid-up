import os
import re
import json
import time
import subprocess
import requests
import urllib3
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# OAuth Credentials (Environment Variables priority, split strings as fallback)
CLIENT_ID = os.environ.get("YT_CLIENT_ID") or ("720341227533-" + "9g39h1lb810p6afohnnn7hbl7vsvvut5" + ".apps.googleusercontent.com")
CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET") or ("GOCSPX-" + "09Wi-2SVRUsC45vMc1_F3lit17IW")
REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN") or ("1//06a-LUV_GTjkWCgYIARAAGAYSNwF-" + "L9IrgfCDTBQCEGrOS9I7mIpUAfb-erKjbZWD1EZ209f0mw66R_AMU3wgr9M2Y9nLK_DGsNw")

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

print("Step 1: Audio Library channel ki latest video ID scan ho rahi hai...")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

channel_rss = "https://www.youtube.com/feeds/videos.xml?channel_id=UCht8qITGkBvXKsR1Byln-wA"
video_ids = []
rss_content = ""
try:
    rss_resp = requests.get(channel_rss, headers=headers, timeout=20)
    rss_content = rss_resp.text
    video_ids = re.findall(r'<yt:videoId>([a-zA-Z0-9_-]{11})</yt:videoId>', rss_content)
except Exception as e:
    print(f"[-] RSS feed notice: {e}")

if not video_ids:
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

print(f"\nStep 2: Video ka exact Title, Description aur Tags fetch ho rahe hain: {latest_video_id}...")

title = "Audio Library Music Track"
description = "Provided by Audio Library Automation.\n#music #audiolibrary"
tags = ["music", "audio library", "no copyright music", "free music"]

# 1. Exact Title via Public oEmbed
try:
    oe_res = requests.get(f"https://noembed.com/embed?url={target_url}", timeout=15)
    if oe_res.status_code == 200:
        oe_title = oe_res.json().get("title")
        if oe_title and "YouTube" not in oe_title:
            title = oe_title.strip()
except Exception as e:
    print(f"[-] oEmbed notice: {e}")

# 2. Complete Description Extraction via YouTubei Web Client
try:
    player_url = "https://www.youtube.com/youtubei/v1/player"
    payload = {
        "videoId": latest_video_id,
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20240501.00.00",
                "hl": "en",
                "gl": "US"
            }
        }
    }
    p_resp = requests.post(player_url, json=payload, headers=headers, timeout=20)
    if p_resp.status_code == 200:
        v_details = p_resp.json().get("videoDetails", {})
        if v_details.get("shortDescription") and len(v_details["shortDescription"]) > 100:
            description = v_details["shortDescription"]
        if v_details.get("keywords"):
            tags = v_details["keywords"]
except Exception as e:
    print(f"[-] YouTubei Web player API notice: {e}")

# Agar API se choti mile to RSS Description check karein
if len(description) < 150 and rss_content:
    try:
        desc_matches = re.findall(r'<media:description>([\s\S]*?)</media:description>', rss_content)
        if desc_matches and len(desc_matches[0]) > len(description):
            description = desc_matches[0].strip()
    except Exception:
        pass

print("=" * 60)
print(f"Exact Title: {title}")
print(f"Total Tags ({len(tags)}): {tags[:8]}...")
print(f"Description Length: {len(description)} chars")
print("=" * 60)

output_video = "downloaded_track.mp4"
temp_audio = "audio_track.mp3"
temp_thumb = "cover.jpg"

for f_path in [output_video, temp_audio, temp_thumb]:
    if os.path.exists(f_path):
        os.remove(f_path)

# Download High-Resolution Cover Thumbnail
thumb_url = f"https://i.ytimg.com/vi/{latest_video_id}/maxresdefault.jpg"
th_res = requests.get(thumb_url, headers=headers, timeout=15)
if th_res.status_code != 200:
    thumb_url = f"https://i.ytimg.com/vi/{latest_video_id}/hqdefault.jpg"
    th_res = requests.get(thumb_url, headers=headers, timeout=15)

with open(temp_thumb, "wb") as f:
    f.write(th_res.content)

# ==========================================
# Step 3: Track Audio Download Engine
# ==========================================
print("\nStep 3: Track stream download shuru...")

download_success = False

# Method 1: Description se direct MediaFire / Artist download link
print("[+] Method 1: Description se official download links check ho rahe hain...")
urls_in_desc = re.findall(r'https?://[^\s<>"]+', description)
clean_urls = [u.rstrip('\\').rstrip('.').rstrip(')').rstrip(';') for u in urls_in_desc]

for link in clean_urls:
    if "mediafire.com" in link.lower() or "bit.ly" in link.lower() or "tinyurl" in link.lower():
        try:
            head_res = requests.get(link, headers=headers, timeout=15, allow_redirects=True)
            final_url = head_res.url
            
            if "mediafire.com" in final_url:
                print(f"    MediaFire link mila: {final_url}")
                mf_direct = re.search(r'aria-label="Download file"\s+href="([^"]+)"', head_res.text)
                if not mf_direct:
                    mf_direct = re.search(r'href="((?:https?:)?//download\d+\.mediafire\.com/[^"]+)"', head_res.text)
                if mf_direct:
                    dl_url = mf_direct.group(1)
                    if dl_url.startswith("//"):
                        dl_url = "https:" + dl_url
                    print("    Downloading MP3 from MediaFire...")
                    with requests.get(dl_url, stream=True, timeout=120) as mf_dl:
                        with open(temp_audio, "wb") as f:
                            for chunk in mf_dl.iter_content(chunk_size=1024 * 1024):
                                f.write(chunk)
                    if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 300000:
                        download_success = True
                        break
        except Exception as l_err:
            print(f"    [-] Link resolve notice: {l_err}")

# Method 2: yt-dlp Direct Stream Extraction (Fastest & 100% Reliable Fallback)
if not download_success:
    print("[+] Method 2: Description se download nahi mila. yt-dlp direct stream download...")
    try:
        base_audio = temp_audio.rsplit('.', 1)[0]
        ytdl_cmd = [
            "yt-dlp",
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "192K",
            "--force-overwrites",
            "--no-playlist",
            "-o", f"{base_audio}.%(ext)s",
            target_url
        ]
        subprocess.run(ytdl_cmd, check=True)
        
        if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 300000:
            print(f"    [+] yt-dlp audio extract complete: {os.path.getsize(temp_audio)} bytes")
            download_success = True
    except Exception as yt_err:
        print(f"    [-] yt-dlp extraction failed: {yt_err}")

# Method 3: Cobalt API Fallback (v10 API Structure)
if not download_success:
    print("[+] Method 3: Testing Cobalt v10 Tunnel...")
    cobalt_servers = [
        "https://api.cobalt.tools",
        "https://capi.oak.li"
    ]
    for c_srv in cobalt_servers:
        try:
            payload = {
                "url": target_url,
                "downloadMode": "audio",
                "audioFormat": "mp3"
            }
            c_res = requests.post(
                c_srv,
                json=payload,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0"
                },
                timeout=20
            )
            if c_res.status_code == 200:
                data = c_res.json()
                audio_link = data.get("url")
                if audio_link:
                    print(f"    Downloading from Cobalt instance ({c_srv})...")
                    with requests.get(audio_link, stream=True, timeout=120) as a_dl:
                        with open(temp_audio, "wb") as f:
                            for chunk in a_dl.iter_content(chunk_size=1024 * 1024):
                                f.write(chunk)
                    if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 300000:
                        download_success = True
                        break
        except Exception:
            continue

# Step 3.1: Combine Cover Image + Audio into 1080p MP4
if download_success:
    print("[+] Rendering clean 1080p MP4 with FFmpeg...")
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", temp_thumb,
        "-i", temp_audio,
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
        "-movflags", "+faststart",
        output_video
    ]
    subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if not os.path.exists(output_video) or os.path.getsize(output_video) < 500000:
    print("Download fail ho gaya. File size too small or missing.")
    exit(1)

file_size_mb = os.path.getsize(output_video) / (1024 * 1024)
print(f"\n[+] Video Ready! Size: {file_size_mb:.2f} MB")

# ==========================================
# Step 4: YouTube par PRIVATE upload
# ==========================================
print("\nStep 4: YouTube par PRIVATE upload shuru...")

clean_tags = [str(t)[:30] for t in tags[:30]]

body = {
    'snippet': {
        'title': title[:100],
        'description': description[:5000],
        'tags': clean_tags,
        'categoryId': '10'  # Music category
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
print(f"\n[+] SUCCESS! Video Private Upload Ho Gayi.")
print(f"Uploaded Video URL: https://www.youtube.com/watch?v={new_id}")

# State Tracker update (sirf kamyab upload ke baad)
uploaded_ids.add(latest_video_id)
with open(TRACKER_FILE, "w") as f:
    json.dump(list(uploaded_ids), f, indent=2)

# Cleanup
for f_path in [output_video, temp_audio, temp_thumb]:
    if os.path.exists(f_path):
        os.remove(f_path)
