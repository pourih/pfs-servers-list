"""Remove duplicate servers (same host + port). The first one wins, order is kept.

Usage: python3 merge.py all.txt > merged.txt
"""
import sys, base64, json
from urllib.parse import urlsplit


def pad(b):
    return b + "=" * (-len(b) % 4)


def iter_lines(f):
    """Yield plain share links, auto-decoding any Base64-encoded blocks."""
    buf = []

    def flush():
        if not buf:
            return
        chunk = "".join(buf)
        buf.clear()
        try:
            decoded = base64.urlsafe_b64decode(pad(chunk)).decode("utf-8", errors="ignore")
            if "://" in decoded:
                for sub in decoded.splitlines():
                    sub = sub.strip()
                    if "://" in sub and not sub.startswith(("#", "//")):
                        yield sub
        except Exception:
            pass

    for line in f:
        line = line.strip()
        if not line:
            yield from flush()
        elif "://" in line and not line.startswith(("#", "//")):
            yield from flush()
            yield line
        else:
            buf.append(line)
            if line.endswith("="):
                yield from flush()
    yield from flush()


def key(line):
    """Return what identifies a server. Change this to alter what counts as a duplicate."""
    scheme, sep, rest = line.partition("://")
    scheme = scheme.lower()
    body = rest.split("#")[0].split("?")[0]
    try:
        if sep and scheme == "vmess":
            j = json.loads(base64.urlsafe_b64decode(pad(body)))
            host = str(j["add"]).strip().strip("[]").lower()
            port = str(j["port"]).strip()
            if host and port:
                return ("addr", host, port)
        if sep and scheme == "ss" and "@" not in body:
            # legacy format: ss://base64(method:pass@host:port)
            dec = base64.urlsafe_b64decode(pad(body)).decode()
            host, _, port = dec.rsplit("@", 1)[1].rpartition(":")
            host = host.strip("[]").lower()
            if host and port:
                return ("addr", host, port)
        if sep:
            u = urlsplit(scheme + "://" + body)
            if u.hostname and u.port:
                return ("addr", u.hostname.lower(), str(u.port))
    except Exception:
        pass
    return ("raw", line)  # unparseable: fall back to exact-line match


def main():
    seen = set()
    with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
        for line in iter_lines(f):
            k = key(line)
            if k in seen:
                continue
            seen.add(k)
            print(line)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
