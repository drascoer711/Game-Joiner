"""Discord Roblox public-information bot.

Commands:
    /user username
    /avatar username
    /groups username
    /badges username
    /scan username
    /check-accounts username1 username2   (administrator only)

The check command compares two usernames that an administrator explicitly
provides. It reports public overlap and never claims that either account is an
alt. Roblox does not provide an official API that confirms alternate accounts.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import aiohttp
import discord
from discord import app_commands


TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN is missing from Replit Secrets.")

USERS_API = "https://users.roblox.com/v1"
GROUPS_API = "https://groups.roblox.com/v2"
THUMBNAILS_API = "https://thumbnails.roblox.com/v1"
BADGES_API = "https://badges.roblox.com/v1"


async def request_json(
    method: str, url: str, **kwargs: Any
) -> Optional[dict[str, Any]]:
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
        params={
            "userIds": str(user_id),
            "size": "420x420",
            "format": "Png",
            "isCircular": "false",
        },
    )
    avatars = data.get("data", []) if data else []
    return avatars[0].get("imageUrl") if avatars else None


async def get_groups(user_id: int) -> list[dict[str, Any]]:
    data = await request_json(
        "GET", f"{GROUPS_API}/users/{user_id}/groups/roles"
    )
    return data.get("data", []) if data else []


async def get_badges(user_id: int) -> list[dict[str, Any]]:
    data = await request_json(
        "GET",
        f"{BADGES_API}/users/{user_id}/badges",
        params={"limit": 10, "sortOrder": "Desc"},
    )
    return data.get("data", []) if data else []


async def resolve(username: str) -> Optional[dict[str, Any]]:
    user = await find_user(username)
    if not user:
        return None
    info = await get_user(int(user["id"]))
    return info or user


class RobloxBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=discord.Intents.none())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} slash commands to guild {guild_id}.")
        else:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} global slash commands.")

    async def on_ready(self) -> None:
        if self.user:
            print(f"Bot online as {self.user} (ID: {self.user.id})")


bot = RobloxBot()


@bot.tree.command(name="user", description="Search for a Roblox user.")
@app_commands.describe(username="Roblox username")
async def user_command(
    interaction: discord.Interaction, username: str
) -> None:
    await interaction.response.defer()
    info = await resolve(username)
    if not info:
        await interaction.followup.send(
            f"Roblox user `{username}` was not found.", ephemeral=True
        )
        return

    user_id = int(info["id"])
    embed = discord.Embed(title="Roblox User", color=discord.Color.blurple())
    embed.add_field(name="Username", value=f"`{info.get('name', 'Unknown')}`")
    embed.add_field(name="Display Name", value=info.get("displayName", "Unknown"))
    embed.add_field(name="User ID", value=f"`{user_id}`")
    embed.add_field(name="Created", value=info.get("created", "Unknown")[:10])
    embed.add_field(
        name="Profile",
        value=f"https://www.roblox.com/users/{user_id}/profile",
        inline=False,
    )
    avatar = await get_avatar(user_id)
    if avatar:
        embed.set_thumbnail(url=avatar)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="avatar", description="Show a Roblox user's avatar.")
@app_commands.describe(username="Roblox username")
async def avatar_command(
    interaction: discord.Interaction, username: str
) -> None:
    await interaction.response.defer()
    info = await resolve(username)
    if not info:
        await interaction.followup.send("Roblox user not found.", ephemeral=True)
        return
    avatar = await get_avatar(int(info["id"]))
    if not avatar:
        await interaction.followup.send("Avatar could not be retrieved.", ephemeral=True)
        return
    embed = discord.Embed(
        title=f"{info.get('name', username)}'s Avatar",
        color=discord.Color.blurple(),
    )
    embed.set_image(url=avatar)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="groups", description="Show a Roblox user's public groups.")
@app_commands.describe(username="Roblox username")
async def groups_command(
    interaction: discord.Interaction, username: str
) -> None:
    await interaction.response.defer()
    info = await resolve(username)
    if not info:
        await interaction.followup.send("Roblox user not found.", ephemeral=True)
        return
    groups = await get_groups(int(info["id"]))
    lines = [
        f"**{entry['group'].get('name', 'Unknown')}** — role: "
        f"`{entry['role'].get('name', 'Unknown')}`"
        for entry in groups[:20]
    ]
    embed = discord.Embed(
        title=f"Groups — {info.get('name', username)}",
        description="\n".join(lines) if lines else "No public groups found.",
        color=discord.Color.blurple(),
    )
    embed.set_footer(text=f"{len(groups)} groups found")
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="badges", description="Show a Roblox user's public badges.")
@app_commands.describe(username="Roblox username")
async def badges_command(
    interaction: discord.Interaction, username: str
) -> None:
    await interaction.response.defer()
    info = await resolve(username)
    if not info:
        await interaction.followup.send("Roblox user not found.", ephemeral=True)
        return
    badges = await get_badges(int(info["id"]))
    description = "\n".join(
        f"• {badge.get('name', 'Unknown')}" for badge in badges
    ) or "No badges found."
    embed = discord.Embed(
        title=f"Badges — {info.get('name', username)}",
        description=description,
        color=discord.Color.gold(),
    )
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="scan", description="Show a Roblox user's public information.")
@app_commands.describe(username="Roblox username")
async def scan_command(
    interaction: discord.Interaction, username: str
) -> None:
    await interaction.response.defer()
    info = await resolve(username)
    if not info:
        await interaction.followup.send("Roblox user not found.", ephemeral=True)
        return
    groups = await get_groups(int(info["id"]))
    badges = await get_badges(int(info["id"]))
    embed = discord.Embed(
        title="Roblox Public Information",
        description=f"Public information for **{info.get('name', username)}**.",
        color=discord.Color.orange(),
    )
    embed.add_field(name="User ID", value=f"`{info['id']}`")
    embed.add_field(name="Created", value=info.get("created", "Unknown")[:10])
    embed.add_field(name="Groups", value=str(len(groups)))
    embed.add_field(name="Badges Retrieved", value=str(len(badges)))
    embed.add_field(
        name="Privacy",
        value="This uses public Roblox information only; it does not access private data.",
        inline=False,
    )
    avatar = await get_avatar(int(info["id"]))
    if avatar:
        embed.set_thumbnail(url=avatar)
    await interaction.followup.send(embed=embed)


@bot.tree.command(
    name="check-accounts",
    description="Admin-only comparison of two Roblox accounts.",
)
@app_commands.describe(
    username1="First Roblox username",
    username2="Second Roblox username",
)
@app_commands.checks.has_permissions(administrator=True)
async def check_accounts(
    interaction: discord.Interaction, username1: str, username2: str
) -> None:
    await interaction.response.defer(ephemeral=True)
    first, second = await __import__("asyncio").gather(
        resolve(username1), resolve(username2)
    )
    if not first or not second:
        await interaction.followup.send(
            "One or both Roblox users were not found.", ephemeral=True
        )
        return

    first_groups, second_groups = await __import__("asyncio").gather(
        get_groups(int(first["id"])), get_groups(int(second["id"]))
    )
    first_by_id = {entry["group"]["id"]: entry["group"]["name"] for entry in first_groups}
    second_ids = {entry["group"]["id"] for entry in second_groups}
    shared_names = [
        name for group_id, name in first_by_id.items() if group_id in second_ids
    ]
    shared_text = ", ".join(shared_names[:15]) if shared_names else "None found"

    embed = discord.Embed(
        title="Roblox Account Comparison",
        description=(
            f"Public comparison of **{first.get('name', username1)}** and "
            f"**{second.get('name', username2)}**."
        ),
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Shared public groups", value=shared_text, inline=False)
    embed.add_field(
        name="Account IDs",
        value=f"`{first['id']}` and `{second['id']}`",
        inline=False,
    )
    embed.add_field(
        name="Important",
        value=(
            "Shared groups or similar public details do not prove account "
            "ownership or an alternate account."
        ),
        inline=False,
    )
    await interaction.followup.send(embed=embed, ephemeral=True)


@check_accounts.error
async def check_accounts_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        message = "Only Discord server administrators can use this command."
    else:
        message = "The account comparison could not be completed."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


bot.run(TOKEN)