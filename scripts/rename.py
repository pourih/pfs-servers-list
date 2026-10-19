"""Give every server a name like Alpha-M10-D18 and remember it between runs.

Name = NATO word(s) + month (M) + day (D) the server was first seen.
If the single words run out on a day, two words are used: Alpha-Alpha-M10-D18.

Usage: python3 rename.py merged.txt old_names.json new_names.json [gemini_cache.json] > named.txt
"""
import sys, os, json, base64, itertools
from datetime import datetime, timezone, timedelta
from merge import key, pad

NATO = [
    "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel",
    "India", "Juliett", "Kilo", "Lima", "Mike", "November", "Oscar", "Papa",
    "Quebec", "Romeo", "Sierra", "Tango", "Uniform", "Victor", "Whiskey",
    "Xray", "Yankee", "Zulu",
]
FORGET_AFTER_DAYS = 30


def word_parts():
    n = 1
    while True:
        for combo in itertools.product(NATO, repeat=n):
            yield "-".join(combo)
        n += 1


def new_name(used, today):
    for words in word_parts():
        name = "%s-M%02d-D%02d" % (words, today.month, today.day)
        if name not in used:
            return name


def set_remark(line, name):
    scheme, _, rest = line.partition("://")
    if scheme.lower() == "vmess":
        body = rest.split("#")[0]
        j = json.loads(base64.b64decode(pad(body)))
        j["ps"] = name
        raw = json.dumps(j, ensure_ascii=False).encode("utf-8")
        return scheme + "://" + base64.b64encode(raw).decode()
    return line.split("#")[0] + "#" + name


def main():
    merged_file, old_file, new_file = sys.argv[1:4]
    gemini_file = sys.argv[4] if len(sys.argv) > 4 else None

    today = datetime.now(timezone.utc).date()
    cutoff = (today - timedelta(days=FORGET_AFTER_DAYS)).isoformat()

    # Load existing server names
    records = {}
    if os.path.exists(old_file):
        with open(old_file, encoding="utf-8") as f:
            records = {k: v for k, v in json.load(f).items() if v["last_seen"] >= cutoff}
    used = {v["name"] for v in records.values()}

    # Load Gemini status cache if present
    gemini_cache = {}
    if gemini_file and os.path.exists(gemini_file):
        try:
            with open(gemini_file, encoding="utf-8") as f:
                gemini_cache = json.load(f)
        except Exception:
            gemini_cache = {}

    with open(merged_file, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            k = key(line)
            if k[0] != "addr":
                print(line)
                continue

            node = "%s|%s" % (k[1], k[2])
            name = records[node]["name"] if node in records else new_name(used, today)

            # Prepend ✨ if node connects to Gemini
            is_gemini = gemini_cache.get(node, {}).get("gemini", False)
            display_name = f"✨ {name}" if is_gemini else name

            try:
                print(set_remark(line, display_name))
            except Exception:
                print(line)
                continue

            used.add(name)
            records[node] = {"name": name, "last_seen": today.isoformat()}

    with open(new_file, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
