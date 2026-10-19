"""Check if new proxy nodes can connect to Google Gemini / AI Studio.

Caches results in a separate JSON file to keep runs fast and gentle on Google.
Usage: python3 scripts/check_gemini.py merged.txt old_cache.json new_cache.json
"""
import sys
import os
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from merge import key

def test_node(line):
    """Test if a single node can access Google AI Studio."""
    proxy = None
    try:
        from singbox2proxy import SingBoxProxy
        proxy = SingBoxProxy(line)
        proxy_url = proxy.http_proxy_url

        handler = urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
        opener = urllib.request.build_opener(handler)
        req = urllib.request.Request(
            "https://aistudio.google.com",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )

        with opener.open(req, timeout=7) as resp:
            final_url = resp.geturl()
            # If Google redirects to the unsupported region page
            if "available-regions" in final_url or "available_regions" in final_url:
                return False
            return True

    except urllib.error.HTTPError as e:
        # HTTP 403 or redirect headers indicating region block
        if e.code == 403:
            return False
        loc = e.headers.get("Location", "")
        if "available-regions" in loc or "available_regions" in loc:
            return False
        if "accounts.google.com" in loc:
            return True
        return False
    except Exception:
        # Proxy is dead or timed out
        return False
    finally:
        if proxy:
            try:
                proxy.stop()
            except Exception:
                pass


def main():
    merged_file, old_cache_file, new_cache_file = sys.argv[1:4]

    # Load existing cache
    cache = {}
    if os.path.exists(old_cache_file):
        try:
            with open(old_cache_file, encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    # Find nodes that need testing
    to_test = {}
    with open(merged_file, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            k = key(line)
            if k[0] == "addr":
                node_id = f"{k[1]}|{k[2]}"
                if node_id not in cache and node_id not in to_test:
                    to_test[node_id] = line

    if to_test:
        print(f"Testing {len(to_test)} new node(s) for Gemini compatibility...")
        # Test up to 5 proxies at a time
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = executor.map(test_node, to_test.values())
            for node_id, is_supported in zip(to_test.keys(), results):
                cache[node_id] = {"gemini": is_supported}
                status = "✨ Supported" if is_supported else "❌ Blocked"
                print(f"  {node_id} -> {status}")
    else:
        print("No new nodes to test. Gemini cache is up to date.")

    # Save updated cache
    with open(new_cache_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    main()