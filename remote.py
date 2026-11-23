import base64
import urllib.error
import urllib.request


def attachment_uploaded(url: str, username: str, password: str, key: str) -> bool:
    request = urllib.request.Request(f"{url}/zotero/{key}.zip", method="PROPFIND")
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    request.add_header("Authorization", f"Basic {token}")
    request.add_header("Depth", "0")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except (urllib.error.HTTPError, urllib.error.URLError):
        return False
