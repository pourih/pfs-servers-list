"""Check if proxy nodes can connect to Google Gemini.

Caches results in a separate JSON file to keep runs fast and gentle on Google.
Usage: python3 scripts/check_gemini.py merged.txt old_cache.json new_cache.json
"""
import sys
import os
import json
from concurrent.futures import ThreadPoolExecutor
from merge import key

def test_node(line):
    """Test if a single node can access the Gemini endpoint."""
    proxy = None
    try:
        from singbox2proxy import SingBoxProxy
        proxy = SingBoxProxy(line)

        # Query the official Gemini API endpoint
        resp = proxy.request(
            "GET",
            "https://generativelanguage.googleapis.com/v1beta/models",
            timeout=8
        )
        body = resp.text

        # If Google rejects based on region:
        if "User location is not supported" in body:
            return False, "Region blocked by Google"

        # If Google passed the location gate (asks for API key or returns 200):
        if "API key not valid" in body or resp.status_code == 200:
            return True, "Supported"

        return False, f"HTTP {resp.status_code} - unexpected response"

    except Exception as e:
        return False, f"Connection error: {type(e).__name__}"
    finally:
        if proxy:
            try:
                proxy.stop()
            except Exception:
                pass


def main():
    merged_file, old_cache_file, new_cache_file = sys.argv[1:4]

    cache = {}
    if os.path.exists(old_cache_file):
        try:
            with open(old_cache_file, encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    to_test = {}
    with open(merged_file, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            k = key(line)
            if k[0] == "addr":
                node_id = f"{k[1]}|{k[2]}"
                # Test nodes not in cache, or re-test nodes that previously failed
                if node_id not in cache or not cache[node_id].get("gemini", False):
                    to_test[node_id] = line

    if to_test:
        print(f"Testing {len(to_test)} node(s) for Gemini compatibility...")
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_node = {executor.submit(test_node, line): node_id for node_id, line in to_test.items()}
            for future in future_to_node:
                node_id = future_to_node[future]
                is_supported, reason = future.result()
                cache[node_id] = {"gemini": is_supported}
                status_icon = "✨ Supported" if is_supported else f"❌ ({reason})"
                print(f"  {node_id} -> {status_icon}")
    else:
        print("All nodes already have verified status in cache.")

    with open(new_cache_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    main()
