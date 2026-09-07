from datetime import datetime, timezone
import asyncio
import os
import re
from threading import Thread
import json
import unicodedata
from urllib.parse import urlparse
import ipaddress
import traceback

import aiohttp
from aiohttp import web
import socketio

import discord
from discord import app_commands
from discord.ext import commands

# ============================================================
# CONFIGURATION
# ============================================================

VERCEL_SITE_URL = "https://website2-umber-zeta.vercel.app/"

WEBHOOK_URL = "https://discord.com/api/webhooks/1544127043023667221/BUrnc0QZlvPk4RSWLWb4oiAoyuAmrMBrEq8ui39M2T00p6rpM4L_5Ec7wKM0GJHJYgCW"
DATACENTER_ALERT_WEBHOOK_URL = WEBHOOK_URL

KNOWN_DATACENTERS_FILE = "known_datacenters.json"
DC_SUBSCRIPTIONS_FILE = "dc_subscriptions.json"
DC_BOOKMARKS_FILE = "dc_bookmarks.json"
DC_GEO_CACHE_FILE = "dc_geo_cache.json"
TRACKED_NODES_FILE = "tracked_datacenters.json"

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN is missing from environment variables.")

APP_OWNER_ID = int(
    os.getenv("APP_OWNER_ID", "1256992368477864029")
    or 1256992368477864029
)
REQUIRED_ROLE_ID = int(
    os.getenv("REQUIRED_ROLE_ID", "1457867706790580317")
    or 1457867706790580317
)
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID", "").strip()

ALL_LOGS_CHANNEL_ID = 1540448203323875430
VERIFY_LOG_CHANNEL_ID = 1541463371394711583
OWNER_ID = 1256992368477864029

SIO_APP_PORT = int(os.getenv("PORT", os.getenv("SIO_APP_PORT", "10000")))

TARGET_PLACE_IDS = [920587237, 1818, 3237166, 4483381587]

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


# ============================================================
# KNOWN ROBLOX HOST NODES
# ============================================================

TRACKED_NODES = {
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

SEEN_SERVERS_BY_PLACE = {place_id: set() for place_id in TARGET_PLACE_IDS}
SEEN_TESTING_SERVERS_BY_PLACE = {place_id: set() for place_id in TARGET_PLACE_IDS}

KNOWN_HOST_REGIONS = {
    unicodedata.normalize("NFKD", node["city"])
    .encode("ascii", "ignore")
    .decode("ascii")
    .lower()
    for node in TRACKED_NODES.values()
}


# ============================================================
# JSON / DATACENTER HELPERS
# ============================================================

def _load_json_file(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[ERROR LOG] Failed loading {path}: {e}")
    return default


def _save_json_file(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR LOG] Failed saving {path}: {e}")


def normalize_city(name: str) -> str:
    if not name:
        return ""
    n = unicodedata.normalize("NFKD", name)
    n = "".join(ch for ch in n if not unicodedata.combining(ch))
    n = n.lower()
    n = re.sub(r"[^\w\s]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def make_dcid(city: str, ip: str) -> str:
    safe_city = re.sub(r"[^\w]", "_", city.strip().upper()) if city else "UNKNOWN"
    safe_ip = re.sub(r"[^0-9A-Fa-f:.]", "", ip or "").replace(".", "_").replace(":", "_")
    return f"{safe_city}_{safe_ip or 'UNKNOWN'}"


def load_known_datacenters():
    data = _load_json_file(KNOWN_DATACENTERS_FILE, [])
    return list(data) if isinstance(data, list) else []


def save_known_datacenters(datacenters):
    save_list = sorted(set(str(x) for x in datacenters))
    _save_json_file(KNOWN_DATACENTERS_FILE, save_list)


def load_dc_subscriptions():
    return _load_json_file(DC_SUBSCRIPTIONS_FILE, {})


def save_dc_subscriptions(subs):
    _save_json_file(DC_SUBSCRIPTIONS_FILE, subs)


def load_bookmarks():
    return _load_json_file(DC_BOOKMARKS_FILE, {})


def save_bookmarks(bookmarks):
    _save_json_file(DC_BOOKMARKS_FILE, bookmarks)


def load_geo_cache():
    return _load_json_file(DC_GEO_CACHE_FILE, {})


def save_geo_cache(cache):
    _save_json_file(DC_GEO_CACHE_FILE, cache)


def load_persisted_nodes():
    data = _load_json_file(TRACKED_NODES_FILE, {})
    if not isinstance(data, dict):
        return

    for dcid, node in data.items():
        if isinstance(node, dict):
            TRACKED_NODES[str(dcid)] = node

    KNOWN_HOST_REGIONS.update(
        normalize_city(node.get("city", ""))
        for node in data.values()
        if isinstance(node, dict) and node.get("city")
    )


def persist_tracked_nodes():
    _save_json_file(TRACKED_NODES_FILE, TRACKED_NODES)


load_persisted_nodes()


async def broadcast_new_datacenter(
    dcid: str,
    city: str,
    ip: str,
    source: str = "auto",
):
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
        "location": city,
        "id": dcid,
        "ip": ip,
        "status": "🟢 Online",
        "discovered_by": source,
        "discovered_at": datetime.now(timezone.utc).isoformat(),
    }

    KNOWN_HOST_REGIONS.add(normalize_city(city))

    geo_cache = load_geo_cache()
    geo_cache[dcid] = geo_cache.get(
        dcid,
        {
            "ip": ip,
            "lat": None,
            "lon": None,
            "city": city,
        },
    )
    save_geo_cache(geo_cache)
    persist_tracked_nodes()

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(
            broadcast_new_datacenter(dcid, city, ip, source)
        )
    except RuntimeError:
        pass

    return True, dcid


# ============================================================
# DISCORD HELPERS / PERMISSIONS
# ============================================================

async def log_to_channel(channel_id: int, content: str):
    try:
        channel = await bot.fetch_channel(channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            await channel.send(content[:1990] + ("..." if len(content) > 1990 else ""))
    except Exception as e:
        print(
            f"[ERROR LOG] Failed to send log to channel {channel_id}: "
            f"{type(e).__name__} - {e}"
        )


async def post_webhook(payload):
    if not DATACENTER_ALERT_WEBHOOK_URL:
        print("[WEBHOOK] Webhook URL is empty.")
        return False

    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                DATACENTER_ALERT_WEBHOOK_URL,
                json=payload,
            ) as response:
                if response.status >= 300:
                    text = await response.text()
                    print(
                        f"[WEBHOOK] HTTP {response.status}: {text[:500]}"
                    )
                    return False
                return True
    except Exception as e:
        print(f"[WEBHOOK] Failed: {type(e).__name__} - {e}")
        return False


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
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="🚫 Restricted Access",
                        description="This command can only be used inside Discord servers.",
                        color=0xED4245,
                    ),
                    ephemeral=True,
                )
            return False

        return True


# ============================================================
# VERIFICATION VIEW
# ============================================================

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
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        target = interaction.user
        target_created = target.created_at
        target_name_base = re.sub(r"\d+", "", target.name).lower()
        now_utc = datetime.now(timezone.utc)

        suspects = []
        checked_ids = set()

        try:
            for guild in interaction.client.guilds:
                if not guild.get_member(target.id):
                    continue

                for member in guild.members:
                    if member.id == target.id or member.id in checked_ids:
                        continue

                    checked_ids.add(member.id)

                    score = 0
                    reasons = []
                    member_created = member.created_at

                    age_diff = abs(
                        (target_created - member_created).total_seconds()
                    )

                    if age_diff < 172800:
                        reasons.append("<48h window")
                        score += 4

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
                        score += 3

                    if (now_utc - member_created).days < 14:
                        reasons.append("New account")
                        score += 2

                    if score >= 4:
                        suspects.append(
                            f"• **{member}** (`{member.id}`) "
                            f"[Score: `{score}` | {', '.join(reasons)}]"
                        )

        except Exception as e:
            print(f"[ERROR LOG] Verification scan failed: {e}")

        alt_summary = (
            "\n".join(suspects[:3])
            if suspects
            else "No high-probability linked accounts detected across mutual servers."
        )

        try:
            verify_log_channel = await interaction.client.fetch_channel(
                VERIFY_LOG_CHANNEL_ID
            )

            log_embed = discord.Embed(
                title="🛡️ Verification Gate Triggered",
                description=(
                    f"User **{interaction.user}** (`{interaction.user.id}`) "
                    "initialized the verification process."
                ),
                color=0x2B2D31,
                timestamp=now_utc,
            )

            log_embed.add_field(
                name="📊 Account Metadata",
                value=(
                    f"• **Created At:** "
                    f"<t:{int(target_created.timestamp())}:R>"
                ),
                inline=False,
            )

            log_embed.add_field(
                name="🕵️‍♂️ Potential Account Heuristic",
                value=alt_summary[:1024],
                inline=False,
            )

            log_embed.set_footer(
                text="Security Telemetry Subsystem v2.4",
                icon_url=interaction.user.display_avatar.url,
            )

            await verify_log_channel.send(embed=log_embed)

        except Exception as e:
            print(f"[ERROR LOG] Verification logging failed: {e}")

        embed = discord.Embed(
            title="🔒 Secure Authentication Portal",
            description=(
                "Your account has been successfully verified!\n\n"
                "🌐 THIS VERIFY DOES NOT TAKE IPS OR SUCH INFORMATION."
            ),
            color=0x57F287,
        )

        embed.add_field(
            name="Direct Portal Link",
            value=f"🔗 [Click Here to Proceed]({VERCEL_SITE_URL})",
            inline=False,
        )

        embed.set_footer(text="Protected by Enterprise Node Security")

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )


async def deploy_verify_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛡️ Account Verification",
        description=(
            "Click the button below to begin account verification.\n\n"
            "The verification flow does not request or collect IP addresses."
        ),
        color=0x57F287,
    )

    embed.set_footer(text="Verification System")

    await interaction.response.send_message(embed=embed)

    try:
        message = await interaction.original_response()
        await message.edit(view=PersistentVerificationView())
    except Exception as e:
        print(f"[ERROR LOG] Failed to attach verification view: {e}")


# ============================================================
# ROBLOX SERVER HELPERS
# ============================================================

async def fetch_all_active_servers(
    place_id: int,
    session: aiohttp.ClientSession,
    max_pages: int = 10,
):
    url = f"https://games.roblox.com/v1/games/{place_id}/servers/Public?limit=100"
    cursor = ""
    all_servers = []
    pages = 0

    while pages < max_pages:
        paginated_url = f"{url}&cursor={cursor}" if cursor else url
        headers = {"User-Agent": "Mozilla/5.0"}

        try:
            async with session.get(
                paginated_url,
                headers=headers,
            ) as response:
                if response.status != 200:
                    print(
                        f"[ROBLOX] Server list returned HTTP {response.status} "
                        f"for place {place_id}"
                    )
                    break

                data = await response.json()
                all_servers.extend(data.get("data", []))

                cursor = data.get("nextPageCursor")
                pages += 1

                if not cursor:
                    break

        except Exception as e:
            print(f"[ERROR LOG] Failed fetching servers: {e}")
            break

    return all_servers


def clean_host(value):
    if not value:
        return None

    value = str(value).strip()

    if "://" in value:
        parsed = urlparse(value)
        value = parsed.hostname or ""

    if value.startswith("[") and "]" in value:
        value = value[1:value.index("]")]

    if value.count(":") == 1:
        value = value.split(":", 1)[0]

    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        return None


async def resolve_server_ip_and_region(
    session: aiohttp.ClientSession,
    place_id: int,
    job_id: str,
):
    join_url = "https://gamejoin.roblox.com/v1/join-game-instance"
    payload = {
        "placeId": place_id,
        "gameId": job_id,
    }

    try:
        headers = {"Origin": "https://www.roblox.com"}

        async with session.post(
            join_url,
            json=payload,
            headers=headers,
        ) as response:
            if response.status != 200:
                return None

            data = await response.json()

        join_script = data.get("joinScript", {}) or {}

        server_address = (
            join_script.get("ClientServerHost")
            or join_script.get("MachineAddress")
            or data.get("serverAddress")
        )

        clean_ip = clean_host(server_address)

        if not clean_ip:
            return None

        geo_url = f"http://ip-api.com/json/{clean_ip}"

        async with session.get(geo_url) as geo_response:
            if geo_response.status != 200:
                return None

            geo_data = await geo_response.json()

        if geo_data.get("status") != "success":
            return None

        city = geo_data.get("city") or "Unknown City"

        return {
            "ip": clean_ip,
            "city": city,
            "country": geo_data.get("country", "Unknown Country"),
            "isp": geo_data.get("isp", "Unknown Host"),
            "lat": geo_data.get("lat"),
            "lon": geo_data.get("lon"),
        }

    except Exception as e:
        print(
            f"[ERROR LOG] Failed resolving server region for job "
            f"{job_id}: {type(e).__name__} - {e}"
        )

    return None


def public_game_url(place_id: int):
    return f"https://www.roblox.com/games/{place_id}"


# ============================================================
# BACKGROUND MONITORS
# ============================================================

async def monitor_client_versions():
    await bot.wait_until_ready()

    last_versions = {}
    channels = ["WindowsPlayer", "MacPlayer"]

    while not bot.is_closed():
        try:
            timeout = aiohttp.ClientTimeout(total=20)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                for channel in channels:
                    url = (
                        "https://clientsettingscdn.roblox.com/"
                        f"v1/client-version/{channel}"
                    )

                    async with session.get(url) as response:
                        if response.status != 200:
                            continue

                        data = await response.json()
                        client_version = data.get("clientVersionUpload")

                        if not client_version:
                            continue

                        if channel not in last_versions:
                            last_versions[channel] = client_version
                            continue

                        if client_version == last_versions[channel]:
                            continue

                        old_version = last_versions[channel]
                        last_versions[channel] = client_version

                        embed = {
                            "title": f"🧪 New Roblox {channel} Build Detected",
                            "color": 16776960,
                            "fields": [
                                {
                                    "name": "Deployment Channel",
                                    "value": f"`{channel}`",
                                    "inline": True,
                                },
                                {
                                    "name": "Previous Build",
                                    "value": f"`{old_version}`",
                                    "inline": False,
                                },
                                {
                                    "name": "New Build Hash",
                                    "value": f"`{client_version}`",
                                    "inline": False,
                                },
                            ],
                            "footer": {
                                "text": "Client Deployment Telemetry Watcher"
                            },
                        }

                        await post_webhook({"embeds": [embed]})

        except Exception as e:
            print(
                f"[ERROR LOG] Client version monitor error: "
                f"{type(e).__name__} - {e}"
            )

        await asyncio.sleep(300)


async def monitor_datacenter_discoveries():
    await bot.wait_until_ready()

    known_dcs = set(load_known_datacenters())

    while not bot.is_closed():
        try:
            timeout = aiohttp.ClientTimeout(total=30)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                for place_id in TARGET_PLACE_IDS:
                    servers = await fetch_all_active_servers(
                        place_id,
                        session,
                        max_pages=3,
                    )

                    for server in servers:
                        job_id = server.get("id")
                        if not job_id:
                            continue

                        region_info = await resolve_server_ip_and_region(
                            session,
                            place_id,
                            job_id,
                        )

                        if not region_info:
                            continue

                        city = region_info["city"]
                        ip = region_info["ip"]
                        dcid = make_dcid(city, ip)

                        if dcid in known_dcs:
                            continue

                        registered, created_dcid = register_datacenter(
                            city,
                            ip,
                            source="datacenter_discovery",
                        )

                        if not registered:
                            continue

                        known_dcs.add(created_dcid)

                        embed = {
                            "title": "📍 New Datacenter Discovered",
                            "description": (
                                f"A new Roblox infrastructure region was "
                                f"observed in **{city}**."
                            ),
                            "color": 15158332,
                            "fields": [
                                {
                                    "name": "Datacenter ID",
                                    "value": f"`{created_dcid}`",
                                    "inline": True,
                                },
                                {
                                    "name": "Location",
                                    "value": (
                                        f"`{city}, "
                                        f"{region_info['country']}`"
                                    ),
                                    "inline": True,
                                },
                                {
                                    "name": "Infrastructure IP",
                                    "value": f"`{ip}`",
                                    "inline": False,
                                },
                                {
                                    "name": "Discovery Source",
                                    "value": (
                                        f"`place:{place_id} "
                                        f"job:{job_id}`"
                                    ),
                                    "inline": False,
                                },
                            ],
                            "footer": {
                                "text": "RoValra Datacenter Notifier"
                            },
                        }

                        await post_webhook({"embeds": [embed]})

        except Exception as e:
            print(
                f"[ERROR LOG] Datacenter tracker error: "
                f"{type(e).__name__} - {e}"
            )

        await asyncio.sleep(600)


async def monitor_testing_and_staging_servers():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            timeout = aiohttp.ClientTimeout(total=30)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                for place_id in TARGET_PLACE_IDS:
                    servers = await fetch_all_active_servers(
                        place_id,
                        session,
                        max_pages=3,
                    )

                    seen = SEEN_TESTING_SERVERS_BY_PLACE.setdefault(
                        place_id,
                        set(),
                    )

                    for server in servers:
                        job_id = server.get("id")
                        if not job_id or job_id in seen:
                            continue

                        seen.add(job_id)

                        region_info = await resolve_server_ip_and_region(
                            session,
                            place_id,
                            job_id,
                        )

                        if not region_info:
                            continue

                        city = region_info["city"]
                        ip = region_info["ip"]
                        normalized = normalize_city(city)

                        is_brand_new_region = (
                            normalized not in KNOWN_HOST_REGIONS
                        )

                        if is_brand_new_region:
                            _, dcid = register_datacenter(
                                city,
                                ip,
                                source="testing_scan",
                            )
                        else:
                            dcid = make_dcid(city, ip)

                        KNOWN_HOST_REGIONS.add(normalized)

                        ping = server.get("ping", 0)
                        playing = server.get("playing", 0)
                        max_players = server.get("maxPlayers", 0)

                        title = (
                            f"🚨 Brand New Roblox Host Region Discovered "
                            f"({city})!"
                            if is_brand_new_region
                            else "🧪 New Testing / Staging Instance Observed"
                        )

                        embed = {
                            "title": title,
                            "color": (
                                16711680
                                if is_brand_new_region
                                else 15158332
                            ),
                            "fields": [
                                {
                                    "name": "Datacenter ID",
                                    "value": f"`{dcid}`",
                                    "inline": True,
                                },
                                {
                                    "name": "Location",
                                    "value": (
                                        f"{city}, "
                                        f"{region_info['country']}"
                                    ),
                                    "inline": True,
                                },
                                {
                                    "name": "Infrastructure IP",
                                    "value": f"`{ip}`",
                                    "inline": False,
                                },
                                {
                                    "name": "ISP / Host",
                                    "value": region_info["isp"][:1024],
                                    "inline": True,
                                },
                                {
                                    "name": "Player Load",
                                    "value": f"`{playing}/{max_players}`",
                                    "inline": True,
                                },
                                {
                                    "name": "Node Latency",
                                    "value": f"`{ping} ms`",
                                    "inline": True,
                                },
                                {
                                    "name": "Job ID",
                                    "value": f"`{job_id}`",
                                    "inline": False,
                                },
                                {
                                    "name": "Game Page",
                                    "value": (
                                        f"[Open Roblox Game]("
                                        f"{public_game_url(place_id)})"
                                    ),
                                    "inline": False,
                                },
                            ],
                            "footer": {
                                "text": (
                                    "Staging & Testing Server Radar • "
                                    "Real-Time Infrastructure Watch"
                                )
                            },
                        }

                        await post_webhook({"embeds": [embed]})

                    if len(seen) > 3000:
                        SEEN_TESTING_SERVERS_BY_PLACE[place_id] = set(
                            list(seen)[-1500:]
                        )

        except Exception as e:
            print(
                f"[ERROR LOG] Testing server monitor error: "
                f"{type(e).__name__} - {e}"
            )

        await asyncio.sleep(20)


async def monitor_live_game_servers():
    await bot.wait_until_ready()

    try:
        async with aiohttp.ClientSession() as session:
            for place_id in TARGET_PLACE_IDS:
                initial_servers = await fetch_all_active_servers(
                    place_id,
                    session,
                    max_pages=3,
                )

                SEEN_SERVERS_BY_PLACE[place_id] = {
                    server.get("id")
                    for server in initial_servers
                    if server.get("id")
                }

        total = sum(
            len(server_ids)
            for server_ids in SEEN_SERVERS_BY_PLACE.values()
        )
        print(
            f"[HOST SCANNER] Initialized tracking with {total} "
            "active servers across all target places."
        )

    except Exception as e:
        print(f"[HOST SCANNER] Initial scan failed: {e}")

    while not bot.is_closed():
        try:
            timeout = aiohttp.ClientTimeout(total=30)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                for place_id in TARGET_PLACE_IDS:
                    current_servers = await fetch_all_active_servers(
                        place_id,
                        session,
                        max_pages=3,
                    )

                    current_ids = {
                        server.get("id")
                        for server in current_servers
                        if server.get("id")
                    }

                    seen = SEEN_SERVERS_BY_PLACE.setdefault(
                        place_id,
                        set(),
                    )

                    new_servers = [
                        server
                        for server in current_servers
                        if server.get("id") and server.get("id") not in seen
                    ]

                    seen.intersection_update(current_ids)
                    seen.update(current_ids)

                    for server in new_servers:
                        job_id = server["id"]

                        region = await resolve_server_ip_and_region(
                            session,
                            place_id,
                            job_id,
                        )

                        if not region:
                            continue

                        city = region["city"]
                        normalized = normalize_city(city)
                        ip = region["ip"]

                        is_new_region = (
                            normalized not in KNOWN_HOST_REGIONS
                        )

                        if is_new_region:
                            _, dcid = register_datacenter(
                                city,
                                ip,
                                source="live_scan",
                            )
                        else:
                            dcid = make_dcid(city, ip)

                        KNOWN_HOST_REGIONS.add(normalized)

                        embed = {
                            "title": (
                                f"🚨 New Roblox Host Region Discovered "
                                f"({city})!"
                                if is_new_region
                                else "🚨 New Roblox Server Instance Observed"
                            ),
                            "color": 16711680,
                            "fields": [
                                {
                                    "name": "Datacenter ID",
                                    "value": f"`{dcid}`",
                                    "inline": True,
                                },
                                {
                                    "name": "Country",
                                    "value": region["country"],
                                    "inline": True,
                                },
                                {
                                    "name": "City",
                                    "value": region["city"],
                                    "inline": True,
                                },
                                {
                                    "name": "Infrastructure IP",
                                    "value": f"`{ip}`",
                                    "inline": False,
                                },
                                {
                                    "name": "ISP / Host",
                                    "value": region["isp"][:1024],
                                    "inline": True,
                                },
                                {
                                    "name": "Player Load",
                                    "value": (
                                        f"`{server.get('playing', 0)}/"
                                        f"{server.get('maxPlayers', 0)}`"
                                    ),
                                    "inline": True,
                                },
                                {
                                    "name": "Node Ping",
                                    "value": (
                                        f"`{server.get('ping', 0)} ms`"
                                    ),
                                    "inline": True,
                                },
                                {
                                    "name": "Job ID",
                                    "value": f"`{job_id}`",
                                    "inline": False,
                                },
                                {
                                    "name": "Game Page",
                                    "value": (
                                        f"[Open Roblox Game]("
                                        f"{public_game_url(place_id)})"
                                    ),
                                    "inline": False,
                                },
                            ],
                            "footer": {
                                "text": (
                                    "Live Instance Radar • "
                                    "Region Tracking Active"
                                )
                            },
                        }

                        await post_webhook({"embeds": [embed]})

                    if len(seen) > 2500:
                        SEEN_SERVERS_BY_PLACE[place_id] = set(
                            list(seen)[-1250:]
                        )

        except Exception as e:
            print(
                f"[ERROR LOG] Live server tracker error: "
                f"{type(e).__name__} - {e}"
            )

        await asyncio.sleep(45)


# ============================================================
# SOCKET.IO DASHBOARD
# ============================================================

sio = socketio.AsyncServer(
    async_mode="aiohttp",
    cors_allowed_origins="*",
)

sio_aio_app = web.Application()
sio.attach(sio_aio_app)

DASH_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Datacenter Dashboard</title>
<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
<style>
body {
  font-family: Arial, Helvetica, sans-serif;
  background: #0f1720;
  color: #e6eef8;
  padding: 20px;
}
.card {
  background: #111827;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
}
.new {
  border-left: 4px solid #34d399;
  padding-left: 8px;
}
.list {
  max-height: 60vh;
  overflow: auto;
}
.meta {
  color: #9aa8bf;
  font-size: 13px;
}
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
const statusEl = document.getElementById("status");
const eventsEl = document.getElementById("events");
const knownEl = document.getElementById("known");

socket.on("connect", () => {
  statusEl.textContent = "yes";
  socket.emit("request_known_datacenters");
});

socket.on("disconnect", () => {
  statusEl.textContent = "no";
});

socket.on("new_datacenter", (data) => {
  const card = document.createElement("div");
  card.className = "card new";
  card.textContent =
    "New DC: " + data.city + " (" + data.ip + ") | ID: " +
    data.dcid + " | source: " + data.source;
  eventsEl.prepend(card);
});

socket.on("known_datacenters", (list) => {
  knownEl.innerHTML = "";

  list.forEach((d) => {
    const item = document.createElement("div");
    item.className = "card";

    const title = document.createElement("strong");
    title.textContent = d.city;

    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent =
      d.dcid + " • " + (d.ip || "n/a");

    item.appendChild(title);
    item.appendChild(meta);
    knownEl.appendChild(item);
  });
});
</script>
</body>
</html>
"""


async def handle_root(request):
    return web.Response(
        text=DASH_HTML,
        content_type="text/html",
    )


@sio.event
async def connect(sid, environ):
    print(f"[SIO] client connected: {sid}")


@sio.event
async def disconnect(sid):
    print(f"[SIO] client disconnected: {sid}")


@sio.on("request_known_datacenters")
async def handle_request_known(sid, data=None):
    try:
        known = load_known_datacenters()
        geo_cache = load_geo_cache()
        out = []

        for dcid in known:
            node = TRACKED_NODES.get(dcid, {})
            cached = geo_cache.get(dcid, {})

            out.append(
                {
                    "dcid": dcid,
                    "city": node.get(
                        "city",
                        cached.get("city", "Unknown"),
                    ),
                    "ip": node.get(
                        "ip",
                        cached.get("ip"),
                    ),
                }
            )

        await sio.emit(
            "known_datacenters",
            out,
            to=sid,
        )

    except Exception as e:
        print(f"[SIO] Failed sending known list: {e}")


_dashboard_started = False


async def start_dashboard_server():
    global _dashboard_started

    if _dashboard_started:
        return

    _dashboard_started = True

    try:
        sio_aio_app.router.add_get("/", handle_root)

        async def known_json(request):
            known = load_known_datacenters()
            geo_cache = load_geo_cache()
            out = []

            for dcid in known:
                node = TRACKED_NODES.get(dcid, {})
                cached = geo_cache.get(dcid, {})

                out.append(
                    {
                        "dcid": dcid,
                        "city": node.get(
                            "city",
                            cached.get("city", "Unknown"),
                        ),
                        "ip": node.get(
                            "ip",
                            cached.get("ip"),
                        ),
                    }
                )

            return web.json_response(out)

        sio_aio_app.router.add_get(
            "/api/known",
            known_json,
        )

        runner = web.AppRunner(sio_aio_app)
        await runner.setup()

        site = web.TCPSite(
            runner,
            "0.0.0.0",
            SIO_APP_PORT,
        )

        await site.start()

        print(
            f"[SIO] Dashboard started on port {SIO_APP_PORT}"
        )

    except Exception as e:
        _dashboard_started = False
        print(
            f"[SIO] Dashboard failed to start: "
            f"{type(e).__name__} - {e}"
        )


# ============================================================
# BOT
# ============================================================

class UnifiedForensicsBot(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            tree_cls=GuildOnlyCommandTree,
        )

    async def setup_hook(self):
        self.add_view(PersistentVerificationView())

        self.loop.create_task(monitor_live_game_servers())
        self.loop.create_task(monitor_client_versions())
        self.loop.create_task(monitor_testing_and_staging_servers())
        self.loop.create_task(monitor_datacenter_discoveries())
        self.loop.create_task(start_dashboard_server())

        try:
            if DISCORD_GUILD_ID:
                guild_obj = discord.Object(
                    id=int(DISCORD_GUILD_ID)
                )

                self.tree.copy_global_to(
                    guild=guild_obj
                )

                synced = await self.tree.sync(
                    guild=guild_obj
                )

                print(
                    f"[SYNC] Instantly synced {len(synced)} "
                    f"commands to Guild ID: {DISCORD_GUILD_ID}"
                )

            else:
                synced = await self.tree.sync()

                print(
                    f"[SYNC] Synced {len(synced)} commands globally."
                )

            asyncio.create_task(
                log_to_channel(
                    ALL_LOGS_CHANNEL_ID,
                    (
                        "⚙️ Command tree synced successfully "
                        f"({len(synced)} commands registered)."
                    ),
                )
            )

        except Exception as e:
            print(
                "[ERROR LOG] Failed to sync command tree: "
                f"{type(e).__name__} - {e}"
            )

    async def on_ready(self):
        if self.user:
            print(
                f"[INFO] Bot logged in successfully as "
                f"{self.user} (ID: {self.user.id})"
            )

            asyncio.create_task(
                log_to_channel(
                    ALL_LOGS_CHANNEL_ID,
                    f"🟢 **System Online:** Authenticated as `{self.user}`",
                )
            )


bot = UnifiedForensicsBot()


# ============================================================
# GLOBAL COMMAND ERROR HANDLER
# ============================================================

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    if isinstance(error, RequiredRoleError):
        embed = discord.Embed(
            title="🚫 Access Denied",
            description=str(error),
            color=0xED4245,
        )

    elif isinstance(error, app_commands.CheckFailure):
        embed = discord.Embed(
            title="🚫 Permission Error",
            description=(
                "You do not have permission to execute this command."
            ),
            color=0xED4245,
        )

    else:
        print(
            f"[COMMAND ERROR] {type(error).__name__}: {error}"
        )
        traceback.print_exc()

        embed = discord.Embed(
            title="⚠️ Command Error",
            description=(
                "The command failed unexpectedly. "
                "Check the bot console for details."
            ),
            color=0xED4245,
        )

    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
            )
    except Exception as e:
        print(f"[ERROR LOG] Failed sending command error: {e}")


# ============================================================
# /findnewhost
# ============================================================

@bot.tree.command(
    name="findnewhost",
    description=(
        "Scan and locate newly created/testing Roblox servers "
        "and their resolved infrastructure regions."
    ),
)
@app_commands.check(has_bot_access)
async def findnewhost(interaction: discord.Interaction):
    await interaction.response.defer(
        thinking=True,
        ephemeral=True,
    )

    try:
        found_nodes = []

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=45)
        ) as session:

            for place_id in TARGET_PLACE_IDS[:3]:
                servers = await fetch_all_active_servers(
                    place_id,
                    session,
                    max_pages=2,
                )

                for server in servers[:10]:
                    job_id = server.get("id")

                    if not job_id:
                        continue

                    region_info = await resolve_server_ip_and_region(
                        session,
                        place_id,
                        job_id,
                    )

                    if not region_info:
                        continue

                    city = region_info["city"]
                    ip = region_info["ip"]
                    normalized = normalize_city(city)

                    is_new_region = (
                        normalized not in KNOWN_HOST_REGIONS
                    )

                    dcid = make_dcid(city, ip)

                    if is_new_region:
                        _, created_dcid = register_datacenter(
                            city,
                            ip,
                            source="manual_findnewhost",
                        )
                        dcid = created_dcid or dcid

                    found_nodes.append(
                        {
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
                            "is_new_region": is_new_region,
                        }
                    )

        if not found_nodes:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="🔍 Testing Host Radar",
                    description=(
                        "No resolvable testing/staging infrastructure "
                        "was found in this scan cycle."
                    ),
                    color=0xFEE75C,
                ),
                ephemeral=True,
            )
            return

        new_region_exists = any(
            node["is_new_region"]
            for node in found_nodes
        )

        embed = discord.Embed(
            title=(
                "🚨 New Roblox Host Region Observed"
                if new_region_exists
                else "🧪 Testing & Staging Server Nodes"
            ),
            description=(
                "Scan results synchronized with the infrastructure "
                "telemetry feed."
            ),
            color=(
                0xED4245
                if new_region_exists
                else 0x57F287
            ),
            timestamp=datetime.now(timezone.utc),
        )

        for node in found_nodes[:5]:
            field_value = (
                f"• **Datacenter ID:** `{node['dcid']}`\n"
                f"• **Location:** `{node['city']}, "
                f"{node['country']}`\n"
                f"• **Infrastructure IP:** `{node['ip']}`\n"
                f"• **ISP/Host:** `{node['isp']}`\n"
                f"• **Players:** "
                f"`{node['playing']}/{node['max']}`\n"
                f"• **Ping:** `{node['ping']}ms`\n"
                f"• **Job ID:** `{node['job_id']}`\n"
                f"• **Game:** "
                f"[Open Roblox Game]("
                f"{public_game_url(node['place_id'])})"
            )

            if node["is_new_region"]:
                field_value += "\n• **Status:** 🚨 NEW REGION"

            embed.add_field(
                name=f"📍 Node [{node['city']}]",
                value=field_value[:1024],
                inline=False,
            )

        embed.set_footer(
            text="Datacenter Telemetry Subsystem • Testing Node Matrix"
        )

        await post_webhook(
            {"embeds": [embed.to_dict()]}
        )

        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
        )

    except Exception as e:
        print(
            f"[ERROR LOG] /findnewhost failed: "
            f"{type(e).__name__} - {e}"
        )

        await interaction.followup.send(
            embed=discord.Embed(
                title="⚠️ Error",
                description=(
                    f"Failed to scan testing hosts: `{e}`"
                ),
                color=0xED4245,
            ),
            ephemeral=True,
        )


# ============================================================
# /setup-verify and /setupverify
# ============================================================

@bot.tree.command(
    name="setup-verify",
    description="Deploy the persistent account verification panel.",
)
@app_commands.checks.has_permissions(administrator=True)
async def setup_verify(interaction: discord.Interaction):
    await deploy_verify_panel(interaction)


@bot.tree.command(
    name="setupverify",
    description="Deploy the persistent account verification panel.",
)
@app_commands.checks.has_permissions(administrator=True)
async def setupverify(interaction: discord.Interaction):
    await deploy_verify_panel(interaction)


# ============================================================
# /checklocation
# ============================================================

@bot.tree.command(
    name="checklocation",
    description="Show metadata for a tracked Roblox infrastructure node.",
)
@app_commands.describe(node_id="Tracked datacenter/node ID")
@app_commands.check(has_bot_access)
async def checklocation(
    interaction: discord.Interaction,
    node_id: str,
):
    node = TRACKED_NODES.get(node_id.strip())

    if not node:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Node Not Found",
                description=(
                    f"No tracked node exists with ID `{node_id}`."
                ),
                color=0xED4245,
            ),
            ephemeral=True,
        )
        return

    embed = discord.Embed(
        title=f"📍 {node['city']} Infrastructure Node",
        color=0x5865F2,
    )

    embed.add_field(
        name="Node ID",
        value=f"`{node['id']}`",
        inline=True,
    )
    embed.add_field(
        name="City",
        value=node.get("city", "Unknown"),
        inline=True,
    )
    embed.add_field(
        name="Location",
        value=node.get("location", "Unknown"),
        inline=False,
    )
    embed.add_field(
        name="IP",
        value=f"`{node.get('ip', 'Unavailable')}`",
        inline=False,
    )
    embed.add_field(
        name="Status",
        value=node.get("status", "Indexed"),
        inline=True,
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True,
    )


# ============================================================
# /processdc
# ============================================================

@bot.tree.command(
    name="processdc",
    description="Register a datacenter node using supplied public metadata.",
)
@app_commands.describe(
    city="Datacenter city",
    ip="Public infrastructure IP associated with the node",
)
@app_commands.check(has_bot_access)
async def processdc(
    interaction: discord.Interaction,
    city: str,
    ip: str,
):
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Invalid IP",
                description="Please provide a valid IP address.",
                color=0xED4245,
            ),
            ephemeral=True,
        )
        return

    registered, dcid = register_datacenter(
        city.strip(),
        ip.strip(),
        source=f"processdc:{interaction.user.id}",
    )

    if registered:
        title = "📍 Datacenter Registered"
        description = (
            f"Registered **{city}** as `{dcid}`."
        )
        color = 0x57F287
    else:
        title = "ℹ️ Datacenter Already Known"
        description = (
            f"`{dcid}` is already present in the datacenter index."
        )
        color = 0xFEE75C

    await interaction.response.send_message(
        embed=discord.Embed(
            title=title,
            description=description,
            color=color,
        ),
        ephemeral=True,
    )


# ============================================================
# /checkallservers
# ============================================================

@bot.tree.command(
    name="checkallservers",
    description="Show all currently indexed Roblox infrastructure nodes.",
)
@app_commands.check(has_bot_access)
async def checkallservers(interaction: discord.Interaction):
    await interaction.response.defer(
        ephemeral=True,
        thinking=True,
    )

    nodes = list(TRACKED_NODES.values())

    if not nodes:
        await interaction.followup.send(
            "No infrastructure nodes are currently indexed.",
            ephemeral=True,
        )
        return

    embed = discord.Embed(
        title="🌐 Indexed Infrastructure Nodes",
        description=(
            f"Showing `{len(nodes)}` indexed nodes. "
            "Status is indexed metadata unless a live scan reports otherwise."
        ),
        color=0x5865F2,
    )

    lines = []

    for node in nodes[:25]:
        lines.append(
            f"• **{node.get('city', 'Unknown')}** "
            f"`{node.get('id', 'N/A')}` — "
            f"{node.get('status', '📋 Indexed')}"
        )

    embed.description += "\n\n" + "\n".join(lines)

    if len(nodes) > 25:
        embed.set_footer(
            text=f"{len(nodes) - 25} additional nodes omitted from this message."
        )

    await interaction.followup.send(
        embed=embed,
        ephemeral=True,
    )


# ============================================================
# /stats
# ============================================================

@bot.tree.command(
    name="stats",
    description="Show indexed infrastructure statistics.",
)
@app_commands.check(has_bot_access)
async def stats(interaction: discord.Interaction):
    await interaction.response.defer(
        thinking=True,
        ephemeral=False,
    )

    city_counts = {}

    for node in TRACKED_NODES.values():
        city = node.get("city", "Unknown")
        city_counts[city] = city_counts.get(city, 0) + 1

    total_nodes = len(TRACKED_NODES)
    total_regions = len(city_counts)

    embed = discord.Embed(
        title="📊 Infrastructure Statistics",
        description=(
            "Statistics are based on the current indexed node database; "
            "they are not fabricated live server counts."
        ),
        color=0x5865F2,
    )

    embed.add_field(
        name="Indexed Nodes",
        value=f"`{total_nodes}`",
        inline=True,
    )

    embed.add_field(
        name="Unique Cities",
        value=f"`{total_regions}`",
        inline=True,
    )

    region_lines = [
        f"• **{city}:** `{count}`"
        for city, count in sorted(
            city_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]

    embed.add_field(
        name="Nodes by City",
        value="\n".join(region_lines)[:1024] or "None",
        inline=False,
    )

    await interaction.followup.send(embed=embed)


# ============================================================
# /robloxlink
# ============================================================

@bot.tree.command(
    name="robloxlink",
    description="Create a Roblox game page link from a place ID.",
)
@app_commands.describe(place_id="Roblox place ID")
@app_commands.check(has_bot_access)
async def robloxlink(
    interaction: discord.Interaction,
    place_id: int,
):
    if place_id <= 0:
        await interaction.response.send_message(
            "❌ Invalid place ID.",
            ephemeral=True,
        )
        return

    url = public_game_url(place_id)

    embed = discord.Embed(
        title="🔗 Roblox Game Link",
        description=f"[Open Roblox Game]({url})",
        color=0x5865F2,
    )

    embed.add_field(
        name="Place ID",
        value=f"`{place_id}`",
        inline=True,
    )

    embed.set_footer(
        text="Public game page link • not a private-server join code"
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True,
    )


# ============================================================
# /scanlink
# ============================================================

@bot.tree.command(
    name="scanlink",
    description="Perform basic safe URL heuristics.",
)
@app_commands.describe(url="HTTP/HTTPS URL to inspect")
@app_commands.check(has_bot_access)
async def scanlink(
    interaction: discord.Interaction,
    url: str,
):
    parsed = urlparse(url.strip())

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Invalid URL",
                description="Only valid HTTP/HTTPS URLs are supported.",
                color=0xED4245,
            ),
            ephemeral=True,
        )
        return

    hostname = parsed.hostname
    flags = []

    if hostname.startswith("xn--") or ".xn--" in hostname:
        flags.append("Punycode hostname")

    try:
        ipaddress.ip_address(hostname)
        flags.append("Raw IP hostname")
    except ValueError:
        pass

    if "@" in parsed.netloc:
        flags.append("User-info section present")

    if len(hostname.split(".")) >= 5:
        flags.append("Many hostname levels")

    if len(url) > 250:
        flags.append("Unusually long URL")

    result = (
        "No obvious heuristic flags were found."
        if not flags
        else "\n".join(f"• {flag}" for flag in flags)
    )

    embed = discord.Embed(
        title="🔍 URL Heuristic Scan",
        description=result,
        color=0x57F287 if not flags else 0xFEE75C,
    )

    embed.add_field(
        name="Scheme",
        value=f"`{parsed.scheme}`",
        inline=True,
    )

    embed.add_field(
        name="Hostname",
        value=f"`{hostname}`",
        inline=False,
    )

    embed.set_footer(
        text=(
            "Heuristic inspection only. This does not prove a URL is "
            "safe or malicious."
        )
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True,
    )


# ============================================================
# /globalscan
# ============================================================

@bot.tree.command(
    name="globalscan",
    description="Validate an identifier format without claiming external reputation data.",
)
@app_commands.describe(identifier="User or identifier to validate")
@app_commands.check(has_bot_access)
async def globalscan(
    interaction: discord.Interaction,
    identifier: str,
):
    cleaned = identifier.strip()

    snowflake_like = bool(re.fullmatch(r"\d{15,22}", cleaned))

    embed = discord.Embed(
        title="🌐 Global Identifier Scan",
        color=0x5865F2,
    )

    embed.add_field(
        name="Input",
        value=f"`{cleaned[:100]}`",
        inline=False,
    )

    embed.add_field(
        name="Format",
        value=(
            "Discord Snowflake-like"
            if snowflake_like
            else "General text identifier"
        ),
        inline=True,
    )

    embed.add_field(
        name="External Reputation",
        value="Not queried",
        inline=True,
    )

    embed.set_footer(
        text="Format validation only • no claim of account reputation"
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True,
    )


# ============================================================
# /report
# ============================================================

@bot.tree.command(
    name="report",
    description="Submit a report to the configured log channel.",
)
@app_commands.describe(
    target="Reported user/name",
    reason="Reason for the report",
    proof_url="Optional HTTP/HTTPS proof URL",
)
@app_commands.check(has_bot_access)
async def report(
    interaction: discord.Interaction,
    target: str,
    reason: str,
    proof_url: str = "",
):
    proof_url = proof_url.strip()

    if proof_url:
        parsed = urlparse(proof_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            await interaction.response.send_message(
                "❌ Proof URL must be a valid HTTP/HTTPS URL.",
                ephemeral=True,
            )
            return

    embed = discord.Embed(
        title="🚨 New Report",
        color=0xED4245,
        timestamp=datetime.now(timezone.utc),
    )

    embed.add_field(
        name="Reporter",
        value=f"{interaction.user} (`{interaction.user.id}`)",
        inline=False,
    )
    embed.add_field(
        name="Target",
        value=target[:1024],
        inline=False,
    )
    embed.add_field(
        name="Reason",
        value=reason[:1024],
        inline=False,
    )

    if proof_url:
        embed.add_field(
            name="Proof",
            value=f"[Open proof link]({proof_url})",
            inline=False,
        )

    await log_to_channel(
        ALL_LOGS_CHANNEL_ID,
        f"🚨 Report submitted by `{interaction.user}`",
    )

    try:
        channel = await bot.fetch_channel(ALL_LOGS_CHANNEL_ID)
        if isinstance(channel, discord.TextChannel):
            await channel.send(embed=embed)
    except Exception as e:
        print(f"[ERROR LOG] Failed sending report embed: {e}")

    await interaction.response.send_message(
        embed=discord.Embed(
            title="✅ Report Submitted",
            description="Your report was sent to the configured moderation log.",
            color=0x57F287,
        ),
        ephemeral=True,
    )


# ============================================================
# /user
# ============================================================

@bot.tree.command(
    name="user",
    description="Look up detailed public profile info for a Roblox username.",
)
@app_commands.describe(username="Roblox username to search")
@app_commands.check(has_bot_access)
async def roblox_user(
    interaction: discord.Interaction,
    username: str,
):
    await interaction.response.defer(thinking=True, ephemeral=True)
    username = username.strip()

    try:
        async with aiohttp.ClientSession() as session:
            # 1. Get User ID from username
            async with session.post(
                "https://users.roblox.com/v1/usernames/users",
                json={"usernames": [username], "excludeBannedUsers": True}
            ) as resp:
                if resp.status != 200:
                    raise Exception("Failed to contact Roblox Users API.")
                data = await resp.json()
                users = data.get("data", [])
                if not users:
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="❌ User Not Found",
                            description=f"No active Roblox user found with username `{username}`.",
                            color=0xED4245
                        ),
                        ephemeral=True
                    )
                    return
                user_info = users[0]
                user_id = user_info["id"]
                display_name = user_info.get("displayName", username)
                resolved_name = user_info.get("name", username)

            # 2. Get detailed user info
            async with session.get(f"https://users.roblox.com/v1/users/{user_id}") as resp:
                detailed_data = await resp.json() if resp.status == 200 else {}
                description = detailed_data.get("description", "No bio provided.")
                created_at = detailed_data.get("created")
                is_banned = detailed_data.get("isBanned", False)

            # 3. Get Headshot Thumbnail
            async with session.get(
                f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png&isCircular=false"
            ) as resp:
                thumb_data = await resp.json() if resp.status == 200 else {}
                thumbs = thumb_data.get("data", [])
                avatar_url = thumbs[0].get("imageUrl") if thumbs else None

        embed = discord.Embed(
            title=f"👤 Roblox Profile: {resolved_name}",
            url=f"https://www.roblox.com/users/{user_id}/profile",
            color=0xED4245 if is_banned else 0x5865F2,
            timestamp=datetime.now(timezone.utc)
        )
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        embed.add_field(name="Display Name", value=f"`{display_name}`", inline=True)
        embed.add_field(name="User ID", value=f"`{user_id}`", inline=True)
        embed.add_field(name="Status", value="🚫 Banned" if is_banned else "🟢 Active", inline=True)
        
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                embed.add_field(name="Account Created", value=f"<t:{int(dt.timestamp())}:R>", inline=True)
            except Exception:
                pass

        if description:
            clean_desc = description if len(description) <= 300 else description[:297] + "..."
            embed.add_field(name="Bio", value=f"```{clean_desc}
