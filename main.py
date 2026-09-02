from datetime import datetime, timezone
import asyncio
import os
import random
import re
from threading import Thread
import traceback
import json
import unicodedata

import aiohttp
from aiohttp import web
import socketio

import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask

import ro

# --- Target Verification Website URL ---
VERCEL_SITE_URL = "https://website2-umber-zeta.vercel.app/"

# --- Keep-Alive Web Server Setup (Flask) ---
app = Flask("")


@app.route("/")
def home():
  return "Bot is active and running!"


def run_flask():
  # Keep Flask on port 8080 (unchanged)
  app.run(host="0.0.0.0", port=8080)


def keep_alive():
  t = Thread(target=run_flask, daemon=True)
  t.start()


# ----------------------------------------------------
# Discord/Alert settings
WEBHOOK_URL = "https://discord.com/api/webhooks/1544127043023667221/BUrnc0QZlvPk4RSWLWb4oiAoyuAmrMBrEq8ui39M2T00p6rpM4L_5Ec7wKM0GJHJYgCW"
DATACENTER_ALERT_WEBHOOK_URL = WEBHOOK_URL
KNOWN_DATACENTERS_FILE = "known_datacenters.json"

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
  raise RuntimeError("DISCORD_BOT_TOKEN is missing from environment variables.")

APP_OWNER_ID = int(
    os.getenv("APP_OWNER_ID", "1256992368477864029") or 1256992368477864029
)
REQUIRED_ROLE_ID = int(
    os.getenv("REQUIRED_ROLE_ID", "1457867706790580317") or 1457867706790580317
)
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID", "").strip()

ALL_LOGS_CHANNEL_ID = 1540448203323875430
VERIFY_LOG_CHANNEL_ID = 1541463371394711583
OWNER_ID = 1256992368477864029

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# --- Known nodes (prepopulated) ---
TRACKED_NODES = {
    # North America
    "31204": {
        "city": "Ashburn",
        "location": "Ashburn, Virginia, US",
        "id": "31204",
        "ip": "45.79.19.102",
    },
    "53": {
        "city": "Ashburn",
        "location": "Ashburn, Virginia, US",
        "id": "53",
        "ip": "45.33.18.2",
    },
    "101": {
        "city": "Chicago",
        "location": "Chicago, Illinois, US",
        "id": "101",
        "ip": "192.155.85.2",
    },
    "95": {
        "city": "Dallas",
        "location": "Dallas, Texas, US",
        "id": "95",
        "ip": "45.79.4.11",
    },
    "116": {
        "city": "Los Angeles",
        "location": "Los Angeles, California, US",
        "id": "116",
        "ip": "45.79.8.19",
    },
    "26228": {
        "city": "New York",
        "location": "New York, US",
        "id": "26228",
        "ip": "172.105.99.14",
    },
    "32": {
        "city": "New York City",
        "location": "New York City, New York, US",
        "id": "32",
        "ip": "172.104.2.19",
    },
    "115": {
        "city": "Seattle",
        "location": "Seattle, Washington, US",
        "id": "115",
        "ip": "198.58.100.4",
    },
    "24110": {
        "city": "São Paulo",
        "location": "São Paulo, BR",
        "id": "24110",
        "ip": "177.54.144.12",
    },
    # Europe
    "213": {
        "city": "Amsterdam",
        "location": "Amsterdam, North Holland, NL",
        "id": "213",
        "ip": "178.128.150.18",
    },
    "19823": {
        "city": "Frankfurt",
        "location": "Frankfurt, Hesse, DE",
        "id": "19823",
        "ip": "139.59.130.22",
    },
    "214": {
        "city": "Frankfurt",
        "location": "Frankfurt, Hesse, DE",
        "id": "214",
        "ip": "139.59.150.90",
    },
    "33": {
        "city": "London",
        "location": "London, England, GB",
        "id": "33",
        "ip": "178.62.204.5",
    },
    "212": {
        "city": "Paris",
        "location": "Paris, Île-de-France, FR",
        "id": "212",
        "ip": "159.65.120.44",
    },
    "26330": {
        "city": "Warsaw",
        "location": "Warsaw, Mazovia, PL",
        "id": "26330",
        "ip": "159.203.88.10",
    },
    # Asia-Pacific, Middle East & Newer Global Nodes
    "34044": {
        "city": "Manama",
        "location": "Manama, Capital Governorate, BH",
        "id": "34044",
        "ip": "139.59.99.11",
    },
    "211": {
        "city": "Singapore",
        "location": "Singapore, SG",
        "id": "211",
        "ip": "139.59.230.15",
    },
    "18559": {
        "city": "Sydney",
        "location": "Sydney, New South Wales, AU",
        "id": "18559",
        "ip": "139.162.24.11",
    },
    "21402": {
        "city": "Tokyo",
        "location": "Tokyo, Kantō, JP",
        "id": "21402",
        "ip": "139.162.112.45",
    },
    "55": {
        "city": "Tokyo",
        "location": "Tokyo, Kantō, JP",
        "id": "55",
        "ip": "172.104.90.1",
    },
    "CPT_01": {
        "city": "Cape Town",
        "location": "Cape Town, South Africa",
        "id": "CPT_01",
        "ip": "196.28.178.1",
    },
    "SCL_01": {
        "city": "Santiago",
        "location": "Santiago, Chile",
        "id": "SCL_01",
        "ip": "200.9.110.1",
    },
    "IST_01": {
        "city": "Istanbul",
        "location": "Istanbul, Turkey",
        "id": "IST_01",
        "ip": "185.93.0.1",
    },
    "MIL_01": {
        "city": "Milan",
        "location": "Milan, Italy",
        "id": "MIL_01",
        "ip": "185.22.172.1",
    },
    "ATH_01": {
        "city": "Athens",
        "location": "Athens, Greece",
        "id": "ATH_01",
        "ip": "212.205.0.1",
    },
    "ZRH_01": {
        "city": "Zürich",
        "location": "Zürich, Switzerland",
        "id": "ZRH_01",
        "ip": "193.134.0.1",
    },
}

SEEN_SERVERS = set()
SEEN_TESTING_SERVERS = set()
KNOWN_HOST_REGIONS = {node["city"].lower() for node in TRACKED_NODES.values()}

# --- Dashboard (Socket.IO) globals ---
SIO_APP_PORT = int(os.getenv("SIO_APP_PORT", "8081"))
sio = socketio.AsyncServer(async_mode="aiohttp", cors_allowed_origins="*")
sio_aio_app = web.Application()
sio.attach(sio_aio_app)

# Simple JSON file helpers
def _load_json_file(path, default):
  try:
    if os.path.exists(path):
      with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
  except Exception:
    pass
  return default

def _save_json_file(path, data):
  try:
    with open(path, "w", encoding="utf-8") as f:
      json.dump(data, f, indent=2, ensure_ascii=False)
  except Exception as e:
    print(f"[ERROR LOG] Failed to save {path}: {e}")

def normalize_city(name: str) -> str:
  if not name:
    return ""
  n = unicodedata.normalize("NFKD", name)
  n = "".join(ch for ch in n if not unicodedata.combining(ch))
  n = n.lower()
  n = re.sub(r"[^\w\s]", " ", n)
  n = re.sub(r"\s+", " ", n).strip()
  return n

def make_dcid(city: str, ip: str) -> str:
  safe_city = re.sub(r"[^\w]", "_", city.strip().upper()) if city else "UNKNOWN"
  safe_ip = ip.replace(".", "_") if ip else "0_0_0_0"
  return f"{safe_city}_{safe_ip}"

def load_known_datacenters():
  try:
    data = _load_json_file(KNOWN_DATACENTERS_FILE, [])
    return list(data)
  except Exception:
    return []

def save_known_datacenters(datacenters):
  _save_json_file(KNOWN_DATACENTERS_FILE, list(sorted(datacenters)))

DC_SUBSCRIPTIONS_FILE = "dc_subscriptions.json"
DC_BOOKMARKS_FILE = "dc_bookmarks.json"
DC_GEO_CACHE_FILE = "dc_geo_cache.json"

def load_dc_subscriptions():
  return _load_json_file(DC_SUBSCRIPTIONS_FILE, {})

def save_dc_subscriptions(subs):
  _save_json_file(DC_SUBSCRIPTIONS_FILE, subs)

def load_bookmarks():
  return _load_json_file(DC_BOOKMARKS_FILE, {})

def save_bookmarks(b):
  _save_json_file(DC_BOOKMARKS_FILE, b)

def load_geo_cache():
  return _load_json_file(DC_GEO_CACHE_FILE, {})

def save_geo_cache(c):
  _save_json_file(DC_GEO_CACHE_FILE, c)

# Dashboard broadcast helper
async def broadcast_new_datacenter(dcid: str, city: str, ip: str, source: str = "auto"):
  payload = {
      "dcid": dcid,
      "city": city,
      "ip": ip,
      "source": source,
      "timestamp": datetime.now(timezone.utc).isoformat(),
  }
  try:
    await sio.emit("new_datacenter", payload)
  except Exception as e:
    print(f"[SIO ERROR] emit failed: {e}")

# Register datacenter (synchronous-ish)
def register_datacenter(city: str, ip: str, source: str = "auto"):
  if not city or not ip:
    return False, None
  dcid = make_dcid(city, ip)
  known = set(load_known_datacenters())
  if dcid in known:
    return False, dcid

  known.add(dcid)
  save_known_datacenters(known)

  TRACKED_NODES[dcid] = {
      "city": city,
      "location": f"{city}, {''}",
      "id": dcid,
      "ip": ip,
      "status": "🟢 Online",
      "discovered_by": source,
      "discovered_at": datetime.now(timezone.utc).isoformat(),
  }
  KNOWN_HOST_REGIONS.add(normalize_city(city))
  # cache geolocation lookup placeholder (populated later)
  geo_cache = load_geo_cache()
  geo_cache[dcid] = geo_cache.get(dcid, {"ip": ip, "lat": None, "lon": None, "city": city})
  save_geo_cache(geo_cache)
  # schedule broadcast on the bot loop
  try:
    asyncio.get_event_loop().call_soon_threadsafe(lambda: asyncio.create_task(broadcast_new_datacenter(dcid, city, ip, source)))
  except Exception:
    # fallback: create a task if loop exists
    try:
      asyncio.create_task(broadcast_new_datacenter(dcid, city, ip, source))
    except Exception:
      pass
  return True, dcid

# Discord helpers
async def log_to_channel(channel_id: int, content: str) -> None:
  try:
    channel = await bot.fetch_channel(channel_id)
    if channel and isinstance(channel, discord.TextChannel):
      if len(content) > 1990:
        content = content[:1987] + "..."
      await channel.send(content)
  except Exception as e:
    print(
        f"[ERROR LOG] Failed to send log to channel {channel_id}:"
        f" {type(e).__name__} - {e}"
    )

class RequiredRoleError(app_commands.CheckFailure):
  pass

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
    raise app_commands.CheckFailure(
        "Only the configured app owner can use this command."
    )

  return app_commands.check(predicate)

class GuildOnlyCommandTree(app_commands.CommandTree):

  async def interaction_check(self, interaction: discord.Interaction) -> bool:
    if not interaction.guild:
      await interaction.response.send_message(
          embed=discord.Embed(
              title="🚫 Restricted Access",
              description=(
                  "This command can only be used inside Discord servers, not in"
                  " direct messages."
              ),
              color=0xED4245,
          ),
          ephemeral=True,
      )
      return False
    return True

class PersistentVerificationView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="Verify Account",
      style=discord.ButtonStyle.green,
      custom_id="persistent_verify:btn",
      emoji="✅",
  )
  async def verify_button(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
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
            age_diff = abs(
                (target_created - member_created).total_seconds()
            )

            if age_diff < 172800:
              reasons.append("<48h window")
              alt_score += 4

            member_name_base = re.sub(r"\d+", "", member.name).lower()
            if (
                target_name_base
                and member_name_base
                and (
                    target_name_base in member_name_base
                    or member_name_base in target_name_base
                )
                and len(target_name_base) > 3
            ):
              reasons.append("Matching name pattern")
              alt_score += 3

            if (now_utc - member_created).days < 14:
              reasons.append("New/Burner velocity")
              alt_score += 2

            if alt_score >= 4:
              suspects.append(
                  f"• **{member}** (`{member.id}`) [Score: `{alt_score}` |"
                  f" {', '.join(reasons)}]"
              )
    except Exception as alt_err:
      print(
          "[ERROR LOG] Error scanning alts in verification view:"
          f" {type(alt_err).__name__} - {alt_err}"
      )

    alt_summary = (
        "\n".join(suspects[:3])
        if suspects
        else (
            "No high-probability linked accounts detected across mutual nodes."
        )
    )

    try:
      verify_log_channel = await interaction.client.fetch_channel(
          VERIFY_LOG_CHANNEL_ID
      )
      log_embed = discord.Embed(
          title="🛡️ Verification Gate Triggered",
          description=(
              f"User **{interaction.user}** (`{interaction.user.id}`)"
              " initialized the secure verification process."
          ),
          color=0x2B2D31,
          timestamp=now_utc,
      )
      log_embed.add_field(
          name="📊 Account Metadata",
          value=(
              "• **Created At:**"
              f" `<t:{int(interaction.user.created_at.timestamp())}:R>`"
          ),
          inline=False,
      )
      log_embed.add_field(
          name="🕵️ Potential Alts Heuristic",
          value=alt_summary[:1024],
          inline=False,
      )
      log_embed.set_footer(
          text="Security Telemetry Subsystem v2.4",
          icon_url=interaction.user.display_avatar.url,
      )
      await verify_log_channel.send(embed=log_embed)
    except Exception as log_err:
      print(
          "[ERROR LOG] Failed to dispatch verification log embed:"
          f" {type(log_err).__name__} - {log_err}"
      )

    embed = discord.Embed(
        title="🔒 Secure Authentication Portal",
        description=(
            "Your account has been successfully verified!\n\n🌐 THIS VERIFY"
            " DOES NOT TAKE IPS OR ANY SUCH INFO\n\n"
        ),
        color=0x57F287,
    )
    embed.add_field(
        name="Direct Portal Link",
        value=f"🔗 [Click Here to Proceed]({VERCEL_SITE_URL})",
        inline=False,
    )
    embed.set_footer(text="Protected by Enterprise Node Security")
    await interaction.response.send_message(embed=embed, ephemeral=True)


class UnifiedForensicsBot(commands.Bot):

  def __init__(self) -> None:
    super().__init__(
        command_prefix="!", intents=intents, tree_cls=GuildOnlyCommandTree
    )

  async def setup_hook(self) -> None:
    self.add_view(PersistentVerificationView())
    self.loop.create_task(monitor_live_game_servers())
    self.loop.create_task(monitor_client_versions())
    self.loop.create_task(monitor_testing_and_staging_servers())
    self.loop.create_task(monitor_datacenter_discoveries())
    # start dashboard aiohttp + socket.io server
    self.loop.create_task(start_dashboard_server())

    try:
      if DISCORD_GUILD_ID:
        guild_obj = discord.Object(id=int(DISCORD_GUILD_ID))
        self.tree.copy_global_to(guild=guild_obj)
        synced = await self.tree.sync(guild=guild_obj)
        print(
            "[SYNC] Instantly synced"
            f" {len(synced)} commands to Guild ID: {DISCORD_GUILD_ID}"
        )
      else:
        synced = await self.tree.sync()
        print(f"[SYNC] Synced {len(synced)} commands globally.")

      asyncio.create_task(
          log_to_channel(
              ALL_LOGS_CHANNEL_ID,
              (
                  "⚙️ Command tree synced successfully"
                  f" ({len(synced)} commands registered)."
              ),
          )
      )
    except Exception as e:
      print(f"[ERROR LOG] Failed to sync commands tree: {type(e).__name__} - {e}")

  async def on_ready(self) -> None:
    if self.user:
      print(
          "[INFO] Bot logged in successfully as"
          f" {self.user} (ID: {self.user.id})"
      )
      asyncio.create_task(
          log_to_channel(
              ALL_LOGS_CHANNEL_ID,
              f"🟢 **System Online:** Authenticated as `{self.user}`",
          )
      )


bot = UnifiedForensicsBot()

# --- Global App Command Error Handler ---
@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
  if isinstance(error, RequiredRoleError):
    embed = discord.Embed(
        title="🚫 Access Denied", description=str(error), color=0xED4245
    )
    if interaction.response.is_done():
      await interaction.followup.send(embed=embed, ephemeral=True)
    else:
      await interaction.response.send_message(embed=embed, ephemeral=True)
  elif isinstance(error, app_commands.CheckFailure):
    embed = discord.Embed(
        title="🚫 Permission Error",
        description="You do not have permission to execute this command.",
        color=0xED4245,
    )
    if interaction.response.is_done():
      await interaction.followup.send(embed=embed, ephemeral=True)
    else:
      await interaction.response.send_message(embed=embed, ephemeral=True)
  else:
    print(f"[COMMAND ERROR] {error}")

# --- Roblox server scanning helpers (unchanged) ---
async def fetch_all_active_servers(place_id: int, session: aiohttp.ClientSession):
  url = f"https://games.roblox.com/v1/games/{place_id}/servers/Public?limit=100"
  cursor = ""
  all_servers = []

  while True:
    paginated_url = f"{url}&cursor={cursor}" if cursor else url
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
      async with session.get(paginated_url, headers=headers) as resp:
        if resp.status != 200:
          break
        data = await resp.json()
        all_servers.extend(data.get("data", []))

        cursor = data.get("nextPageCursor")
        if not cursor:
          break
    except Exception as e:
      print(f"[ERROR LOG] Failed fetching paginated servers: {e}")
      break

  return all_servers

async def resolve_server_ip_and_region(
    session: aiohttp.ClientSession, place_id: int, job_id: str
):
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
      geo_url = f"http://ip-api.com/json/{clean_ip}"
      async with session.get(geo_url) as geo_resp:
        if geo_resp.status == 200:
          geo_data = await geo_resp.json()
          if geo_data.get("status") == "success":
            # update geo cache if we have a DC created earlier
            try:
              dcid = make_dcid(geo_data.get("city", "Unknown City"), clean_ip)
              geo_cache = load_geo_cache()
              geo_cache.setdefault(dcid, {})
              geo_cache[dcid].update({"ip": clean_ip, "lat": geo_data.get("lat"), "lon": geo_data.get("lon"), "city": geo_data.get("city")})
              save_geo_cache(geo_cache)
            except Exception:
              pass
            return {
                "ip": clean_ip,
                "city": geo_data.get("city", "Unknown City"),
                "country": geo_data.get("country", "Unknown Country"),
                "isp": geo_data.get("isp", "Roblox Infrastructure"),
                "lat": geo_data.get("lat"),
                "lon": geo_data.get("lon"),
            }
  except Exception as e:
    print(f"[ERROR LOG] Failed scanning region for job {job_id}: {e}")

  return None

# --- Background monitors (unchanged behavior), but they will emit to the dashboard when registering new DCs --- #
async def monitor_client_versions():
  """Monitors Roblox client deployment channels for builds/testing rollouts without flip-flop spam."""
  await bot.wait_until_ready()
  last_alerted_versions = {}
  channels = ["WindowsPlayer", "MacPlayer"]
  
  while not bot.is_closed():
    try:
      async with aiohttp.ClientSession() as session:
        for channel in channels:
          url = f"https://clientsettingscdn.roblox.com/v1/client-version/{channel}"
          async with session.get(url) as resp:
            if resp.status == 200:
              data = await resp.json()
              client_version = data.get("clientVersionUpload")
              if client_version:
                if channel not in last_alerted_versions:
                  last_alerted_versions[channel] = client_version
                elif client_version != last_alerted_versions[channel]:
                  old_version = last_alerted_versions[channel]
                  last_alerted_versions[channel] = client_version
                  
                  embed = {
                      "title": f"🧪 New Roblox {channel} Build / Testing Rollout Detected!",
                      "color": 16776960,
                      "fields": [
                          {"name": "Deployment Channel", "value": f"`{channel}`", "inline": True},
                          {"name": "Previous Build", "value": f"`{old_version}`", "inline": False},
                          {"name": "New Build Hash", "value": f"`{client_version}`", "inline": False},
                          {"name": "Status", "value": "⚠️ Edge nodes and test servers are spinning up fresh updates.", "inline": False}
                      ],
                      "footer": {"text": "Client Deployment Telemetry Watcher"}
                  }
                  
                  async with session.post(
                      DATACENTER_ALERT_WEBHOOK_URL, json={"embeds": [embed]}
                  ) as webhook_resp:
                    pass
    except Exception as e:
      print(f"[ERROR LOG] Client version monitor error: {type(e).__name__} - {e}")
    
    await asyncio.sleep(300)


async def monitor_datacenter_discoveries():
  """Scans for new Roblox host regions/datacenters and alerts via Discord webhook."""
  await bot.wait_until_ready()
  known_dcs = set(load_known_datacenters())
  TARGET_PLACE_IDS = [920587237, 1818, 3237166, 4483381587]

  while not bot.is_closed():
    try:
      async with aiohttp.ClientSession() as session:
        for place_id in TARGET_PLACE_IDS:
          servers = await fetch_all_active_servers(place_id, session)
          for server in servers:
            job_id = server.get("id")
            if not job_id:
              continue
            region_info = await resolve_server_ip_and_region(session, place_id, job_id)
            if not region_info:
              continue
            city = region_info.get("city", "Unknown City")
            ip = region_info.get("ip", "0.0.0.0")
            dcid = make_dcid(city, ip)
            if dcid not in known_dcs:
              is_new, created_dcid = register_datacenter(city, ip, source="datacenter_discovery")
              known_dcs.add(created_dcid)
              # send alert embed with DCID and IP
              embed = {
                  "title": "📍 New Datacenter Discovered",
                  "description": f"A new Roblox datacenter was discovered in **{city}**.",
                  "color": 15158332,
                  "fields": [
                      {"name": "Datacenter ID", "value": f"`{created_dcid}`", "inline": True},
                      {"name": "Location", "value": f"`{city}, {region_info.get('country')}`", "inline": True},
                      {"name": "IP Address", "value": f"`{ip}`", "inline": False},
                      {"name": "Discovery Source", "value": f"`place:{place_id} job:{job_id}`", "inline": False}
                  ],
                  "footer": {"text": "RoValra Datacenter notifier"}
              }
              async with session.post(
                  DATACENTER_ALERT_WEBHOOK_URL, json={"embeds": [embed]}
              ) as webhook_resp:
                pass
    except Exception as e:
      print(f"[ERROR LOG] Datacenter tracker error: {type(e).__name__} - {e}")
    await asyncio.sleep(600)


async def monitor_testing_and_staging_servers():
  """Background daemon continuously scouting brand new servers and entirely new host regions."""
  await bot.wait_until_ready()
  TARGET_PLACE_IDS = [920587237, 1818, 3237166, 4483381587]
  
  while not bot.is_closed():
    try:
      async with aiohttp.ClientSession() as session:
        for place_id in TARGET_PLACE_IDS:
          servers = await fetch_all_active_servers(place_id, session)
          for server in servers:
            job_id = server.get("id")
            if not job_id:
              continue
              
            if job_id not in SEEN_TESTING_SERVERS:
              SEEN_TESTING_SERVERS.add(job_id)
              region_info = await resolve_server_ip_and_region(session, place_id, job_id)
              if region_info:
                city = region_info['city']
                ip = region_info['ip']
                city_lower = city.lower()
                is_brand_new_region = city_lower not in KNOWN_HOST_REGIONS
                if is_brand_new_region:
                  registered, dcid = register_datacenter(city, ip, source="testing_scan")
                else:
                  dcid = make_dcid(city, ip)

                KNOWN_HOST_REGIONS.add(city_lower)

                ping = server.get("ping", 0)
                playing = server.get("playing", 0)
                max_players = server.get("maxPlayers", 0)
                
                title_text = f"🚨 Brand New Roblox Host Region Discovered ({city})!" if is_brand_new_region else "🧪 Brand New Server / Testing Instance Spawned!"
                color_val = 16711680 if is_brand_new_region else 15158332

                embed = {
                    "title": title_text,
                    "color": color_val,
                    "fields": [
                        {"name": "Datacenter ID", "value": f"`{dcid}`", "inline": True},
                        {"name": "Location", "value": f"{city}, {region_info['country']}", "inline": True},
                        {"name": "IP Node", "value": f"`{ip}`", "inline": False},
                        {"name": "ISP / Host", "value": region_info['isp'], "inline": True},
                        {"name": "Player Load", "value": f"`{playing}/{max_players}`", "inline": True},
                        {"name": "Node Latency", "value": f"`{ping} ms`", "inline": True},
                        {"name": "Job ID", "value": f"`{job_id}`", "inline": False},
                        {
                            "name": "Direct Join Link",
                            "value": f"__[Join Testing Instance](https://www.roblox.com/games/{place_id}?privateServerLinkCode={job_id})__",
                            "inline": False
                        }
                    ],
                    "footer": {"text": "Staging & Testing Server Radar • Real-Time Interception"}
                }
                
                async with session.post(DATACENTER_ALERT_WEBHOOK_URL, json={"embeds": [embed]}) as resp:
                  pass
                  
          if len(SEEN_TESTING_SERVERS) > 3000:
            SEEN_TESTING_SERVERS.clear()
    except Exception as e:
      print(f"[ERROR LOG] Testing server monitor error: {e}")
      
    await asyncio.sleep(20)


async def monitor_live_game_servers():
  await bot.wait_until_ready()
  TARGET_PLACE_IDS = [920587237, 1818, 3237166, 4483381587]

  async with aiohttp.ClientSession() as session:
    for place_id in TARGET_PLACE_IDS:
      initial_servers = await fetch_all_active_servers(place_id, session)
      for server in initial_servers:
        job_id = server.get("id")
        if job_id:
          SEEN_SERVERS.add(job_id)
    print(f"[HOST SCANNER] Initialized tracking with {len(SEEN_SERVERS)} active servers.")

  while not bot.is_closed():
    try:
      async with aiohttp.ClientSession() as session:
        for target_place_id in TARGET_PLACE_IDS:
          current_servers = await fetch_all_active_servers(target_place_id, session)
          current_server_ids = {s.get("id") for s in current_servers if s.get("id")}

          new_servers_found = []
          for server in current_servers:
            job_id = server.get("id")
            if not job_id:
              continue
            
            if job_id not in SEEN_SERVERS:
              SEEN_SERVERS.add(job_id)
              new_servers_found.append((server, target_place_id))

          dead_servers = SEEN_SERVERS - current_server_ids
          for dead_id in dead_servers:
            SEEN_SERVERS.remove(dead_id)

          if len(SEEN_SERVERS) > 2500:
            SEEN_SERVERS.clear()

          for server, p_id in new_servers_found:
            job_id = server.get("id")
            new_region = await resolve_server_ip_and_region(
                session, p_id, job_id
            )
            if new_region:
              city = new_region['city']
              ip = new_region['ip']
              city_lower = city.lower()
              is_brand_new_region = city_lower not in KNOWN_HOST_REGIONS
              if is_brand_new_region:
                registered, dcid = register_datacenter(city, ip, source="live_scan")
              else:
                dcid = make_dcid(city, ip)
              KNOWN_HOST_REGIONS.add(city_lower)

              ping = server.get("ping", 0)
              playing = server.get("playing", 0)
              max_players = server.get("maxPlayers", 0)

              title_text = f"🚨 Brand New Roblox Host Region Discovered ({city})!" if is_brand_new_region else "🚨 New Roblox Country/Region Discovered!"
              color_val = 16711680 if is_brand_new_region else 16711680

              embed = {
                  "title": title_text,
                  "color": color_val,
                  "fields": [
                      {"name": "Datacenter ID", "value": f"`{dcid}`", "inline": True},
                      {"name": "Country", "value": new_region["country"], "inline": True},
                      {"name": "City", "value": new_region["city"], "inline": True},
                      {"name": "IP Node", "value": f"`{new_region['ip']}`", "inline": False},
                      {"name": "ISP / Host", "value": new_region["isp"], "inline": True},
                      {"name": "Player Load", "value": f"`{playing}/{max_players}`", "inline": True},
                      {"name": "Node Latency / Ping", "value": f"`{ping} ms`", "inline": True},
                      {"name": "Job ID", "value": f"`{job_id}`", "inline": False},
                      {
                          "name": "Direct Join Link",
                          "value": (
                              "__[Join Server](https://www.roblox.com/games/"
                              f"{p_id}?privateServerLinkCode={job_id})__"
                          ),
                          "inline": False,
                      },
                  ],
                  "footer": {
                      "text": "Live Instance Radar • Region Tracking Active"
                  },
              }

              async with session.post(
                  DATACENTER_ALERT_WEBHOOK_URL, json={"embeds": [embed]}
              ) as webhook_resp:
                pass
    except Exception as e:
      print(f"[ERROR LOG] Live server tracker error: {type(e).__name__} - {e}")

    await asyncio.sleep(45)


# ----------------- Socket.IO dashboard server ----------------- #
# HTML client served at the aiohttp root path
DASH_HTML = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Datacenter Dashboard</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
      body { font-family: Arial, Helvetica, sans-serif; background:#0f1720; color:#e6eef8; padding:20px; }
      .card { background:#111827; border-radius:8px; padding:12px; margin-bottom:10px; box-shadow:0 2px 6px rgba(0,0,0,0.6); }
      .new { border-left:4px solid #34d399; padding-left:8px; }
      .list { max-height: 60vh; overflow:auto; }
      h1 { margin-top:0; }
      .meta { color:#9aa8bf; font-size:13px; }
    </style>
  </head>
  <body>
    <h1>Datacenter Real-Time Dashboard</h1>
    <p class="meta">Connected: <span id="status">no</span></p>
    <div id="events"></div>
    <h2>Known Datacenters</h2>
    <div id="known" class="list"></div>
    <script>
      const socket = io();
      const statusEl = document.getElementById('status');
      const eventsEl = document.getElementById('events');
      const knownEl = document.getElementById('known');

      socket.on('connect', () => {
        statusEl.textContent = 'yes';
        socket.emit('request_known_datacenters');
      });
      socket.on('disconnect', () => statusEl.textContent='no');

      socket.on('new_datacenter', (data) => {
        const card = document.createElement('div');
        card.className = 'card new';
        card.innerHTML = `<strong>New DC:</strong> ${data.city} (${data.ip}) <br/><span class="meta">ID: ${data.dcid} • source: ${data.source} • ${data.timestamp}</span>`;
        eventsEl.prepend(card);
        // add to known list
        const item = document.createElement('div');
        item.className='card';
        item.innerHTML = `<strong>${data.city}</strong> <div class="meta">${data.dcid} • ${data.ip}</div>`;
        knownEl.prepend(item);
      });

      socket.on('known_datacenters', (list) => {
        knownEl.innerHTML = '';
        list.forEach(d => {
          const item = document.createElement('div');
          item.className='card';
          item.innerHTML = `<strong>${d.city}</strong> <div class="meta">${d.dcid} • ${d.ip || 'n/a'}</div>`;
          knownEl.appendChild(item);
        });
      });
    </script>
  </body>
</html>
"""

async def handle_root(request):
  return web.Response(text=DASH_HTML, content_type='text/html')

# Socket.IO event handlers
@sio.event
async def connect(sid, environ):
  print(f"[SIO] client connected: {sid}")

@sio.event
async def disconnect(sid):
  print(f"[SIO] client disconnected: {sid}")

@sio.on("request_known_datacenters")
async def handle_request_known(sid, data):
  # build a simple list from known datacenters
  try:
    known = load_known_datacenters()
    out = []
    geo_cache = load_geo_cache()
    for dcid in known:
      node = TRACKED_NODES.get(dcid, {})
      entry = {
        "dcid": dcid,
        "city": node.get("city", geo_cache.get(dcid, {}).get("city", "Unknown")),
        "ip": node.get("ip", geo_cache.get(dcid, {}).get("ip", None)),
      }
      out.append(entry)
    await sio.emit("known_datacenters", out, to=sid)
  except Exception as e:
    print(f"[SIO] failed to send known list: {e}")

async def start_dashboard_server():
  # attach root handler
  sio_aio_app.router.add_get("/", handle_root)
  # optionally add an HTTP route that returns known datacenters JSON
  async def known_json(request):
    known = load_known_datacenters()
    geo_cache = load_geo_cache()
    out = []
    for dcid in known:
      node = TRACKED_NODES.get(dcid, {})
      out.append({
        "dcid": dcid,
        "city": node.get("city", geo_cache.get(dcid, {}).get("city", node.get("city", "Unknown"))),
        "ip": node.get("ip", geo_cache.get(dcid, {}).get("ip"))
      })
    return web.json_response(out)
  sio_aio_app.router.add_get("/api/known", known_json)

  runner = web.AppRunner(sio_aio_app)
  await runner.setup()
  site = web.TCPSite(runner, "0.0.0.0", SIO_APP_PORT)
  await site.start()
  print(f"[SIO] Dashboard started on port {SIO_APP_PORT}")

# ----------------- Bot commands (select few shown; rest of your commands should remain intact) ----------------- #

@bot.tree.command(
    name="findnewhost",
    description="Scan, locate and sync newly created/testing Roblox servers matching datacenter format.",
)
@app_commands.check(has_bot_access)
async def findnewhost(interaction: discord.Interaction):
  await interaction.response.defer(thinking=True, ephemeral=True)
  try:
    TARGET_PLACE_IDS = [920587237, 1818, 3237166]
    found_nodes = []
    
    async with aiohttp.ClientSession() as session:
      for place_id in TARGET_PLACE_IDS:
        servers = await fetch_all_active_servers(place_id, session)
        # sample first servers to limit work
        for server in servers[:10]:
          job_id = server.get("id")
          if not job_id:
            continue
          
          region_info = await resolve_server_ip_and_region(session, place_id, job_id)
          if region_info:
            city = region_info["city"]
            ip = region_info["ip"]
            city_lower = city.lower()
            is_new_region = city_lower not in KNOWN_HOST_REGIONS
            dcid = make_dcid(city, ip)
            if is_new_region:
              registered, created_dcid = register_datacenter(city, ip, source="manual_findnewhost")
              dcid = created_dcid or dcid

            found_nodes.append({
                "dcid": dcid,
                "country": region_info["country"],
                "city": city,
                "ip": ip,
                "isp": region_info["isp"],
                "ping": server.get("ping", 0),
                "playing": server.get("playing", 0),
                "max": server.get("maxPlayers", 0),
                "job_id": job_id,
                "place_id": place_id,
                "is_new_region": is_new_region
            })

    if not found_nodes:
      await interaction.followup.send(
          embed=discord.Embed(
              title="🔍 Testing Host Radar",
              description="No new testing or staging nodes resolved in the active scan cycle. Try again shortly.",
              color=0xFEE75C
          ),
          ephemeral=True
      )
      return

    embed = discord.Embed(
        title="🚨 Brand New Roblox Host Region Discovered!" if any(n['is_new_region'] for n in found_nodes) else "🧪 Newly Spun-Up Testing & Staging Server Nodes",
        description="Real-time scan synchronized with datacenter telemetry feeds.",
        color=16711680 if any(n['is_new_region'] for n in found_nodes) else 0x57F287,
        timestamp=datetime.now(timezone.utc)
    )

    for node in found_nodes[:5]:
      join_url = f"https://www.roblox.com/games/{node['place_id']}?privateServerLinkCode={node['job_id']}"
      badge_text = " 🚨 [NEW REGION]" if node['is_new_region'] else ""
      field_value = (
          f"• **Datacenter ID:** `{node['dcid']}`\n"
          f"• **Location:** `{node['city']}, {node['country']}`{badge_text}\n"
          f"• **IP Node:** `{node['ip']}`\n"
          f"• **ISP/Host:** `{node['isp']}`\n"
          f"• **Players:** `{node['playing']}/{node['max']}` | **Ping:** `{node['ping']}ms`\n"
          f"• **Direct Link:** [Join Testing Instance]({join_url})"
      )
      embed.add_field(name=f"📍 Node [{node['city']}]", value=field_value, inline=False)

    embed.set_footer(text="Datacenter Telemetry Subsystem • Testing Node Matrix")
    
    async with aiohttp.ClientSession() as session:
      await session.post(DATACENTER_ALERT_WEBHOOK_URL, json={"embeds": [embed.to_dict()]})

    await interaction.followup.send(embed=embed, ephemeral=True)

  except Exception as e:
    print(f"[ERROR LOG] Command /findnewhost failed: {type(e).__name__} - {e}")
    await interaction.followup.send(
        embed=discord.Embed(
            title="⚠️ Error",
            description=f"Failed to scan testing hosts: `{e}`",
            color=0xED4245,
        ),
        ephemeral=True,
    )

# Other commands (user, avatar, groups, badges, scan, setup-verify, processdc, checklocation, checkip, checkallservers, etc.)
# Keep the rest of your existing commands here as in your original file.
# For brevity I omitted copying all unchanged commands, but they should remain in your main.py as before.
# Ensure you keep the unchanged command definitions from your previous file (they integrate with this dashboard).

if __name__ == "__main__":
  keep_alive()
  bot.run(TOKEN)