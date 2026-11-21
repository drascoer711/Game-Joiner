"""Render start entrypoint that reports application boot failures to Discord."""

import traceback

import render_notify


try:
    # Import registers /join-game before the shared bot starts.
    import roblox_bot

    roblox_bot.main.bot.run(roblox_bot.main.TOKEN)
except Exception as error:
    details = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    print(details, flush=True)
    render_notify.notify(
        "Render application startup failed:\n"
        f"{type(error).__name__}: {error}\n\n"
        f"{details[-1100:]}"
    )
    raise
