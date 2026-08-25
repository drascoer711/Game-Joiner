# whitelist.py
# Simple persistent whitelist stored as a JSON array of user ID strings.
# The file is created automatically if it doesn't exist.

import json
import os
from typing import List

PATH = "whitelist.json"
_whitelist: List[str] = []

def load_whitelist() -> None:
    """Load whitelist from disk (creates file if missing)."""
    global _whitelist
    if os.path.exists(PATH):
        try:
            with open(PATH, "r", encoding="utf8") as f:
                data = json.load(f)
                _whitelist = [str(x) for x in data] if isinstance(data, list) else []
        except Exception:
            _whitelist = []
            save_whitelist()
    else:
        _whitelist = []
        save_whitelist()

def save_whitelist() -> None:
    """Persist whitelist to disk."""
    with open(PATH, "w", encoding="utf8") as f:
        json.dump(_whitelist, f, indent=2)

def is_whitelisted(user_id: int) -> bool:
    """Return True if the provided user ID is on the whitelist."""
    return str(user_id) in _whitelist

def add_whitelist(user_id: int) -> bool:
    """Add a user to the whitelist. Returns True if added, False if already present."""
    s = str(user_id)
    if s not in _whitelist:
        _whitelist.append(s)
        save_whitelist()
        return True
    return False

def remove_whitelist(user_id: int) -> bool:
    """Remove a user from the whitelist. Returns True if removed, False if not present."""
    s = str(user_id)
    if s in _whitelist:
        _whitelist.remove(s)
        save_whitelist()
        return True
    return False

def list_whitelist() -> List[str]:
    """Return the whitelist as a list of strings (user IDs)."""
    return list(_whitelist)