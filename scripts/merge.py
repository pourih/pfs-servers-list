"""Remove duplicate servers (same host + port). The first one wins, order is kept.

Usage: python3 merge.py all.txt > merged.txt
"""
import sys, base64, json
from urllib.parse import urlsplit


def pad(b):
    return b + "=" * (-len(b) % 4)


def key(line):
    """Return what identifies a server. Change this to alter what counts as a duplicate."""
    scheme, sep, rest = line.partition("://")
    scheme = scheme.lower()
    body = rest.split("#")[0].split("?")[0]
    try:
        if sep and scheme == "vmess":
            j = json.loads(base64.b64decode(pad(body)))
            return ("addr", str(j["add"]).strip().lower(), str(j["port"]).strip())
        if sep and scheme == "ss" and "@" not in body:
            # legacy format: ss://base64(method:pass@host:port)
            dec = base64.urlsafe_b64decode(pad(body)).decode()
            host, _, port = dec.rsplit("@", 1)[1].rpartition(":")
            return ("addr", host.strip("[]").lower(), port)
        if sep:
            u = urlsplit(line)
            if u.hostname and u.port:
                return ("addr", u.hostname.lower(), str(u.port))
    except Exception:
        pass
    return ("raw", line)  # unparseable: fall back to exact-line match


def main():
    seen = set()
    with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            k = key(line)
            if k in seen:
                continue
            seen.add(k)
            print(line)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
