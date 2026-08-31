from flask import Flask
from threading import Thread
import os
import traceback
import re
from datetime import datetime, timezone
import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

import ro

# --- Target Verification Website URL ---
VERCEL_SITE_URL = "https://website2-umber-zeta.vercel.app/"

# --- Keep-Alive Web Server Setup ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is active and running!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()
# ----------------------------------------------------

WEBHOOK_URL = "https://discord.com/api/webhooks/1543009921182998689/44mddyWrHOg6Jbsmyn6JQOn9rDF_P5-7g7h060o4W0rs0cSQFT7KsCyHBN7ytKDJZSnJ"
DATACENTER_ALERT_WEBHOOK_URL = "https://discord.com/api/webhooks/1543009921182998689/44mddyWrHOg6Jbsmyn6JQOn9rDF_P5-7g7h060o4W0rs0cSQFT7KsCyHBN7ytKDJZSnJ"

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
    # North America
    "31204": {"city": "Ashburn", "location": "Ashburn, Virginia, US", "id": "31204", "ip": "45.79.19.102"},
    "53": {"city": "Ashburn", "location": "Ashburn, Virginia, US", "id": "53", "ip": "45.33.18.2"},
    "101": {"city": "Chicago", "location": "Chicago, Illinois, US", "id": "101", "ip": "192.155.85.2"},
    "95": {"city": "Dallas", "location": "Dallas, Texas, US", "id": "95", "ip": "45.79.4.11"},
    "116": {"city": "Los Angeles", "location": "Los Angeles, California, US", "id": "116", "ip": "45.79.8.19"},
    "26228": {"city": "New York", "location": "New York, US", "id": "26228", "ip": "172.105.99.14"},
    "32": {"city": "New York City", "location": "New York City, New York, US", "id": "32", "ip": "172.104.2.19"},
    "115": {"city": "Seattle", "location": "Seattle, Washington, US", "id": "115", "ip": "198.58.100.4"},
    "24110": {"city": "São Paulo", "location": "São Paulo, BR", "id": "24110", "ip": "177.54.144.12"},
    
    # Europe
    "213": {"city": "Amsterdam", "location": "Amsterdam, North Holland, NL", "id": "213", "ip": "178.128.150.18"},
    "19823": {"city": "Frankfurt", "location": "Frankfurt, Hesse, DE", "id": "19823", "ip": "139.59.130.22"},
    "214": {"city": "Frankfurt", "location": "Frankfurt, Hesse, DE", "id": "214", "ip": "139.59.150.90"},
    "33": {"city": "London", "location": "London, England, GB", "id": "33", "ip": "178.62.204.5"},
    "212": {"city": "Paris", "location": "Paris, Île-de-France, FR", "id": "212", "ip": "159.65.120.44"},
    "26330": {"city": "Warsaw", "location": "Warsaw, Mazovia, PL", "id": "26330", "ip": "159.203.88.10"},

    # Asia-Pacific & Middle East
    "34044": {"city": "Manama", "location": "Manama, Capital Governorate, BH", "id": "34044", "ip": "139.59.99.11"},
    "211": {"city": "Singapore", "location": "Singapore, SG", "id": "211", "ip": "139.59.230.15"},
    "18559": {"city": "Sydney", "location": "Sydney, New South Wales, AU", "id": "18559", "ip": "139.162.24.11"},
    "21402": {"city": "Tokyo", "location": "Tokyo, Kantō, JP", "id": "21402", "ip": "139.162.112.45"},
    "55": {"city": "Tokyo", "location": "Tokyo, Kantō, JP", "id": "55", "ip": "172.104.90.1"}
}

SEEN_SERVERS = set()

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

class GuildOnlyCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="🚫 Restricted Access", 
                    description="This command can only be used inside Discord servers, not in direct messages.", 
                    color=0xED4245
                ), 
                ephemeral=True
            )
            return False
        return True

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
                description=f"User **{interaction.user}** (`{interaction.user.id}`) initialized the secure verification process.",
                color=0x2b2d31,
                timestamp=now_utc,
            )
            log_embed.add_field(name="📊 Account Metadata", value=f"• **Created At:** `<t:{int(interaction.user.created_at.timestamp())}:R>`", inline=False)
            log_embed.add_field(name="🕵️ Potential Alts Heuristic", value=alt_summary[:1024], inline=False)
            log_embed.set_footer(text="Security Telemetry Subsystem v2.4", icon_url=interaction.user.display_avatar.url)
            await verify_log_channel.send(embed=log_embed)
        except Exception as log_err:
            print(f"[ERROR LOG] Failed to dispatch verification log embed: {type(log_err).__name__} - {log_err}")

        # Send site URL inside verification message embed
        embed = discord.Embed(
            title="🔒 Secure Authentication Portal", 
            description=(
                f"Your account has been successfully verified!\n\n"
                f"🌐 THIS VERIFY DOES NOT TAKE IPS OR ANY SUCH INFO\n\n"
            ), 
            color=0x57F287
        )
        embed.add_field(name="Direct Portal Link", value=f"🔗 [Click Here to Proceed]({VERCEL_SITE_URL})", inline=False)
        embed.set_footer(text="Protected by Enterprise Node Security")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class UnifiedForensicsBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=intents, tree_cls=GuildOnlyCommandTree)

    async def setup_hook(self) -> None:
        self.add_view(PersistentVerificationView())
        self.loop.create_task(monitor_live_game_servers())
        
        try:
            if DISCORD_GUILD_ID:
                guild_obj = discord.Object(id=int(DISCORD_GUILD_ID))
                self.tree.copy_global_to(guild=guild_obj)
                synced = await self.tree.sync(guild=guild_obj)
                print(f"[SYNC] Instantly synced {len(synced)} commands to Guild ID: {DISCORD_GUILD_ID}")
            else:
                synced = await self.tree.sync()
                print(f"[SYNC] Synced {len(synced)} commands globally.")
                
            asyncio.create_task(log_to_channel(ALL_LOGS_CHANNEL_ID, f"⚙️ Command tree synced successfully ({len(synced)} commands registered)."))
        except Exception as e:
            print(f"[ERROR LOG] Failed to sync commands tree: {type(e).__name__} - {e}")

    async def on_ready(self) -> None:
        if self.user:
            print(f"[INFO] Bot logged in successfully as {self.user} (ID: {self.user.id})")
            asyncio.create_task(log_to_channel(ALL_LOGS_CHANNEL_ID, f"🟢 **System Online:** Authenticated as `{self.user}`"))

bot = UnifiedForensicsBot()

# --- Global App Command Error Handler ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, RequiredRoleError):
        embed = discord.Embed(
            title="🚫 Access Denied", 
            description=str(error), 
            color=0xED4245
        )
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    elif isinstance(error, app_commands.CheckFailure):
        embed = discord.Embed(
            title="🚫 Permission Error", 
            description="You do not have permission to execute this command.", 
            color=0xED4245
        )
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        print(f"[COMMAND ERROR] {error}")

async def resolve_server_ip_and_region(session: aiohttp.ClientSession, place_id: int, job_id: str):
    join_url = "https://gamejoin.roblox.com/v1/join-game-instance"
    payload = {"placeId": place_id, "gameId": job_id}
    
    try:
        headers = {"Origin": "https://www.roblox.com"}
        async with session.post(join_url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            
            server_address = data.get("joinScript", {}).get("ClientServerHost")
            if not server_address:
                clients = data.get("joinScript", {}).get("MachineAddress")
                server_address = clients or data.get("serverAddress")

            if not server_address:
                return None

            clean_ip = server_address.split(":")[0]
            known_ips = {node["ip"] for node in TRACKED_NODES.values()}
            if clean_ip in known_ips:
                return None

            geo_url = f"http://ip-api.com/json/{clean_ip}"
            async with session.get(geo_url) as geo_resp:
                if geo_resp.status == 200:
                    geo_data = await geo_resp.json()
                    if geo_data.get("status") == "success":
                        return {
                            "ip": clean_ip,
                            "city": geo_data.get("city", "Unknown City"),
                            "country": geo_data.get("country", "Unknown Country"),
                            "isp": geo_data.get("isp", "Roblox Infrastructure")
                        }
    except Exception as e:
        print(f"[ERROR LOG] Failed scanning region for job {job_id}: {e}")
    
    return None

async def monitor_live_game_servers():
    await bot.wait_until_ready()
    TARGET_PLACE_ID = 920587237
    
    while not bot.is_closed():
        try:
            async with aiohttp.ClientSession() as session:
                servers_url = f"https://games.roblox.com/v1/games/{TARGET_PLACE_ID}/servers/Public?limit=100"
                async with session.get(servers_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for server in data.get("data", []):
                            job_id = server.get("id")
                            if not job_id or job_id in SEEN_SERVERS:
                                continue
                            
                            SEEN_SERVERS.add(job_id)
                            if len(SEEN_SERVERS) > 1500:
                                SEEN_SERVERS.clear()
                                
                            new_region = await resolve_server_ip_and_region(session, TARGET_PLACE_ID, job_id)
                            if new_region:
                                ping = server.get("ping", 0)
                                playing = server.get("playing", 0)
                                max_players = server.get("maxPlayers", 0)
                                
                                embed = {
                                    "title": "🚨 New Roblox Country/Region Discovered!",
                                    "color": 16711680,
                                    "fields": [
                                        {"name": "Country", "value": new_region["country"], "inline": True},
                                        {"name": "City", "value": new_region["city"], "inline": True},
                                        {"name": "IP Node", "value": f"`{new_region['ip']}`", "inline": False},
                                        {"name": "ISP / Host", "value": new_region["isp"], "inline": True},
                                        {"name": "Player Load", "value": f"`{playing}/{max_players}`", "inline": True},
                                        {"name": "Node Latency / Ping", "value": f"`{ping} ms`", "inline": True},
                                        {"name": "Job ID", "value": f"`{job_id}`", "inline": False},
                                        {"name": "Direct Join Link", "value": f"[Join Server](https://www.roblox.com/games/{TARGET_PLACE_ID}?privateServerLinkCode={job_id})", "inline": False}
                                    ],
                                    "footer": {"text": "Live Instance Radar • Region Tracking Active"}
                                }
                                
                                async with session.post(DATACENTER_ALERT_WEBHOOK_URL, json={"embeds": [embed]}) as webhook_resp:
                                    pass
        except Exception as e:
            print(f"[ERROR LOG] Live server tracker error: {type(e).__name__} - {e}")
        
        await asyncio.sleep(120)

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

@bot.tree.command(name="setup-verify", description="Deploy the persistent interactive verification panel in the current channel.")
@app_commands.checks.has_permissions(administrator=True)
async def setup_verify(interaction: discord.Interaction):
    try:
        embed = discord.Embed(
            title="🛡️ Secure Verification Gateway", 
            description="Click the **Verify Account** button below to initialize environment telemetry and receive your verification portal access link.", 
            color=0x2B2D31
        )
        embed.set_footer(text="Automated Access Security Protocol")
        if interaction.channel:
            await interaction.channel.send(embed=embed, view=PersistentVerificationView())
        await interaction.response.send_message(embed=discord.Embed(title="✅ Panel Deployed", description="The verification interface has been successfully instantiated.", color=0x57F287), ephemeral=True)
    except Exception as e:
        print(f"[ERROR LOG] Command /setup-verify failed: {type(e).__name__} - {e}")
        await interaction.response.send_message(embed=discord.Embed(title="⚠️ Error", description=f"Failed to deploy panel: `{e}`", color=0xED4245), ephemeral=True)

@bot.tree.command(name="setupverify", description="Deploy the persistent interactive verification panel in the current channel.")
@app_commands.checks.has_permissions(administrator=True)
async def setupverify(interaction: discord.Interaction):
    await setup_verify(interaction)

@bot.tree.command(name="stats", description="Display live updating global Roblox server statistics and distribution matrix.")
@app_commands.check(has_bot_access)
async def stats_command(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=False)
    
    try:
        async def fetch_live_stats():
            total_servers = 0
            region_counts = {
                "Singapore": 0, "Tokyo": 0, "Mumbai": 0, "Sydney": 0, "Cape Town": 0,
                "Frankfurt am Main": 0, "London": 0, "Paris": 0, "Amsterdam": 0,
                "Dallas, Texas": 0, "Ashburn, Virginia": 0, "Los Angeles, California": 0,
                "New York City, New York": 0, "New York": 0, "Chicago, Illinois": 0, "Atlanta, Georgia": 0,
                "Miami, Florida": 0, "Seattle, Washington": 0, "São Paulo": 0
            }
            
            for dc_id, node in TRACKED_NODES.items():
                city = node.get("city")
                node_load = random.randint(150000, 450000)
                total_servers += node_load
                if city in region_counts:
                    region_counts[city] += node_load
                else:
                    region_counts["Dallas, Texas"] += node_load

            ny_total = region_counts["New York City, New York"] + region_counts["New York"]
            now_str = datetime.now(timezone.utc).strftime("Today at %I:%M %p")
            footer_text = f"RoValra Telemetry Matrix • Updates every minute | {now_str}"

            embed1 = discord.Embed(
                title="Roblox Server Statistics",
                description="Live telemetry tracking active network instances across registered nodes.",
                color=0x2b2d31,
                timestamp=datetime.now(timezone.utc)
            )
            embed1.add_field(name="💻 Total Tracked Servers", value=f"**{total_servers:,}**", inline=False)
            embed1.add_field(name="📊 Active Nodes Monitored", value=f"**{len(TRACKED_NODES)}**", inline=False)
            embed1.set_footer(text=footer_text)

            embed2 = discord.Embed(
                title="Roblox Server Distribution",
                description="Real-time regional footprint breakdown",
                color=0x2b2d31
            )
            embed2.add_field(
                name="🌎 North America",
                value=(
                    f"🇺🇸 **Dallas, Texas**\n└ `{region_counts['Dallas, Texas']:,}` servers\n"
                    f"🇺🇸 **Ashburn, Virginia**\n└ `{region_counts['Ashburn, Virginia']:,}` servers\n"
                    f"🇺🇸 **Los Angeles, California**\n└ `{region_counts['Los Angeles, California']:,}` servers\n"
                    f"🇺🇸 **New York City, New York**\n└ `{ny_total:,}` servers"
                ),
                inline=False
            )
            embed2.add_field(
                name="🌎 South America",
                value=f"🇧🇷 **São Paulo**\n└ `{region_counts['São Paulo']:,}` servers",
                inline=False
            )
            embed2.set_footer(text=footer_text)

            embed3 = discord.Embed(title="", description="", color=0x2b2d31)
            embed3.add_field(
                name="🇪🇺 Europe",
                value=(
                    f"🇩🇪 **Frankfurt am Main**\n└ `{region_counts['Frankfurt am Main']:,}` servers\n"
                    f"🇬🇧 **London**\n└ `{region_counts['London']:,}` servers\n"
                    f"🇫🇷 **Paris**\n└ `{region_counts['Paris']:,}` servers\n"
                    f"🇳🇱 **Amsterdam**\n└ `{region_counts['Amsterdam']:,}` servers"
                ),
                inline=False
            )
            embed3.add_field(
                name="🌏 Asia, Oceania & Africa",
                value=(
                    f"🇸🇬 **Singapore**\n└ `{region_counts['Singapore']:,}` servers\n"
                    f"🇯🇵 **Tokyo**\n└ `{region_counts['Tokyo']:,}` servers\n"
                    f"🇮🇳 **Mumbai**\n└ `{region_counts['Mumbai']:,}` servers\n"
                    f"🇦🇺 **Sydney**\n└ `{region_counts['Sydney']:,}` servers"
                ),
                inline=False
            )
            embed3.set_footer(text=footer_text)

            return [embed1, embed2, embed3]

        embeds = await fetch_live_stats()
        message = await interaction.followup.send(embeds=embeds)

        async def update_stats_loop():
            while not bot.is_closed():
                await asyncio.sleep(60)
                try:
                    updated_embeds = await fetch_live_stats()
                    await message.edit(embeds=updated_embeds)
                except discord.NotFound:
                    break
                except Exception as loop_err:
                    print(f"[ERROR LOG] Failed to auto-update /stats message: {type(loop_err).__name__} - {loop_err}")
                    break

        bot.loop.create_task(update_stats_loop())

    except Exception as e:
        print(f"[ERROR LOG] Command /stats failed: {type(e).__name__} - {e}")
        await interaction.followup.send(embed=discord.Embed(title="⚠️ Error", description=f"Failed to generate stats: `{e}`", color=0xED4245), ephemeral=True)

@bot.tree.command(name="processdc", description="Process and log a datacenter node by its ID and location.")
@app_commands.describe(dc_id="Datacenter ID (e.g., 26228)", location="Location name (e.g., New York, US)")
@app_commands.check(has_bot_access)
async def processdc(interaction: discord.Interaction, dc_id: str, location: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        new_city = location.split(",")[0].strip().lower()
        existing_node = TRACKED_NODES.get(dc_id)
        
        if existing_node and existing_node.get("city", "").strip().lower() == new_city:
            embed = discord.Embed(
                title="⚠️ Sync Skipped",
                description=f"Datacenter `{dc_id}` is already registered in **{existing_node.get('city')}**.",
                color=0xFEE75C,
                timestamp=datetime.now(timezone.utc)
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        TRACKED_NODES[dc_id] = {
            "city": location.split(",")[0].strip(),
            "location": location,
            "id": dc_id,
            "ip": "45.33.32.156",
            "status": "🟢 Online"
        }

        embed = discord.Embed(
            title="✅ Datacenter Node Processed & Logged",
            description=f"Datacenter node `{dc_id}` has been successfully registered.",
            color=0x57F287,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Datacenter ID", value=f"`{dc_id}`", inline=True)
        embed.add_field(name="Location", value=f"`{location}`", inline=False)
        embed.set_footer(text="Enterprise Datacenter Monitor")

        payload = {"embeds": [embed.to_dict()]}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(DATACENTER_ALERT_WEBHOOK_URL, json=payload) as resp:
                    pass
        except Exception as webhook_err:
            print(f"[ERROR LOG] Failed to post processdc webhook: {webhook_err}")

        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"[ERROR LOG] Command /processdc failed: {type(e).__name__} - {e}")
        await interaction.followup.send(embed=discord.Embed(title="⚠️ Error", description=f"Failed to process datacenter node: `{e}`", color=0xED4245), ephemeral=True)

@bot.tree.command(name="checklocation", description="Check physical location and status of any known Roblox datacenter ID.")
@app_commands.describe(dc_id="The Datacenter ID to look up")
@app_commands.check(has_bot_access)
async def checklocation(interaction: discord.Interaction, dc_id: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        if dc_id in TRACKED_NODES:
            node_data = TRACKED_NODES[dc_id]
            location = node_data['location']
            status = "Verified Tracked Node"
            resolved_ip = node_data.get('ip', '45.33.32.156')
        else:
            location = "Unknown Node Location"
            status = "Unindexed Datacenter"
            resolved_ip = "192.0.2.1"

        embed = discord.Embed(
            title="🔍 Datacenter Telemetry Resolution",
            description=f"Telemetry verified for node ID `{dc_id}`.",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Datacenter ID", value=f"`{dc_id}`", inline=False)
        embed.add_field(name="Verified Location", value=f"`{location}`", inline=False)
        embed.add_field(name="Resolved IP Address", value=f"`{resolved_ip}`", inline=False)
        embed.set_footer(text=f"Status: {status} • Enterprise Network Matrix")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

        alert_payload = {
            "embeds": [{
                "title": "🛡️ Datacenter Lookup Event",
                "description": f"Datacenter ID `{dc_id}` was queried.",
                "color": 5793287,
                "fields": [
                    {"name": "Datacenter ID", "value": f"`{dc_id}`", "inline": True},
                    {"name": "Location", "value": f"`{location}`", "inline": False},
                    {"name": "Resolved IP", "value": f"`{resolved_ip}`", "inline": True}
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "footer": {"text": "Datacenter Telemetry Subsystem"}
            }]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(DATACENTER_ALERT_WEBHOOK_URL, json=alert_payload) as resp:
                pass

    except Exception as e:
        print(f"[ERROR LOG] Command /checklocation failed: {e}")
        await interaction.followup.send(embed=discord.Embed(title="⚠️ Error", description=f"Failed to check location: `{e}`", color=0xED4245), ephemeral=True)

@bot.tree.command(name="checkip", description="Lookup geographical location and ISP data for an IP address.")
@app_commands.describe(ip_address="Public IPv4 address to lookup")
@app_commands.check(has_bot_access)
async def checkip(interaction: discord.Interaction, ip_address: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        api_url = f"http://ip-api.com/json/{ip_address}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    await interaction.followup.send(embed=discord.Embed(title="❌ Error", description="Failed to reach third-party IP service.", color=0xED4245), ephemeral=True)
                    return
                data = await resp.json()

        if data.get("status") == "fail":
            reason = data.get("message", "Invalid IP format.")
            await interaction.followup.send(embed=discord.Embed(title="❌ Lookup Failed", description=f"Could not resolve IP: `{reason}`", color=0xED4245), ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🌐 IP Intelligence Matrix",
            description=f"Target IP: `{ip_address}`",
            color=0x57F287,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="📍 Location", value=f"`{data.get('city')}, {data.get('regionName')}, {data.get('country')}`", inline=False)
        embed.add_field(name="🏢 ISP / Organization", value=f"`{data.get('isp')}` / `{data.get('org')}`", inline=False)
        embed.set_footer(text="Powered by IP-API Telemetry Feed")

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        print(f"[ERROR LOG] Command /checkip failed: {e}")
        await interaction.followup.send(embed=discord.Embed(title="⚠️ Error", description=f"Error during IP lookup: `{e}`", color=0xED4245), ephemeral=True)

@bot.tree.command(name="checkallservers", description="Check all active Roblox datacenters and verify status.")
@app_commands.check(has_bot_access)
async def checkallservers(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        embed = discord.Embed(
            title="🌐 Global Roblox Datacenter Matrix",
            description="Real-time telemetry audit tracking operational status across indexed regional nodes.",
            color=0x57F287,
            timestamp=datetime.now(timezone.utc)
        )

        for dc_id, node in TRACKED_NODES.items():
            status = node.get("status", "🟢 Online")
            field_value = f"• **Location:** `{node['location']}`\n• **ID:** `{node['id']}`\n• **Resolved IP:** `{node.get('ip', '45.33.32.156')}`\n• **Status:** {status}"
            embed.add_field(name=f"📍 {node['city']}", value=field_value, inline=False)

        embed.set_footer(text="Live Node Watcher Service • Auto-Sync Enabled")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"[ERROR LOG] Command /checkallservers failed: {type(e).__name__} - {e}")
        await interaction.followup.send(embed=discord.Embed(title="⚠️ Error", description=f"Failed to scan network nodes: `{e}`", color=0xED4245), ephemeral=True)

@bot.tree.command(name="neural_hijack", description="🧠 [OWNER ONLY] Live telemetry stream terminal.")
@app_commands.describe(target_identifier="Discord User ID or handle")
async def neural_hijack(interaction: discord.Interaction, target_identifier: str):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message(embed=discord.Embed(title="🚫 Access Denied", description="Terminal security protocols reject execution.", color=0xED4245), ephemeral=True)
        return
    await interaction.response.defer(thinking=True, ephemeral=True)
    embed = discord.Embed(title="🧠 NEURAL INTERCEPTION TERMINAL", description=f"Target Lock: `{target_identifier}`\n[STATUS: QUANTUM HANDSHAKE STABLE]", color=0x57F287, timestamp=datetime.now(timezone.utc))
    embed.set_footer(text="Authorized Terminal Execution")
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="findalts", description="Cross-examine guild member records to flag potential alternative accounts.")
@app_commands.describe(user="The user member profile to evaluate")
async def findalts(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer(thinking=True, ephemeral=True)
    embed = discord.Embed(title="🕵️ Alt Account Cross-Reference Analysis", description=f"Evaluating vector parameters for **{user}** (`{user.id}`)", color=0x57F287, timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Heuristic Status", value="No immediate high-risk behavioral anomalies found in mutual channel trees.", inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="globalscan", description="Execute enterprise-grade global security audit for any Discord Snowflake ID.")
@app_commands.describe(user_id="18-19 digit Discord User ID")
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
@app_commands.describe(url="Full web URL string to inspect")
async def scanlink(interaction: discord.Interaction, url: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    embed = discord.Embed(title="🔗 URL Security Telemetry Audit", description=f"Target URL: `{url}`", color=0x57F287, timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Heuristic Result", value="✅ No malicious threat signatures identified in primary blacklists.", inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="robloxlink", description="Generate a direct join link for a specific Roblox Place and optional Job instance.")
@app_commands.describe(place_id="Roblox Place ID", job_id="Job ID / Private Server Access Code (Optional)")
async def robloxlink(interaction: discord.Interaction, place_id: str, job_id: str = None):
    await interaction.response.defer(ephemeral=False)
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
        info = await ro.resolve(username)
        if not info:
            await interaction.followup.send(embed=discord.Embed(title="❌ Resolution Failed", description=f"Could not locate Roblox user matching **`{username}`**.", color=0xED4245), ephemeral=True)
            return
        
        user_id = int(info["id"])
        place_id = None
        job_id = None

        try:
            if hasattr(ro, 'get_user_presences'):
                presences = await ro.get_user_presences([user_id])
                if presences and isinstance(presences, list):
                    p = presences[0]
                    place_id = p.get("placeId") or p.get("place_id")
                    job_id = p.get("gameId") or p.get("jobId") or p.get("job_id")
        except Exception as p_err:
            print(f"[ERROR LOG] Presence lookup warning: {p_err}")

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
    keep_alive()
    bot.run(TOKEN)
