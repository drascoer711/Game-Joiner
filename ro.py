from __future__ import annotations

import aiohttp

ROBLOX_USERS_API = "https://users.roblox.com/v1"
ROBLOX_THUMBNAILS_API = "https://thumbnails.roblox.com/v1"
ROBLOX_GROUPS_API = "https://groups.roblox.com/v1"
ROBLOX_BADGES_API = "https://badges.roblox.com/v1"

async def resolve(username: str) -> dict | None:
    """Resolves a Roblox username to its user ID and basic info."""
    url = f"{ROBLOX_USERS_API}/usernames/users"
    payload = {"usernames": [username], "excludeBannedUsers": True}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            if response.status != 200:
                return None
            data = await response.json()
            users = data.get("data", [])
            if not users:
                return None
            return {
                "id": str(users[0]["id"]),
                "name": users[0]["name"],
                "displayName": users[0].get("displayName", users[0]["name"])
            }

async def get_avatar(user_id: int) -> str | None:
    """Fetches the headshot thumbnail URL for a Roblox user."""
    url = f"{ROBLOX_THUMBNAILS_API}/users/avatar-headshot"
    params = {
        "userIds": user_id,
        "size": "420x420",
        "format": "Png",
        "isCircular": False
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                return None
            data = await response.json()
            data_list = data.get("data", [])
            if not data_list:
                return None
            return data_list[0].get("imageUrl")

async def get_groups(user_id: int) -> list:
    """Fetches a list of public groups a Roblox user belongs to."""
    url = f"{ROBLOX_GROUPS_API}/users/{user_id}/groups/roles"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                return []
            data = await response.json()
            return data.get("data", [])

async def get_badges(user_id: int) -> list:
    """Fetches a list of public badges awarded to a Roblox user."""
    url = f"{ROBLOX_BADGES_API}/users/{user_id}/badges"
    params = {"limit": 100}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                return []
            data = await response.json()
            return data.get("data", [])
