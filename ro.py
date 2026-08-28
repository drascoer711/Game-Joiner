import json
import urllib.request
import urllib.parse
import asyncio

async def resolve(username: str):
    def _fetch():
        url = "https://users.roblox.com/v1/usernames/users"
        payload = json.dumps({"usernames": [username], "excludeBannedUsers": True}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    users = data.get("data", [])
                    if users:
                        return {"id": users[0]["id"], "name": users[0]["name"]}
        except Exception:
            pass
        return None
    return await asyncio.to_thread(_fetch)

async def get_avatar(user_id: int):
    def _fetch():
        url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=420x420&format=Png&isCircular=false"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    data_list = data.get("data", [])
                    if data_list:
                        return data_list[0].get("imageUrl")
        except Exception:
            pass
        return None
    return await asyncio.to_thread(_fetch)

async def get_groups(user_id: int):
    def _fetch():
        url = f"https://groups.roblox.com/v1/users/{user_id}/groups/roles"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data.get("data", [])
        except Exception:
            pass
        return []
    return await asyncio.to_thread(_fetch)

async def get_badges(user_id: int):
    def _fetch():
        url = f"https://badges.roblox.com/v1/users/{user_id}/badges?limit=10&sortOrder=Desc"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data.get("data", [])
        except Exception:
            pass
        return []
    return await asyncio.to_thread(_fetch)
