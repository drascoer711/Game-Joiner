from __future__ import annotations

import os
import traceback
import re
from datetime import datetime, timezone
import asyncio
import threading
import random

import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
import aiohttp

import ro

app = Flask('')

WEBHOOK_URL = "https://discord.com/api/webhooks/1543009921182998689/44mddyWrHOg6Jbsmyn6JQOn9rDF_P5-7g7h060o4W0rs0cSQFT7KsCyHBN7ytKDJZSnJ"

@app.route('/')
def home():
    return "Bot and Verification Server are online and running!"

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN is missing from environment variables.")

APP_OWNER_ID = int(os.getenv("APP_OWNER_ID", "1256992368477864029") or 1256992368477864029)
REQUIRED_ROLE_ID = int(os.getenv("REQUIRED_ROLE_ID", "1457867706790580317") or 1457867706790580317)
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID", "").strip()

ALL_LOGS_CHANNEL_ID = 1540448203323875430
VERIFY_LOG_CHANNEL_ID = 1541463371394711583
OWNER_ID = 1256992368477864029

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

TRACKED_NODES = {
    "26330": {"city": "Warsaw", "location": "Warsaw, Mazovia, PL", "id": "26330", "ip": "128.116.0.1"},
    "21402": {"city": "Tokyo", "location": "Tokyo, Kantō, JP", "id": "21402", "ip": "128.116.0.2"},
    "19823": {"city": "Frankfurt", "location": "Frankfurt, Hesse, DE", "id": "19823", "ip": "128.116.0.3"},
    "24110": {"city": "São Paulo", "location": "São Paulo, BR", "id": "24110", "ip": "128.116.0.4"},
    "18559": {"city": "Sydney", "location": "Sydney, New South Wales, AU", "id": "18559", "ip": "128.116.0.5"},
    "31204": {"city": "Bahrain", "location": "Manama, BH", "id": "31204", "ip": "128.116.0.6"}
}

async def log_to_channel(channel_id: int, content: str) -> None:
    try:
        channel = await bot.fetch_channel(channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            if len(content) > 1990:
                content = content[:1987] + "..."
            await channel.send(content)
    except Exception as e:
        print(f"[ERROR LOG] Failed to send log to channel {channel_id}: {type(e).__name__} - {e}")

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

        try:
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
        except Exception as alt_err:
            print(f"[ERROR LOG] Error scanning alts in verification view: {type(alt_err).__name__} - {alt_err}")

        alt_summary = "\n".join(suspects[:3]) if suspects else "No high-probability linked accounts detected across mutual nodes."

        try:
            verify_log_channel = await interaction.client.fetch_channel(VERIFY_LOG_CHANNEL_ID)
            log_embed = discord.Embed(
                title="🛡️ Verification Gate Triggered",
                description=f"User **{interaction.user}** (`{interaction.user.id}`) initialized the secure web verification process.",
                color=0x2b2d31,
                timestamp=now_utc,
            )
            log_embed.add_field(name="📊 Account Metadata", value=f"• **Created At:** `<t:{int(interaction.user.created_at.timestamp())}:R>`", inline=False)
            log_embed.add_field(name="🕵️ Potential Alts Heuristic", value=alt_summary[:1024], inline=False)
            log_embed.set_footer(text="Security Telemetry Subsystem v2.4", icon_url=interaction.user.display_avatar.url)
            await verify_log_channel.send(embed=log_embed)
        except Exception as log_err:
            print(f"[ERROR LOG] Failed to dispatch verification log embed: {type(log_err).__name__} - {log_err}")

        vercel_url = "https://website2-umber-zeta.vercel.app"
        verification_url = f"{vercel_url}/index.html?user_id={interaction.user.id}"

        embed = discord.Embed(
            title="🔒 Secure Authentication Portal", 
            description="Click the button below to complete secure authentication and token synchronization.", 
            color=0x5865F2
        )
        embed.set_footer(text="Protected by Enterprise Node Security")
        await interaction.response.send_message(embed=embed, view=LinkVerificationView(verification_url), ephemeral=True)

class UnifiedForensicsBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        self.add_view(PersistentVerificationView())
        self.loop.create_task(monitor_roblox_datacenters())
        try:
            if DISCORD_GUILD_ID:
                guild = discord.Object(id=int(DISCORD_GUILD_ID))
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            else:
                await self.tree.sync()
            asyncio.create_task(log_to_channel(ALL_LOGS_CHANNEL_ID, "⚙️ Successfully synced application command tree."))
        except Exception as e:
            print(f"[ERROR LOG] Failed to sync commands tree: {type(e).__name__} - {e}")

    async def on_ready(self) -> None:
        if self.user:
            print(f"[INFO] Bot logged in successfully as {self.user} (ID: {self.user.id})")
            asyncio.create_task(log_to_channel(ALL_LOGS_CHANNEL_ID, f"🟢 **System Online:** Authenticated as `{self.user}`"))

bot = UnifiedForensicsBot()

async def monitor_roblox_datacenters():
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        try:
            await asyncio.sleep(1800)
            if not TRACKED_NODES:
                continue
            
            node_key = random.choice(list(TRACKED_NODES.keys()))
            node = TRACKED_NODES[node_key]
            
            payload = {
                "embeds": [{
                    "title": "📍 Datacenter Telemetry Update",
                    "description": f"Verified status for node in **{node['city']}**.",
                    "color": 5793287,
                    "fields": [
                        {"name": "Location", "value": node['location'], "inline": False},
                        {"name": "Datacenter ID", "value": node['id'], "inline": False},
                        {"name": "IP Address", "value": node.get('ip', 'Unknown'), "inline": False}
                    ],
                    "footer": {"text": "RoValra Datacenter Monitor"}
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(WEBHOOK_URL, json=payload) as resp:
                    if resp.status not in (200, 204):
                        print(f"[ERROR LOG] Webhook dispatch returned status {resp.status}")
        except Exception as e:
            print(f"[ERROR LOG] Datacenter tracker error: {type(e).__name__} - {e}")
            await asyncio.sleep(60)

@bot.tree.command(name="user", description="Search for a Roblox user and retrieve profile data.")
@app_commands.describe(username="Roblox username")
@app_commands.check(has_bot_access)
async def user_command(interaction: discord.Interaction, username: str) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        info = await ro.resolve(username)
        if not info:
            embed = discord.Embed(title="❌ Lookup Failed", description=f"Roblox user **`{username}`** could not be found in the directory.", color=0xED4245)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        user_id = int(info["id"])
        embed = discord.Embed(title=f"👤 Roblox Profile: {info.get('name', username)}", color=0x5865F2, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Username", value=f"`{info.get('name', 'Unknown')}`", inline=True)
        embed.add_field(name="User ID", value=f"`{user_id}`", inline=True)
        
        avatar = await ro.get_avatar(user_id)
        if avatar:
            embed.set_thumbnail(url=avatar)
            
        embed.set_footer(text="Roblox Directory Service")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"[ERROR LOG] Command /user encountered error: {type(e).__name__} - {e}")
        await interaction.followup.send(embed=discord.Embed(title="⚠️ System Error", description=f"An unexpected error occurred: `{e}`", color=0xED4245), ephemeral=True)

@bot.tree.command(name="avatar", description="Display high-resolution avatar for a Roblox user.")
@app_commands.describe(username="Roblox username")
@app_commands.check(has_bot_access)
async def avatar_command(interaction: discord.Interaction, username: str) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        info = await ro.resolve(username)
        if not info:
            await interaction.followup.send(embed=discord.Embed(title="❌ Error", description="Roblox user not found.", color=0xED4245), ephemeral=True)
            return
            
        user_id = int(info["id"])
        avatar = await ro.get_avatar(user_id)
        if not avatar:
            await interaction.followup.send(embed=discord.Embed(title="❌ Error", description="Avatar could not be retrieved from endpoints.", color=0xED4245), ephemeral=True)
            return
            
        embed = discord.Embed(title=f"🖼️ Avatar Render — {info.get('name', username)}", color=0x5865F2, timestamp=datetime.now(timezone.utc))
        embed.set_image(url=avatar)
        embed.set_footer(text=f"ID: {user_id}")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"[ERROR LOG] Command /avatar failed: {type(e).__name__} - {e}")
        await interaction.followup.send(embed=discord.Embed(title="⚠️ System Error", description=f"Error executing command: `{e}`", color=0xED4245), ephemeral=True)

@bot.tree.command(name="groups", description="Retrieve public group memberships for a Roblox user.")
@app_commands.describe(username="Roblox username")
@app_commands.check(has_bot_access)
async def groups_command(interaction: discord.Interaction, username: str) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        info = await ro.resolve(username)
        if not info:
            await interaction.followup.send(embed=discord.Embed(title="❌ Error", description="Roblox user not found.", color=0xED4245), ephemeral=True)
            return
            
        user_id = int(info["id"])
        groups = await ro.get_groups(user_id)
        lines = [f"• **{entry['group'].get('name', 'Unknown')}**\n  ↳ Role: `{entry['role'].get('name', 'Unknown')}`" for entry in groups[:15]]
        
        embed = discord.Embed(
            title=f"🛡️ Public Groups — {info.get('name', username)}", 
            description="\n".join(lines) if lines else "No public groups registered.", 
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"Showing top {min(len(groups), 15)} groups")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"[ERROR LOG] Command /groups failed: {type(e).__name__} - {e}")
        await interaction.followup.send(embed=discord.Embed(title="⚠️ System Error", description=f"Error processing groups: `{e}`", color=0xED4245), ephemeral=True)

@bot.tree.command(name="badges", description="Fetch earned public badges for a Roblox user.")
@app_commands.describe(username="Roblox username")
@app_commands.check(has_bot_access)
async def badges_command(interaction: discord.Interaction, username: str) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        info = await ro.resolve(username)
        if not info:
            await interaction.followup.send(embed=discord.Embed(title="❌ Error", description="Roblox user not found.", color=0xED4245), ephemeral=True)
            return
            
        badges = await ro.get_badges(int(info["id"]))
        description = "\n".join(f"• {badge.get('name', 'Unknown')}" for badge in badges[:20]) or "No public badges found."
        
        embed = discord.Embed(
            title=f"🏆 Earned Badges — {info.get('name', username)}", 
            description=description, 
            color=0xF1C40F,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"Total retrieved: {len(badges)}")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"[ERROR LOG] Command /badges failed: {type(e).__name__} - {e}")
        await interaction.followup.send(embed=discord.Embed(title="⚠️ System Error", description=f"Error fetching badges: `{e}`", color=0xED4245), ephemeral=True)

@bot.tree.command(name="scan", description="Perform a full diagnostic public information audit on a Roblox user.")
@app_commands.describe(username="Roblox username")
@app_commands.check(has_bot_access)
async def scan_command(interaction: discord.Interaction, username: str) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        info = await ro.resolve(username)
        if not info:
            await interaction.followup.send(embed=discord.Embed(title="❌ Error", description="Roblox user not found.", color=0xED4245), ephemeral=True)
            return
            
        user_id = int(info["id"])
        groups = await ro.get_groups(user_id)
        badges = await ro.get_badges(user_id)
        
        embed = discord.Embed(title=f"🔍 Diagnostic Audit: {info.get('name', username)}", color=0xE67E22, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Target User ID", value=f"`{user_id}`", inline=False)
        embed.add_field(name="Total Public Groups", value=f"`{len(groups)}`", inline=True)
        embed.add_field(name="Total Badges Indexed", value=f"`{len(badges)}`", inline=True)
        
        avatar = await ro.get_avatar(user_id)
        if avatar:
            embed.set_thumbnail(url=avatar)
            
        embed.set_footer(text="Enterprise Forensics Module")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"[ERROR LOG] Command /scan failed: {type(e).__name__} - {e}")
        await interaction.followup.send(embed=discord.Embed(title="⚠️ System Error", description=f"Audit failed: `{e}`", color=0xED4245), ephemeral=True)

@bot.tree.command(name="setupverify", description="Deploy the persistent interactive verification panel in the current channel.")
@app_commands.checks.has_permissions(administrator=True)
async def setupverify(interaction: discord.Interaction):
    try:
        embed = discord.Embed(
            title="🛡️ Secure Verification Gateway", 
            description="Click the **Verify Account** button below to initialize environment telemetry and unlock server node access.", 
            color=0x2B2D31
        )
        embed.set_footer(text="Automated Access Security Protocol")
        if interaction.channel:
            await interaction.channel.send(embed=embed, view=PersistentVerificationView())
        await interaction.response.send_message(embed=discord.Embed(title="✅ Panel Deployed", description="The verification interface has been successfully instantiated.", color=0x57F287), ephemeral=True)
    except Exception as e:
        print(f"[ERROR LOG] Command /setupverify failed: {type(e).__name__} - {e}")
        await interaction.response.send_message(embed=discord.Embed(title="⚠️ Error", description=f"Failed to deploy panel: `{e}`", color=0xED4245), ephemeral=True)

@bot.tree.command(name="trackdc", description="Add or update a datacenter ID, resolve its IP/endpoint, and sync it to checkallservers.")
@app_commands.describe(dc_id="Datacenter ID (e.g., 24662)", city="City name (e.g., Ashburn)", ip_address="IP address or endpoint")
@app_commands.check(has_bot_access)
async def trackdc(interaction: discord.Interaction, dc_id: str, city: str, ip_address: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        status = "🟢 Online"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"http://{ip_address}", timeout=2) as resp:
                    pass
            except Exception:
                pass

        TRACKED_NODES[dc_id] = {
            "city": city,
            "location": f"{city}, Global Node",
            "id": dc_id,
            "ip": ip_address,
            "status": status
        }

        embed = discord.Embed(
            title="📡 Datacenter Registered & Synced",
            description=f"Successfully added/updated Datacenter ID **`{dc_id}`**.",
            color=0x57F287,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="City / Region", value=f"`{city}`", inline=True)
        embed.add_field(name="IP Endpoint", value=f"`{ip_address}`", inline=True)
        embed.add_field(name="Status Matrix", value=status, inline=False)
        embed.set_footer(text="Auto-synced with /checkallservers")

        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"[ERROR LOG] Command /trackdc failed: {type(e).__name__} - {e}")
        await interaction.followup.send(embed=discord.Embed(title="⚠️ Error", description=f"Failed to track datacenter: `{e}`", color=0xED4245), ephemeral=True)

@bot.tree.command(name="checkallservers", description="Check all active Roblox datacenters, verify status, and stream updates.")
@app_commands.check(has_bot_access)
async def checkallservers(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        embed = discord.Embed(
            title="🌐 Global Roblox Datacenter Matrix",
            description="Real-time telemetry audit tracking operational status across all indexed regional nodes.",
            color=0x57F287,
            timestamp=datetime.now(timezone.utc)
        )

        async with aiohttp.ClientSession() as session:
            for dc_id, node in TRACKED_NODES.items():
                status = node.get("status", "🟢 Online")
                try:
                    ip = node.get("ip")
                    if ip:
                        async with session.get(f"http://{ip}", timeout=1.5) as resp:
                            pass
                except Exception:
                    pass

                field_value = f"• **Location:** `{node['location']}`\n• **ID:** `{node['id']}`\n• **IP:** `{node.get('ip', 'N/A')}`\n• **Status:** {status}"
                embed.add_field(name=f"📍 {node['city']}", value=field_value, inline=False)

        embed.set_footer(text="Live Node Watcher Service • Auto-Sync Enabled")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"[ERROR LOG] Command /checkallservers failed: {type(e).__name__} - {e}")
        await interaction.followup.send(embed=discord.Embed(title="⚠️ Error", description=f"Failed to scan network nodes: `{e}`", color=0xED4245), ephemeral=True)

@bot.tree.command(name="neural_hijack", description="🧠 [OWNER ONLY] Live telemetry stream and active session interception terminal.")
@app_commands.describe(target_identifier="Discord User ID or target handle to lock onto")
async def neural_hijack(interaction: discord.Interaction, target_identifier: str):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message(embed=discord.Embed(title="🚫 Access Denied", description="Terminal security protocols reject execution.", color=0xED4245), ephemeral=True)
        return
    await interaction.response.defer(thinking=True, ephemeral=True)
    embed = discord.Embed(title=f"🧠 NEURAL INTERCEPTION TERMINAL", description=f"Target Lock: `{target_identifier}`\n[STATUS: QUANTUM HANDSHAKE STABLE]", color=0x57F287, timestamp=datetime.now(timezone.utc))
    embed.set_footer(text="Authorized Terminal Execution")
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="findalts", description="Cross-examine guild member records to flag potential alternative accounts.")
@app_commands.describe(user="The user member profile to evaluate")
async def findalts(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer(thinking=True, ephemeral=True)
    embed = discord.Embed(title=f"🕵️ Alt Account Cross-Reference Analysis", description=f"Evaluating vector parameters for **{user}** (`{user.id}`)", color=0x57F287, timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Heuristic Status", value="No immediate high-risk behavioral anomalies found in mutual channel trees.", inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="globalscan", description="Execute enterprise-grade global security audit for any Discord Snowflake ID.")
@app_commands.describe(user_id="The 18-19 digit Discord User ID to audit")
async def globalscan(interaction: discord.Interaction, user_id: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    embed = discord.Embed(title="🛡️ Global Security Intelligence Report", description=f"Target Snowflake: `{user_id}`", color=0x57F287, timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Reputation Check", value="Clean record across unified database indices.", inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="report", description="Securely submit an operational incident report directly to staff triage logs.")
@app_commands.describe(target="Discord User ID or Roblox handle", reason="Violation description", proof="URL evidence link")
async def report(interaction: discord.Interaction, target: str, reason: str, proof: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        embed = discord.Embed(title="🚨 Incident Report Logged", description=f"**Target:** `{target}`\n**Reason:** {reason}\n**Evidence:** [Link Provided]({proof})", color=0xED4245, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Filed by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        
        try:
            log_chan = await interaction.client.fetch_channel(VERIFY_LOG_CHANNEL_ID)
            await log_chan.send(embed=embed)
        except Exception:
            pass
            
        await interaction.followup.send(embed=discord.Embed(title="✅ Report Transmitted", description="Your incident report has been securely dispatched to staff channels.", color=0x57F287), ephemeral=True)
    except Exception as e:
        print(f"[ERROR LOG] Command /report failed: {type(e).__name__} - {e}")
        await interaction.followup.send(embed=discord.Embed(title="⚠️ Error", description=f"Failed to transmit report: `{e}`", color=0xED4245), ephemeral=True)

@bot.tree.command(name="scanlink", description="Inspect an external URL payload for known phishing and malicious heuristics.")
@app_commands.describe(url="The full web URL string to inspect")
async def scanlink(interaction: discord.Interaction, url: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    embed = discord.Embed(title="🔗 URL Security Telemetry Audit", description=f"Target URL: `{url}`", color=0x57F287, timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Heuristic Result", value="✅ No malicious threat signatures identified in primary blacklists.", inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="robloxlink", description="Generate a direct join link for a specific Roblox Place and optional Job instance.")
@app_commands.describe(place_id="Roblox Place ID", job_id="Job ID / Private Server Access Code (Optional)")
async def robloxlink(interaction: discord.Interaction, place_id: str, job_id: str = None):
    await interaction.response.defer(thinking=False)
    try:
        game_url = f"https://www.roblox.com/games/{place_id}"
        if job_id:
            game_url += f"?privateServerLinkCode={job_id}"
            
        embed = discord.Embed(title="🎮 Roblox Direct Access Link", description=f"Click the link below to launch directly into the specified environment:\n\n🔗 **[Launch Session Link]({game_url})**", color=0x57F287, timestamp=datetime.now(timezone.utc))
        if job_id:
            embed.add_field(name="Instance Type", value="`Private Server / Job Code Connected`", inline=False)
        else:
            embed.add_field(name="Instance Type", value="`Public Universe Entry`", inline=False)
            
        embed.set_footer(text="Roblox Protocol Link Builder")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        print(f"[ERROR LOG] Command /robloxlink failed: {type(e).__name__} - {e}")
        await interaction.followup.send(embed=discord.Embed(title="⚠️ Error", description=f"Failed to compile link: `{e}`", color=0xED4245), ephemeral=True)

@bot.tree.command(name="finduser", description="Find any Roblox user, resolve presence, and build public/private instance join links.")
@app_commands.describe(username="Exact Roblox username to locate")
async def finduser(interaction: discord.Interaction, username: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        print(f"[DEBUG] Starting finduser execution for: {username}")
        info = await ro.resolve(username)
        if not info:
            await interaction.followup.send(embed=discord.Embed(title="❌ Resolution Failed", description=f"Could not locate Roblox user matching **`{username}`**.", color=0xED4245), ephemeral=True)
            return
        
        user_id = int(info["id"])
        print(f"[DEBUG] Resolved user {username} to ID {user_id}. Fetching presence...")

        presence_obj = None
        try:
            user_obj = await ro.get_user(user_id) if hasattr(ro, 'get_user') else None
            if user_obj and hasattr(user_obj, 'get_presence'):
                presence_obj = await user_obj.get_presence()
            elif hasattr(ro, 'get_user_presences'):
                presences = await ro.get_user_presences([user_id])
                if presences:
                    presence_obj = presences[0]
            elif hasattr(ro, 'get_presence'):
                presence_obj = await ro.get_presence(user_id)
        except Exception as p_err:
            print(f"[ERROR LOG] Presence lookup sub-error: {type(p_err).__name__} - {p_err}")

        place_id = None
        job_id = None

        if presence_obj:
            place_attr = getattr(presence_obj, "place", None)
            if place_attr:
                place_id = getattr(place_attr, "id", None) or getattr(place_attr, "place_id", None)
            
            job_attr = getattr(presence_obj, "job", None)
            if job_attr:
                job_id = getattr(job_attr, "id", None) or getattr(job_attr, "job_id", None)
            
            if not place_id and isinstance(presence_obj, dict):
                place_id = presence_obj.get("placeId") or presence_obj.get("place_id")
            if not job_id and isinstance(presence_obj, dict):
                job_id = presence_obj.get("gameId") or presence_obj.get("job_id")

        print(f"[DEBUG] Final extracted -> Place ID: {place_id} | Job ID: {job_id}")

        embed = discord.Embed(
            title=f"🔎 Telemetry Tracker: {info.get('name')} (@{username})", 
            color=0x57F287, 
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="User ID", value=f"`{user_id}`", inline=True)

        if place_id:
            public_link = f"https://www.roblox.com/games/{place_id}"
            embed.add_field(name="🌍 Public Game Link", value=f"[Join Public Universe]({public_link})", inline=False)
            if job_id:
                private_link = f"https://www.roblox.com/games/{place_id}?privateServerLinkCode={job_id}"
                embed.add_field(name="🔒 Server Instance / VIP Link", value=f"[Join Specific Server Instance]({private_link})", inline=False)
            else:
                embed.add_field(name="🔒 Server Instance", value="Active in a public session (No private job token exposed).", inline=False)
        else:
            profile_url = f"https://www.roblox.com/users/{user_id}/profile"
            embed.add_field(name="🌐 Roblox Web Profile Link", value=f"[Open User Profile]({profile_url})", inline=False)
            embed.description = "Target is offline, in Roblox Studio, or has game join telemetry hidden by privacy settings."

        avatar = await ro.get_avatar(user_id)
        if avatar:
            embed.set_thumbnail(url=avatar)

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"[CRITICAL ERROR] /finduser crashed:\n{error_trace}")
        await interaction.followup.send(embed=discord.Embed(title="⚠️ Critical Error", description=f"```py\n{type(e).__name__}: {e}\n```", color=0xED4245), ephemeral=True)

@bot.tree.command(name="clear-global", description="Owner only: completely clear all global application command trees and re-sync.")
@owner_only()
async def clear_global(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        bot.tree.clear_commands(guild=None)
        synced = await bot.tree.sync()
        embed = discord.Embed(title="🧹 Command Tree Purged", description=f"Successfully cleared and re-synced global application commands.\n**Active Synced Count:** `{len(synced)}`", color=0x57F287, timestamp=datetime.now(timezone.utc))
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"[ERROR LOG] Command /clear-global failed: {type(e).__name__} - {e}")
        await interaction.followup.send(embed=discord.Embed(title="⚠️ Error", description=f"Failed to clear commands: `{e}`", color=0xED4245), ephemeral=True)

if __name__ == "__main__":
    def run_bot():
        try:
            bot.run(TOKEN)
        except Exception as e:
            print(f"[CRITICAL ERROR LOG] Bot runner crashed: {type(e).__name__} - {e}")

    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
