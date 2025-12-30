import re
import requests
import sys

class JsUnpacker:
    def __init__(self, p, a, c, k):
        self.p, self.a, self.c, self.k = p, int(a), int(c), k.split('|')
    def encode_base(self, d):
        digits = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        return digits[d] if d < self.a else self.encode_base(d // self.a) + digits[d % self.a]
    def unpack(self):
        k_dict = {self.encode_base(i): (self.k[i] if i < len(self.k) and self.k[i] else self.encode_base(i)) for i in range(self.c)}
        def replace(match): return k_dict.get(match.group(0), match.group(0))
        return re.sub(r'\b\w+\b', replace, self.p)

def get_kwik_data(kwik_url):
    """
    Connects to the Kwik URL, bypasses the packing, and returns:
    {
        "url": The resolved M3U8 URL,
        "cookies": A dictionary of cookies,
        "referer": The referer URL to use (the kwik_url)
    }
    Returns None if extraction fails.
    """
    print(f"Connecting to: {kwik_url} ...")
    headers = {
        "Referer": "https://animepahe.si/", 
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/110.0.0.0 Safari/537.36",
    }
    session = requests.Session()
    try:
        response = session.get(kwik_url, headers=headers)
    except Exception as e:
        print(f"Connection failed: {e}")
        return None

    packed_pattern = r"\}\('(.*?)',(\d+),(\d+),'(.*?)'\.split\('\|'\)"
    matches = list(re.finditer(packed_pattern, response.text, re.DOTALL))
    
    for i, match in enumerate(matches):
        p, a, c, k = match.groups()
        try:
            unpacker = JsUnpacker(p, a, c, k)
            unpacked = unpacker.unpack().replace(r'\/', '/')
            if "m3u8" in unpacked or "const source" in unpacked:
                url_match = re.search(r"const source\s*=\s*['\"](https?://[^'\"]+)['\"]", unpacked)
                m3u8_url = url_match.group(1) if url_match else re.search(r"(https?://[^'\"]+\.m3u8)", unpacked).group(1)
                
                # Convert cookie jar to a simple dict for easier usage
                cookies_dict = session.cookies.get_dict()
                
                return {
                    "url": m3u8_url,
                    "cookies": cookies_dict,
                    "referer": kwik_url,
                    "user_agent": headers["User-Agent"]
                }
        except Exception as e:
            print(f"Error unpacking block {i}: {e}")
            continue
    return None

if __name__ == "__main__":
    # Test Block
    url = "https://kwik.cx/e/3sWT0WnuRWCh"
    data = get_kwik_data(url)
    if data:
        print(f"URL: {data['url']}")
        # Test downloader
        import downloader
        print("Testing Downloader...")
        downloader.download_stream_pure_python(
            data['url'], 
            "test_video.ts", 
            {"User-Agent": data['user_agent'], "Referer": data['referer']},
            data['cookies'],
            lambda p: print(f"Progress: {p}%")
        )
