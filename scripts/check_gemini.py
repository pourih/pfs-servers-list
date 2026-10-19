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
        import requests
        from singbox2proxy import SingBoxProxy

        # Strip remark fragment (#tag) so special characters/emojis don't break the parser
        clean_line = line.split("#")[0]
        proxy = SingBoxProxy(clean_line)

        # Connect through the proxy using standard requests
        session = requests.Session()
        session.proxies = proxy.proxy_for_requests

        resp = session.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            timeout=12
        )
        body = resp.text.lower()

        # 1. Google's explicit region block
        if "location" in body and "not supported" in body:
            return False, "Region blocked by Google"

        # 2. Location gate passed! Google verified region and asked for key / gave 200
        if any(term in body for term in ["api key", "api_key", "invalid_argument"]) or resp.status_code == 200:
            return True, "Supported"

        return False, f"HTTP {resp.status_code}: {resp.text[:50]}"

    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
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
                # Test new nodes AND re-test nodes previously marked as false
                if node_id not in cache or not cache[node_id].get("gemini", False):
                    to_test[node_id] = line

    if to_test:
        print(f"Testing {len(to_test)} node(s) for Gemini compatibility...")
        with ThreadPoolExecutor(max_workers=3) as executor:
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
