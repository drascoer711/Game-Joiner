from __future__ import annotations
from typing import Any, Optional
import aiohttp

USERS_API = "https://users.roblox.com/v1"
GROUPS_API = "https://groups.roblox.com/v2"
THUMBNAILS_API = "https://thumbnails.roblox.com/v1"
BADGES_API = "https://badges.roblox.com/v1"

async def request_json(method: str, url: str, **kwargs: Any) -> Optional[dict[str, Any]]:
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(method, url, **kwargs) as response:
                if response.status != 200:
                    return None
                return await response.json()
    except (aiohttp.ClientError, TimeoutError):
        return None

async def find_user(username: str) -> Optional[dict[str, Any]]:
    data = await request_json(
        "POST",
        f"{USERS_API}/usernames/users",
        json={"usernames": [username.strip()], "excludeBannedUsers": False},
    )
    users = data.get("data", []) if data else []
    return users[0] if users else None

async def get_user(user_id: int) -> Optional[dict[str, Any]]:
    return await request_json("GET", f"{USERS_API}/users/{user_id}")

async def get_avatar(user_id: int) -> Optional[str]:
    data = await request_json(
        "GET",
        f"{THUMBNAILS_API}/users/avatar-headshot",
        params={"userIds": str(user_id), "size": "420x420", "format": "Png", "isCircular": "false"},
    )
    avatars = data.get("data", []) if data else []
    return avatars[0].get("imageUrl") if avatars else None

async def get_groups(user_id: int) -> list[dict[str, Any]]:
    data = await request_json("GET", f"{GROUPS_API}/users/{user_id}/groups/roles")
    return data.get("data", []) if data else []

async def get_badges(user_id: int) -> list[dict[str, Any]]:
    data = await request_json("GET", f"{BADGES_API}/users/{user_id}/badges", params={"limit": 10, "sortOrder": "Desc"})
    return data.get("data", []) if data else []

async def resolve(username: str) -> Optional[dict[str, Any]]:
    user = await find_user(username)
    if not user:
        return None
    info = await get_user(int(user["id"]))
    return info or user
