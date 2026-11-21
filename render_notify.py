"""Send Render build/startup failure notices to the configured Discord channel.

Uses only Python's standard library so it also works when dependency
installation itself is what failed.
"""

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CHANNEL_ID = "1540449747179937913"


def notify(message: str) -> bool:
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        print(
            "[RENDER ALERT] DISCORD_BOT_TOKEN is unavailable; "
            "cannot send deployment failure notice.",
            file=sys.stderr,
        )
        return False

    content = (message or "Render deployment failed, but no error details were provided.")[:1900]
    payload = json.dumps({"content": content, "allowed_mentions": {"parse": []}}).encode("utf-8")
    request = Request(
        f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages",
        data=payload,
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
            "User-Agent": "Game-Joiner-Render-Notifier/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            if response.status not in (200, 201):
                print(f"[RENDER ALERT] Discord API returned HTTP {response.status}.", file=sys.stderr)
                return False
        print(f"[RENDER ALERT] Deployment failure notice sent to channel {CHANNEL_ID}.")
        return True
    except HTTPError as error:
        print(f"[RENDER ALERT] Discord API returned HTTP {error.code}.", file=sys.stderr)
    except (URLError, TimeoutError, OSError) as error:
        print(f"[RENDER ALERT] Could not reach Discord: {error}", file=sys.stderr)
    return False


if __name__ == "__main__":
    notify(" ".join(sys.argv[1:]))
