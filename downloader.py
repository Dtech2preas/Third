import requests
import concurrent.futures
import time
import os
import random

def download_segment(args):
    """
    Worker function to download a single segment.
    """
    index, url, headers, cookies, retries = args
    
    for attempt in range(retries):
        try:
            # Small random delay to avoid rate limiting
            time.sleep(random.uniform(0.1, 0.5))
            
            response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
            if response.status_code == 200:
                return (index, response.content)
            elif response.status_code == 429: # Rate Limited
                time.sleep(1 * (attempt + 1))
        except Exception:
            pass
        time.sleep(0.5)
            
    return (index, None)

def download_stream_pure_python(m3u8_url, output_path, headers, cookies, callback=None):
    """
    Downloads an HLS stream by fetching segments and concatenating them.
    pure_python = No FFmpeg required.
    
    callback: function(progress_percent)
    """
    try:
        # 1. Get Playlist
        print(f"Fetching playlist: {m3u8_url}")
        playlist_resp = requests.get(m3u8_url, headers=headers, cookies=cookies)
        if playlist_resp.status_code != 200:
            print("Failed to fetch playlist")
            return False

        base_url = m3u8_url.rsplit('/', 1)[0] + "/"
        lines = playlist_resp.text.splitlines()
        
        # Filter out comments/tags, keep only .ts URLs (or relative paths)
        # Note: Some HLS playlists might be nested (master playlist), but Kwik usually gives the media playlist directly.
        segments = [line for line in lines if line and not line.startswith("#")]
        
        total_segments = len(segments)
        print(f"Found {total_segments} segments.")
        
        if total_segments == 0:
            print("No segments found.")
            return False

        # 2. Prepare Tasks
        tasks = []
        for i, seg in enumerate(segments):
            seg_url = seg if seg.startswith("http") else base_url + seg
            tasks.append((i, seg_url, headers, cookies, 5)) # 5 retries

        downloaded_parts = {}
        completed_count = 0
        
        # 3. Download concurrently
        # Limit max_workers to prevent crashing the phone or getting banned
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(download_segment, t) for t in tasks]
            
            for future in concurrent.futures.as_completed(futures):
                idx, content = future.result()
                if content:
                    downloaded_parts[idx] = content
                    completed_count += 1
                    
                    if callback:
                        progress = int((completed_count / total_segments) * 100)
                        callback(progress)
                else:
                    print(f"Failed to download segment {idx}")

        # 4. Stitch
        if len(downloaded_parts) != total_segments:
            print(f"Warning: Downloaded {len(downloaded_parts)}/{total_segments} segments. Video may be incomplete.")
        
        print("Stitching file...")
        with open(output_path, 'wb') as outfile:
            for i in range(total_segments):
                if i in downloaded_parts:
                    outfile.write(downloaded_parts[i])
                    
        print(f"Saved to {output_path}")
        return True
        
    except Exception as e:
        print(f"Download Error: {e}")
        return False
