from __future__ import annotations

import os
import traceback
import math
import re
from datetime import datetime, timezone
from typing import Any, Optional
import asyncio

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask, request, jsonify, render_template_string
from roblox import Client as RobloxClient

# ==========================================
# CONFIGURATION & FLASK WEB SERVER (RENDER)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot and Verification Server are online and running!"

VERIFY_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Secure Verification Portal</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #121214; color: #e1e1e6; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: #202024; padding: 40px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); text-align: center; max-width: 400px; width: 100%; border: 1px solid #323238; }
        h2 { color: #00b37e; margin-bottom: 10px; }
        p { color: #9999a1; font-size: 14px; line-height: 1.5; margin-bottom: 24px; }
        .btn { background: #00b37e; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-weight: bold; cursor: pointer; width: 100%; font-size: 16px; transition: background 0.2s; }
        .btn:hover { background: #00875f; }
        .status { margin-top: 15px; font-size: 12px; color: #7c7c8a; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🛡️ Secure Verification</h2>
        <p>Complete authentication to sync your security tokens and verify your node access within the community database.</p>
        <button class="btn" onclick="verifySession()">Authorize & Verify</button>
        <div class="status" id="statusText">Awaiting user authorization...</div>
    </div>
    <script>
        async function verifySession() {
            const urlParams = new URLSearchParams(window.location.search);
            const userId = urlParams.get('user_id');
            const statusEl = document.getElementById('statusText');
            
            statusEl.innerText = "Transmitting session telemetry...";
            
            try {
                const response = await fetch('/api/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId })
                });
                const data = await response.json();
                if (response.ok) {
                    statusEl.innerText = "✅ Verification successful! You can now close this tab.";
                    document.querySelector('.btn').style.display = 'none';
                } else {
                    statusEl.innerText = "❌ Error: " + (data.error || "Unknown error occurred.");
                }
            } catch (e) {
                statusEl.innerText = "❌ Network transport failed.";
            }
        }
    </script>
</body>
</html>
"""

@app.route('/index.html')
def verify_page():
    return render_template_string(VERIFY_TEMPLATE)

@app.route('/api/verify', methods=['POST'])
def api_verify():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', 'Unknown')
    country = request.headers.get('CF-IPCountry', request.headers.get('X-Render-IP-Country', 'Unknown'))
    
    if not user_id:
        return jsonify({"error": "Missing user identifier"}), 400

    future = asyncio.run_coroutine_threadsafe(
        log_verification_event(user_id, ip_address, user_agent, country), 
        bot.loop
    )
    try:
        future.result(timeout=5)
    except Exception:
        pass

    return jsonify({"status": "success", "message": "Telemetry logged and verified."})

async def log_verification_event(user_id: str, ip_address: str, user_agent: str, country: str):
    try:
        user = bot.get_user(int(user_id)) or await bot.fetch_user(int(user_id))
        verify_channel = bot.get_channel(VERIFY_LOG_CHANNEL_ID) or await bot.fetch_channel(VERIFY_LOG_CHANNEL_ID)
        
        if verify_channel and isinstance(verify_channel, discord.TextChannel):
            embed = discord.Embed(
                title="✅ Web Verification Completed",
                description=f"User **{user}** (`{user_id}`) successfully authenticated via the web browser portal.",
                color=0x57F287,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(
                name="🌐 Captured Telemetry & Network Route",
                value=(
                    f"• **IP Address:** `{ip_address}`\n"
                    f"• **Country Origin:** `{country}`\n"
                    f"• **Browser User-Agent:** `{user_agent[:150]}`"
                ),
                inline=False
            )
            await verify_channel.send(embed=embed)
    except Exception as e:
        print(f"Failed to process webhook verification log: {e}")

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ROBLOX_COOKIE = os.getenv("ROBLOX_COOKIE")

if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN is missing from environment variables.")

APP_OWNER_ID = int(os.getenv("APP_OWNER_ID", "1256992368477864029") or 1256992368477864029)
REQUIRED_ROLE_ID = int(os.getenv("REQUIRED_ROLE_ID", "1457867706790580317") or 1457867706790580317)
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID", "").strip()

# Logging Channel IDs
ALL_LOGS_CHANNEL_ID = 1540448203323875430
FAILED_LOGS_CHANNEL_ID = 1540449747179937913
LOG_CHANNEL_ID = 1540490675928174694
VERIFY_LOG_CHANNEL_ID = 1541463371394711583
OWNER_ID = 1256992368477864029

# Roblox Public APIs
USERS_API = "https://users.roblox.com/v1"
GROUPS_API = "https://groups.roblox.com/v2"
THUMBNAILS_API = "https://thumbnails.roblox.com/v1"
BADGES_API = "https://badges.roblox.com/v1"
FRIENDS_API = "https://friends.roblox.com/v1"
AVATAR_API = "https://avatar.roblox.com/v1"
GAMES_API = "https://games.roblox.com/v2"

roblox = RobloxClient(ROBLOX_COOKIE if ROBLOX_COOKIE else "")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


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

async def log_to_channel(channel_id: int, content: str) -> None:
    try:
        channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            if len(content) > 1990:
                content = content[:1987] + "..."
            await channel.send(content)
    except Exception as e:
        print(f"Failed to send log to channel {channel_id}: {e}")


class RequiredRoleError(app_commands.CheckFailure):
    pass

async def has_bot_access(interaction: discord.Interaction) -> bool:
    if APP_OWNER_ID and interaction.user.id == APP_OWNER_ID:
        return True
    roles = getattr(interaction.user, "roles", [])
    if REQUIRED_ROLE_ID and any(role.id == REQUIRED_ROLE_ID for role in roles):
        return True
    raise RequiredRoleError("You need the required bot access role to use this command.")

def owner_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if APP_OWNER_ID and interaction.user.id == APP_OWNER_ID:
            return True
        raise app_commands.CheckFailure("Only the configured app owner can use this command.")
    return app_commands.check(predicate)


class LinkVerificationView(discord.ui.View):
    def __init__(self, verification_url: str):
        super().__init__(timeout=60)
        self.add_item(discord.ui.Button(label="Open Web Verification", style=discord.ButtonStyle.link, url=verification_url))

class PersistentVerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify Account", style=discord.ButtonStyle.green, custom_id="persistent_verify:btn", emoji="✅")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        target = interaction.user
        target_created = target.created_at
        target_name_base = re.sub(r"\d+", "", target.name).lower()
        now_utc = datetime.now(timezone.utc)

        suspects = []
        checked_ids = set()

        for guild in interaction.client.guilds:
            if guild.get_member(target.id):
                for member in guild.members:
                    if member.id == target.id or member.id in checked_ids:
                        continue
                    checked_ids.add(member.id)

                    alt_score = 0
                    reasons = []
                    member_created = member.created_at
                    age_diff = abs((target_created - member_created).total_seconds())

                    if age_diff < 172800:
                        reasons.append("<48h window")
                        alt_score += 4

                    member_name_base = re.sub(r"\d+", "", member.name).lower()
                    if target_name_base and member_name_base and (target_name_base in member_name_base or member_name_base in target_name_base) and len(target_name_base) > 3:
                        reasons.append("Matching name pattern")
                        alt_score += 3

                    if (now_utc - member_created).days < 14:
                        reasons.append("New/Burner velocity")
                        alt_score += 2

                    if alt_score >= 4:
                        suspects.append(f"• **{member}** (`{member.id}`) [Score: `{alt_score}` | {', '.join(reasons)}]")

        alt_summary = "\n".join(suspects[:3]) if suspects else "No high-probability linked accounts detected across mutual nodes."

        verify_log_channel = interaction.client.get_channel(VERIFY_LOG_CHANNEL_ID)
        if verify_log_channel:
            log_embed = discord.Embed(
                title="🛡️ Verification Portal & Telemetry Triggered",
                description=f"User **{interaction.user}** (`{interaction.user.id}`) initialized the verification flow.",
                color=0x5865F2,
                timestamp=now_utc,
            )
            log_embed.add_field(name="📊 Account Metadata", value=f"• **Created At:** `{interaction.user.created_at.strftime('%Y-%m-%d %H:%M')}`", inline=False)
            log_embed.add_field(name="🕵️ Potential Alts", value=alt_summary[:1024], inline=False)
            try:
                await verify_log_channel.send(embed=log_embed)
            except Exception:
                pass

        # Dynamically reference Render app URL if available, fallback to localhost
        render_external_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:10000")
        verification_url = f"{render_external_url}/index.html?user_id={interaction.user.id}"

        embed = discord.Embed(title="🔒 Secure Verification Portal", description="Click the button below to complete authentication via the web portal.", color=0x5865F2)
        await interaction.response.send_message(embed=embed, view=LinkVerificationView(verification_url), ephemeral=True)


class RobloxCommandTree(app_commands.CommandTree):
    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        fail_msg = f"❌ **Command Failed**\n• **Command:** `/{interaction.command.name if interaction.command else 'unknown'}`\n```py\n{tb_str[:1500]}\n```"
        asyncio.create_task(log_to_channel(FAILED_LOGS_CHANNEL_ID, fail_msg))
        
        message = "The command could not complete. Please try again."
        if isinstance(error, RequiredRoleError):
            message = "You do not have permission to use this bot. You need the required role."
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception:
            pass


class UnifiedForensicsBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=intents)
        self.tree = RobloxCommandTree(self)

    async def setup_hook(self) -> None:
        self.add_view(PersistentVerificationView())
        try:
            if DISCORD_GUILD_ID:
                guild = discord.Object(id=int(DISCORD_GUILD_ID))
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            else:
                await self.tree.sync()
            asyncio.create_task(log_to_channel(ALL_LOGS_CHANNEL_ID, "⚙️ Successfully synced slash commands."))
        except Exception as e:
            print(f"Failed to sync commands: {e}")

    async def on_ready(self) -> None:
        if self.user:
            asyncio.create_task(log_to_channel(ALL_LOGS_CHANNEL_ID, f"🟢 Bot online as {self.user}"))


bot = UnifiedForensicsBot()


@bot.tree.command(name="user", description="Search for a Roblox user.")
@app_commands.describe(username="Roblox username")
@app_commands.check(has_bot_access)
async def user_command(interaction: discord.Interaction, username: str) -> None:
    await interaction.response.defer(ephemeral=True)
    info = await resolve(username)
    if not info:
        await interaction.followup.send(f"Roblox user `{username}` was not found.", ephemeral=True)
        return

    user_id = int(info["id"])
    embed = discord.Embed(title="Roblox User", color=discord.Color.blurple())
    embed.add_field(name="Username", value=f"`{info.get('name', 'Unknown')}`")
    embed.add_field(name="User ID", value=f"`{user_id}`")
    avatar = await get_avatar(user_id)
    if avatar:
        embed.set_thumbnail(url=avatar)
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="setupverify", description="Deploys the persistent verification panel in this channel.")
@app_commands.checks.has_permissions(administrator=True)
async def setupverify(interaction: discord.Interaction):
    embed = discord.Embed(title="🛡️ Server Verification Gate", description="Click **Verify Account** below to launch the secure portal.", color=0x2B2D31)
    await interaction.channel.send(embed=embed, view=PersistentVerificationView())
    await interaction.response.send_message("✅ Verification panel successfully deployed.", ephemeral=True)


# ==========================================
# RENDER STARTUP ROUTINE
# ==========================================
if __name__ == "__main__":
    # Start Discord bot as a background task runner while Flask runs on the main thread
    @bot.event
    async def on_connect():
        print("Discord bot connected successfully.")

    import threading
    def run_bot():
        bot.run(TOKEN)

    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # Render provides a dynamic PORT environment variable (defaults to 10000 if not found)
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
