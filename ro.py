import aiohttp

async def resolve(username: str):
    async with aiohttp.ClientSession() as session:
        async with session.post("https://users.roblox.com/v1/usernames/users", json={"usernames": [username], "excludeBannedUsers": True}) as resp:
            if resp.status == 200:
                data = await resp.json()
                users = data.get("data", [])
                if users:
                    return {"id": users[0]["id"], "name": users[0]["name"]}
    return None

async def get_avatar(user_id: int):
    async with aiohttp.ClientSession() as session:
        url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=420x420&format=Png&isCircular=false"
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                data_list = data.get("data", [])
                if data_list:
                    return data_list[0].get("imageUrl")
    return None

async def get_groups(user_id: int):
    async with aiohttp.ClientSession() as session:
        url = f"https://groups.roblox.com/v1/users/{user_id}/groups/roles"
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("data", [])
    return []

async def get_badges(user_id: int):
    async with aiohttp.ClientSession() as session:
        url = f"https://badges.roblox.com/v1/users/{user_id}/badges?limit=10&sortOrder=Desc"
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("data", [])
    return []
