#!/usr/bin/env python3
"""
Discord Roblox public-information bot with dedicated channel logging & Flask keep-alive.

Commands:
    /user username
    /avatar username
    /groups username
    /badges username
    /scan username
    /check-accounts username1 username2   (admin/owner only)
    /check-discord account1 account2      (admin/owner only)
    /clear-global                         (owner only)
"""

from __future__ import annotations

import os
import difflib
import traceback
from datetime import datetime, timezone
from typing import Any, Optional
import asyncio
from threading import Thread

import aiohttp
import discord
from discord import app_commands
from flask import Flask

# --- FLASK KEEP-ALIVE WEB SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()


TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN is missing from Replit Secrets.")

APP_OWNER_ID = int(os.getenv("APP_OWNER_ID", "1256992368477864029") or 1256992368477864029)
REQUIRED_ROLE_ID = int(os.getenv("REQUIRED_ROLE_ID", "1457867706790580317") or 1457867706790580317)
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID", "").strip()

# Logging Channel IDs
ALL_LOGS_CHANNEL_ID = 1540448203323875430
FAILED_LOGS_CHANNEL_ID = 1540449747179937913

USERS_API = "https://users.roblox.com/v1"
GROUPS_API = "https://groups.roblox.com/v2"
THUMBNAILS_API = "https://thumbnails.roblox.com/v1"
BADGES_API = "https://badges.roblox.com/v1"
FRIENDS_API = "https://friends.roblox.com/v1"
AVATAR_API = "https://avatar.roblox.com/v1"
GAMES_API = "https://games.roblox.com/v2"


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


async def get_avatar_assets(user_id: int) -> list[dict[str, Any]]:
    data = await request_json("GET", f"{AVATAR_API}/users/{user_id}/avatar")
    return data.get("assets", []) if data else []


async def get_favorite_games(user_id: int) -> list[dict[str, Any]]:
    data = await request_json(
        "GET",
        f"{GAMES_API}/users/{user_id}/favorite/games",
        params={"sortOrder": "Desc", "limit": 50},
    )
    return data.get("data", []) if data else []


async def get_friend_page(
    endpoint: str, user_id: int, cursor: Optional[str] = None
) -> Optional[dict[str, Any]]:
    params: dict[str, Any] = {"limit": 100, "sortOrder": "Asc"}
    if cursor:
        params["cursor"] = cursor
    return await request_json("GET", f"{FRIENDS_API}/users/{user_id}/{endpoint}", params=params)


async def get_social_accounts(
    user_id: int, endpoint: str
) -> list[dict[str, Any]]:
    accounts: list[dict[str, Any]] = []
    cursor: Optional[str] = None
    while True:
        page = await get_friend_page(endpoint, user_id, cursor)
        if not page:
            return accounts
        accounts.extend(page.get("data", []))
        cursor = page.get("nextPageCursor")
        if not cursor:
            return accounts


async def resolve(username: str) -> Optional[dict[str, Any]]:
    user = await find_user(username)
    if not user:
        return None
    info = await get_user(int(user["id"]))
    return info or user


async def fetch_discord_profile(user_id: int) -> discord.User:
    return await bot.fetch_user(user_id)


async def log_to_channel(channel_id: int, content: str) -> None:
    """Helper to safely post log strings to a Discord channel in the background."""
    try:
        channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            if len(content) > 1990:
                content = content[:1987] + "..."
            await channel.send(content)
    except Exception as e:
        print(f"Failed to send log to channel {channel_id}: {e}")


class RequiredRoleError(app_commands.CheckFailure):
    """Raised when a member is not allowed to use the bot."""


async def has_bot_access(interaction: discord.Interaction) -> bool:
    if APP_OWNER_ID and interaction.user.id == APP_OWNER_ID:
        return True
    roles = getattr(interaction.user, "roles", [])
    if REQUIRED_ROLE_ID and any(role.id == REQUIRED_ROLE_ID for role in roles):
        return True
    raise RequiredRoleError(
        "You need the required bot access role to use this command."
    )


def owner_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if APP_OWNER_ID and interaction.user.id == APP_OWNER_ID:
            return True
        raise app_commands.CheckFailure("Only the configured app owner can use this command.")
    return app_commands.check(predicate)


class RobloxCommandTree(app_commands.CommandTree):
    async def on_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        print(f"Slash command error: {error}")
        tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))

        fail_msg = (
            f"❌ **Command Failed**\n"
            f"• **Command:** `/{interaction.command.name if interaction.command else 'unknown'}`\n"
            f"• **User:** {interaction.user} (`{interaction.user.id}`)\n"
            f"• **Error Type:** `{type(error).__name__}`\n"
            f"• **Details:** `{error}`\n"
            f"
http://googleusercontent.com/immersive_entry_chip/0
