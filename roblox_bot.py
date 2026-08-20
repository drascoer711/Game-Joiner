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
import difflib
import traceback
from datetime import datetime, timezone
from typing import Any, Optional
import asyncio

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
    """Read public friend/follower pages until Roblox has no next cursor."""

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


class RobloxCommandTree(app_commands.CommandTree):
    async def on_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        """Always acknowledge command failures instead of leaving Discord waiting."""

        print(f"Slash command error: {error}")
        traceback.print_exception(error)
        message = "The command could not complete. Please try again."
        if isinstance(error, app_commands.MissingPermissions):
            message = "Only Discord server administrators can use this command."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.DiscordException as response_error:
            print(f"Could not send slash-command error response: {response_error}")


class RobloxBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=discord.Intents.none())
        self.tree = RobloxCommandTree(self)

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
    first, second = await asyncio.gather(resolve(username1), resolve(username2))
    if not first or not second:
        await interaction.followup.send(
            "One or both Roblox users were not found.", ephemeral=True
        )
        return

    first_id = int(first["id"])
    second_id = int(second["id"])
    (
        first_groups,
        second_groups,
        first_friends,
        second_friends,
        first_followers,
        second_followers,
        first_followings,
        second_followings,
        first_badges,
        second_badges,
        first_avatar,
        second_avatar,
        first_games,
        second_games,
    ) = await asyncio.gather(
        get_groups(first_id),
        get_groups(second_id),
        get_social_accounts(first_id, "friends"),
        get_social_accounts(second_id, "friends"),
        get_social_accounts(first_id, "followers"),
        get_social_accounts(second_id, "followers"),
        get_social_accounts(first_id, "followings"),
        get_social_accounts(second_id, "followings"),
        get_badges(first_id),
        get_badges(second_id),
        get_avatar_assets(first_id),
        get_avatar_assets(second_id),
        get_favorite_games(first_id),
        get_favorite_games(second_id),
    )

    first_by_id = {
        entry["group"]["id"]: entry["group"].get("name", "Unknown")
        for entry in first_groups
    }
    second_ids = {entry["group"]["id"] for entry in second_groups}
    shared_names = [
        name for group_id, name in first_by_id.items() if group_id in second_ids
    ]

    def account_ids(accounts: list[dict[str, Any]]) -> set[int]:
        return {int(account["id"]) for account in accounts if account.get("id")}

    def account_names(
        accounts: list[dict[str, Any]], shared_ids: set[int]
    ) -> list[str]:
        return [
            str(account.get("name", account.get("displayName", account["id"])))
            for account in accounts
            if int(account.get("id", -1)) in shared_ids
        ]

    shared_friend_ids = account_ids(first_friends) & account_ids(second_friends)
    shared_follower_ids = account_ids(first_followers) & account_ids(second_followers)
    shared_following_ids = account_ids(first_followings) & account_ids(second_followings)
    shared_badge_ids = {
        int(badge["id"])
        for badge in first_badges
        if badge.get("id")
    } & {
        int(badge["id"])
        for badge in second_badges
        if badge.get("id")
    }
    first_asset_names = {
        str(asset.get("name", asset.get("id")))
        for asset in first_avatar
    }
    second_asset_names = {
        str(asset.get("name", asset.get("id")))
        for asset in second_avatar
    }
    first_asset_ids = {int(asset["id"]) for asset in first_avatar if asset.get("id")}
    second_asset_ids = {int(asset["id"]) for asset in second_avatar if asset.get("id")}
    shared_assets = sorted(first_asset_names & second_asset_names)
    shared_asset_ids = first_asset_ids & second_asset_ids

    first_game_ids = {int(game["id"]) for game in first_games if game.get("id")}
    second_game_ids = {int(game["id"]) for game in second_games if game.get("id")}
    shared_game_ids = first_game_ids & second_game_ids
    first_game_names = {
        int(game["id"]): str(game.get("name", game["id"]))
        for game in first_games
        if game.get("id")
    }
    shared_game_names = [
        first_game_names[game_id]
        for game_id in sorted(shared_game_ids)
        if game_id in first_game_names
    ]
    first_badge_names = {
        int(badge["id"]): str(badge.get("name", badge["id"]))
        for badge in first_badges
        if badge.get("id")
    }
    second_badge_ids = {
        int(badge["id"]) for badge in second_badges if badge.get("id")
    }
    shared_badge_names = [
        first_badge_names[badge_id]
        for badge_id in sorted(shared_badge_ids)
        if badge_id in first_badge_names and badge_id in second_badge_ids
    ]
    first_roles = {
        entry["group"]["id"]: entry["role"].get("name", "Unknown")
        for entry in first_groups
    }
    second_roles = {
        entry["group"]["id"]: entry["role"].get("name", "Unknown")
        for entry in second_groups
    }
    shared_role_names = [
        f"{first_by_id[group_id]} ({role_name})"
        for group_id, role_name in first_roles.items()
        if group_id in second_roles and role_name == second_roles[group_id]
    ]

    def text_similarity(first_text: str, second_text: str) -> float:
        return difflib.SequenceMatcher(
            None, first_text.casefold().strip(), second_text.casefold().strip()
        ).ratio()

    def account_age_similarity() -> float:
        try:
            first_created = datetime.fromisoformat(
                str(first.get("created", "")).replace("Z", "+00:00")
            )
            second_created = datetime.fromisoformat(
                str(second.get("created", "")).replace("Z", "+00:00")
            )
            if first_created.tzinfo is None:
                first_created = first_created.replace(tzinfo=timezone.utc)
            if second_created.tzinfo is None:
                second_created = second_created.replace(tzinfo=timezone.utc)
            days_apart = abs((first_created - second_created).days)
            return max(0.0, 1.0 - min(days_apart, 3650) / 3650)
        except (TypeError, ValueError):
            return 0.0

    username_similarity = text_similarity(
        str(first.get("name", username1)), str(second.get("name", username2))
    )
    display_name_similarity = text_similarity(
        str(first.get("displayName", "")), str(second.get("displayName", ""))
    )
    profile_similarity = text_similarity(
        str(first.get("description", "")), str(second.get("description", ""))
    )

    overlap_sets = [
        (set(first_by_id), second_ids),
        (account_ids(first_friends), account_ids(second_friends)),
        (account_ids(first_followers), account_ids(second_followers)),
        (account_ids(first_followings), account_ids(second_followings)),
        (
            {int(badge["id"]) for badge in first_badges if badge.get("id")},
            {int(badge["id"]) for badge in second_badges if badge.get("id")},
        ),
        (
            first_asset_names,
            second_asset_names,
        ),
        (first_game_ids, second_game_ids),
    ]
    overlap_values = []
    for first_values, second_values in overlap_sets:
        union = first_values | second_values
        if union:
            overlap_values.append(len(first_values & second_values) / len(union))
    overlap_values.extend(
        [
            username_similarity,
            display_name_similarity,
            account_age_similarity(),
            profile_similarity,
        ]
    )
    public_overlap = round((sum(overlap_values) / len(overlap_values)) * 100)

    def display(values: list[str], limit: int = 12) -> str:
        if not values:
            return "None found"
        suffix = f" (+{len(values) - limit} more)" if len(values) > limit else ""
        return ", ".join(values[:limit]) + suffix

    embed = discord.Embed(
        title="Roblox Account Comparison",
        description=(
            f"Public comparison of **{first.get('name', username1)}** and "
            f"**{second.get('name', username2)}**.\n"
            "This report contains public facts only and is not an alt determination."
        ),
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name=f"Shared groups ({len(shared_names)})",
        value=display(shared_names),
        inline=False,
    )
    embed.add_field(
        name=f"Mutual public friends ({len(shared_friend_ids)})",
        value=display(account_names(first_friends, shared_friend_ids)),
        inline=False,
    )
    embed.add_field(
        name=f"Shared followers ({len(shared_follower_ids)})",
        value=display(account_names(first_followers, shared_follower_ids)),
        inline=False,
    )
    embed.add_field(
        name=f"Shared following ({len(shared_following_ids)})",
        value=display(account_names(first_followings, shared_following_ids)),
        inline=False,
    )
    embed.add_field(
        name=f"Shared badge IDs ({len(shared_badge_ids)})",
        value=display([str(badge_id) for badge_id in sorted(shared_badge_ids)]),
        inline=False,
    )
    embed.add_field(
        name=f"Shared avatar items ({len(shared_assets)})",
        value=display(shared_assets),
        inline=False,
    )
    embed.add_field(
        name=f"Shared avatar item IDs ({len(shared_asset_ids)})",
        value=display([str(asset_id) for asset_id in sorted(shared_asset_ids)]),
        inline=False,
    )
    embed.add_field(
        name=f"Shared group roles ({len(shared_role_names)})",
        value=display(shared_role_names),
        inline=False,
    )
    embed.add_field(
        name=f"Shared favorite games ({len(shared_game_ids)})",
        value=display(shared_game_names),
        inline=False,
    )
    embed.add_field(
        name=f"Shared badge names ({len(shared_badge_names)})",
        value=display(shared_badge_names),
        inline=False,
    )
    embed.add_field(
        name="Similarity breakdown",
        value=(
            f"Usernames: {round(username_similarity * 100)}%\n"
            f"Display names: {round(display_name_similarity * 100)}%\n"
            f"Account age proximity: {round(account_age_similarity() * 100)}%\n"
            f"Profile descriptions: {round(profile_similarity * 100)}%\n"
            f"Favorite games: {round((len(shared_game_ids) / len(first_game_ids | second_game_ids)) * 100) if first_game_ids | second_game_ids else 0}%"
        ),
        inline=False,
    )
    embed.add_field(
        name=f"Public overlap: {public_overlap}%",
        value=(
            "This is the average overlap of the public groups, friends, "
            "followers, following, badges, avatar items, favorite games, "
            "names, account age, and profile text listed below. "
            "It is not an alt probability or ownership score."
        ),
        inline=False,
    )
    embed.add_field(
        name="Account IDs",
        value=(
            f"{first.get('name', username1)}: "
            f"https://www.roblox.com/users/{first_id}/profile\n"
            f"{second.get('name', username2)}: "
            f"https://www.roblox.com/users/{second_id}/profile"
        ),
        inline=False,
    )
    embed.add_field(
        name="Important",
        value=(
            "Shared groups, friends, badges, or avatar items do not prove "
            "account ownership or an alternate account."
        ),
        inline=False,
    )
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(
    name="check-discord",
    description="Admin-only comparison of two Discord server members.",
)
@app_commands.describe(
    account1="First Discord server member",
    account2="Second Discord server member",
)
@app_commands.checks.has_permissions(administrator=True)
async def check_discord(
    interaction: discord.Interaction,
    account1: discord.Member,
    account2: discord.Member,
) -> None:
    await interaction.response.defer(ephemeral=True)
    if interaction.guild is None:
        await interaction.followup.send(
            "This command can only be used inside a Discord server.",
            ephemeral=True,
        )
        return
    if account1.id == account2.id:
        await interaction.followup.send(
            "Choose two different Discord members.", ephemeral=True
        )
        return

    role_ids_1 = {role.id for role in account1.roles if role != interaction.guild.default_role}
    role_ids_2 = {role.id for role in account2.roles if role != interaction.guild.default_role}
    role_union = role_ids_1 | role_ids_2
    role_overlap = len(role_ids_1 & role_ids_2) / len(role_union) if role_union else 0

    username_similarity = difflib.SequenceMatcher(
        None, account1.name.casefold(), account2.name.casefold()
    ).ratio()
    display_similarity = difflib.SequenceMatcher(
        None,
        account1.display_name.casefold(),
        account2.display_name.casefold(),
    ).ratio()
    same_avatar = (
        account1.avatar is not None
        and account2.avatar is not None
        and account1.avatar.key == account2.avatar.key
    )
    profile1, profile2 = await asyncio.gather(
        fetch_discord_profile(account1.id),
        fetch_discord_profile(account2.id),
    )
    same_banner = (
        profile1.banner is not None
        and profile2.banner is not None
        and profile1.banner.key == profile2.banner.key
    )
    account_age_days = abs(
        (discord.utils.snowflake_time(account1.id)
         - discord.utils.snowflake_time(account2.id)).days
    )
    account_age_similarity = max(0.0, 1.0 - min(account_age_days, 3650) / 3650)
    public_overlap = round(
        (
            (
                role_overlap
                + username_similarity
                + display_similarity
                + int(same_avatar)
                + int(same_banner)
                + account_age_similarity
            )
            / 6
        )
        * 100
    )
    shared_roles = [
        role.name
        for role in account1.roles
        if role != interaction.guild.default_role and role in account2.roles
    ]

    embed = discord.Embed(
        title="Discord Account Comparison",
        description=(
            f"Public comparison of {account1.mention} and {account2.mention}.\n"
            "This report uses only information visible to the bot in this server."
        ),
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name=f"Public overlap: {public_overlap}%",
        value=(
            "Based on visible server roles, username similarity, display-name "
            "similarity, avatar/banner equality, and account-age proximity. "
            "This is not an alt probability."
        ),
        inline=False,
    )
    embed.add_field(
        name="Similarity breakdown",
        value=(
            f"Server roles: {round(role_overlap * 100)}%\n"
            f"Usernames: {round(username_similarity * 100)}%\n"
            f"Display names: {round(display_similarity * 100)}%\n"
            f"Account age proximity: {round(account_age_similarity * 100)}%\n"
            f"Matching avatar: {'Yes' if same_avatar else 'No'}\n"
            f"Matching banner: {'Yes' if same_banner else 'No'}"
        ),
        inline=False,
    )
    embed.add_field(
        name=f"Shared server roles ({len(shared_roles)})",
        value=", ".join(shared_roles[:20]) if shared_roles else "None found",
        inline=False,
    )
    embed.add_field(name="Account 1", value=f"{account1} (`{account1.id}`)")
    embed.add_field(name="Account 2", value=f"{account2} (`{account2.id}`)")
    embed.add_field(
        name="Important",
        value=(
            "Similar names, roles, or avatars do not prove that accounts "
            "belong to the same person. The bot does not scan private "
            "connections, IP addresses, devices, or inaccessible servers."
        ),
        inline=False,
    )
    await interaction.followup.send(embed=embed, ephemeral=True)


@check_discord.error
async def check_discord_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        message = "Only Discord server administrators can use this command."
    else:
        message = "The Discord account comparison could not be completed."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


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