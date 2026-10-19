"""Check if proxy nodes can connect to Google Gemini.

Caches results in a separate JSON file to keep runs fast and gentle on Google.
Usage: python3 scripts/check_gemini.py merged.txt old_cache.json new_cache.json
"""
import sys
import os
import json
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from merge import key

MAX_TESTS_PER_RUN = 60  # Prevents long runs; remaining nodes test on next runs
WORKERS = 10            # Number of parallel tests
TIMEOUT = 5             # Gemini responds in <2s on live nodes; 5s is plenty


def is_port_open(host, port, timeout=1.5):
    """Quick 1.5s TCP check to eliminate dead servers instantly."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def test_node(line, host, port):
    """Test if a single node can access the Gemini endpoint."""
    # Fast check: skip dead server ports immediately
    if not is_port_open(host, port):
        return False, "Server unreachable"

    proxy = None
    try:
        import requests
        from singbox2proxy import SingBoxProxy

        clean_line = line.split("#")[0]
        proxy = SingBoxProxy(clean_line)

        session = requests.Session()
        session.proxies = proxy.proxy_for_requests

        resp = session.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            timeout=TIMEOUT
        )
        body = resp.text.lower()

        # 1. Google's explicit region block
        if "location" in body and "not supported" in body:
            return False, "Region blocked by Google"

        # 2. Location gate passed! Google verified region and asked for key / gave 200
        if any(term in body for term in ["api key", "api_key", "invalid_argument"]) or resp.status_code == 200:
            return True, "Supported"

        return False, f"HTTP {resp.status_code}"

    except Exception as e:
        return False, f"{type(e).__name__}"
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
                host, port = k[1], k[2]
                node_id = f"{host}|{port}"
                # Test new nodes or re-test nodes not yet marked as working
                if node_id not in cache or not cache[node_id].get("gemini", False):
                    to_test[node_id] = (line, host, port)

    # Limit batch size to keep workflow run under 1-2 minutes
    batch = dict(list(to_test.items())[:MAX_TESTS_PER_RUN])

    if batch:
        print(f"Testing {len(batch)} node(s) for Gemini (capped at {MAX_TESTS_PER_RUN} per run)...", flush=True)
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            # Submit all jobs
            future_to_node = {
                executor.submit(test_node, line, host, port): node_id
                for node_id, (line, host, port) in batch.items()
            }
            # Stream output in real-time as each node finishes
            for future in as_completed(future_to_node):
                node_id = future_to_node[future]
                is_supported, reason = future.result()
                cache[node_id] = {"gemini": is_supported}
                status_icon = "✨ Supported" if is_supported else f"❌ ({reason})"
                print(f"  {node_id} -> {status_icon}", flush=True)
    else:
        print("All nodes already have verified status in cache.", flush=True)

    with open(new_cache_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    main()
