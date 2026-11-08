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

try:
    oe_res = requests.get(f"https://noembed.com/embed?url={target_url}", timeout=15)
    if oe_res.status_code == 200:
        oe_title = oe_res.json().get("title")
        if oe_title and "YouTube" not in oe_title:
            title = oe_title.strip()
except Exception as e:
    print(f"[-] oEmbed notice: {e}")

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

thumb_url = f"https://i.ytimg.com/vi/{latest_video_id}/maxresdefault.jpg"
th_res = requests.get(thumb_url, headers=headers, timeout=15)
if th_res.status_code != 200:
    thumb_url = f"https://i.ytimg.com/vi/{latest_video_id}/hqdefault.jpg"
    th_res = requests.get(thumb_url, headers=headers, timeout=15)

with open(temp_thumb, "wb") as f:
    f.write(th_res.content)

# Step 3: Multi-Tunnel Audio Downloader
print("\nStep 3: Track stream download shuru...")

download_success = False

# Method 1: Official AudioLibrary.com.co Direct MP3 Resolver
print("[+] Method 1: Searching AudioLibrary / MediaFire link...")
urls_in_desc = re.findall(r'https?://[^\s<>"]+', description)
for link in urls_in_desc:
    clean_link = link.rstrip('\\').rstrip('.').rstrip(')').rstrip(';')
    if any(k in clean_link.lower() for k in ["audiolibrary.com.co", "mediafire.com"]):
        try:
            r = requests.get(clean_link, headers=headers, timeout=15, allow_redirects=True)
            # MediaFire match
            mf = re.search(r'href="((?:https?:)?//download\d+\.mediafire\.com/[^"]+)"', r.text)
            if mf:
                dl_url = mf.group(1)
                if dl_url.startswith("//"): dl_url = "https:" + dl_url
                print(f"    Direct MP3 found on MediaFire: {dl_url[:45]}...")
                with requests.get(dl_url, stream=True, timeout=120) as mf_dl:
                    with open(temp_audio, "wb") as f:
                        for chunk in mf_dl.iter_content(chunk_size=1024 * 1024):
                            f.write(chunk)
                if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 300000:
                    download_success = True
                    break
        except Exception:
            continue

# Method 2: Rapid MP3 Tunnel via Loader.to API
if not download_success:
    print("[+] Method 2: Testing Rapid MP3 Tunnel API...")
    try:
        init_url = f"https://loader.to/ajax/download.php?button=1&start=1&end=1&format=mp3&url={target_url}"
        r_init = requests.get(init_url, headers=headers, timeout=15).json()
        task_id = r_init.get("id")
        if task_id:
            print(f"    Tunnel task created (ID: {task_id}). Waiting for audio conversion...")
            for _ in range(12):
                time.sleep(3)
                p_url = f"https://loader.to/ajax/progress.php?id={task_id}"
                p_res = requests.get(p_url, headers=headers, timeout=15).json()
                if p_res.get("success") == 1 and p_res.get("download_url"):
                    audio_dl_url = p_res["download_url"]
                    print("    Downloading converted MP3 stream...")
                    with requests.get(audio_dl_url, stream=True, timeout=120) as a_stream:
                        with open(temp_audio, "wb") as f:
                            for chunk in a_stream.iter_content(chunk_size=1024 * 1024):
                                f.write(chunk)
                    if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 300000:
                        download_success = True
                        break
                elif p_res.get("text") == "Error":
                    break
    except Exception as e:
        print(f"    [-] Rapid Tunnel notice: {e}")

# Method 3: Invidious Public Instances (Rotated audio stream fallback)
if not download_success:
    print("[+] Method 3: Testing Invidious Instances...")
    invidious_hosts = [
        "https://inv.nadeko.net",
        "https://invidious.nerdvpn.de",
        "https://yewtu.be"
    ]
    for host in invidious_hosts:
        try:
            api_endpoint = f"{host}/api/v1/videos/{latest_video_id}"
            iv_res = requests.get(api_endpoint, headers=headers, timeout=10)
            if iv_res.status_code == 200:
                data = iv_res.json()
                formats = data.get("adaptiveFormats", [])
                audio_fmts = [f for f in formats if f.get("type", "").startswith("audio/")]
                if audio_fmts:
                    best_audio = sorted(audio_fmts, key=lambda x: int(x.get("bitrate", 0)), reverse=True)[0]
                    stream_url = best_audio.get("url")
                    if stream_url:
                        print(f"    Extracting audio via {host}...")
                        raw_temp = "raw_stream.bin"
                        with requests.get(stream_url, stream=True, timeout=120) as r_dl:
                            with open(raw_temp, "wb") as f:
                                for chunk in r_dl.iter_content(chunk_size=1024 * 1024):
                                    f.write(chunk)
                        
                        subprocess.run([
                            "ffmpeg", "-y", "-i", raw_temp, "-vn", "-c:a", "libmp3lame", "-b:a", "192k", temp_audio
                        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        
                        if os.path.exists(raw_temp):
                            os.remove(raw_temp)
                        if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 300000:
                            download_success = True
                            break
        except Exception:
            continue

# Method 4: yt-dlp with TV/IOS Client Bypass (agar cookies maujood hon ya JS bypass ho sake)
if not download_success:
    print("[+] Method 4: yt-dlp tv client fallback...")
    try:
        base_audio = temp_audio.rsplit('.', 1)[0]
        ytdl_cmd = [
            "yt-dlp",
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "192K",
            "--force-overwrites",
            "--no-playlist",
            "--extractor-args", "youtube:player_client=tv_embedded,ios",
            "-o", f"{base_audio}.%(ext)s",
            target_url
        ]
        if os.path.exists("cookies.txt"):
            ytdl_cmd.extend(["--cookies", "cookies.txt"])
            
        subprocess.run(ytdl_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 300000:
            download_success = True
    except Exception:
        pass

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

# Step 4: YouTube par PRIVATE upload with Full Metadata
print("\nStep 4: YouTube par PRIVATE upload shuru...")

clean_tags = [str(t)[:30] for t in tags[:30]]

body = {
    'snippet': {
        'title': title[:100],
        'description': description[:5000],
        'tags': clean_tags,
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
print(f"\n[+] SUCCESS! Video Private Upload Ho Gayi.")
print(f"Uploaded Video URL: https://www.youtube.com/watch?v={new_id}")

uploaded_ids.add(latest_video_id)
with open(TRACKER_FILE, "w") as f:
    json.dump(list(uploaded_ids), f, indent=2)

for f_path in [output_video, temp_audio, temp_thumb]:
    if os.path.exists(f_path):
        os.remove(f_path)
