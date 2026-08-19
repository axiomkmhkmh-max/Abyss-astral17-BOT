# ============================================================
#  ASTRAL ABYSS — Gap Webhook Server
# ------------------------------------------------------------
#  اینجا همون aiohttp.web.Application‌ای‌ه که Railway بهش پورت
#  عمومی می‌ده. مسیرِ callback‌ای که موقعِ ساختِ ربات تو پنلِ
#  my.gap.im وارد می‌کنی باید دقیقاً این باشه:
#     https://<دامنه‌ی-railway-شما>/gap/webhook
#
#  گپ برای هر پیام یه POST با یه هدرِ اختیاری میفرسته؛ خودِ گپ
#  چیزی رو برای امضاء دیجیتال مستند نکرده، پس برای امنیت یه
#  توکنِ مخفی رو تو خودِ مسیر می‌ذاریم (نه فقط /gap/webhook) تا
#  کسی نتونه payload جعلی بفرسته:
#     /gap/webhook/<GAP_WEBHOOK_SECRET>
# ============================================================
from __future__ import annotations

import logging
import os

from aiohttp import web

log = logging.getLogger("gap.webhook")

GAP_WEBHOOK_SECRET = os.getenv("GAP_WEBHOOK_SECRET", "change-me")


def build_gap_app(dispatcher) -> web.Application:
    app = web.Application()

    async def handle_webhook(request: web.Request):
        secret = request.match_info.get("secret")
        if secret != GAP_WEBHOOK_SECRET:
            return web.json_response({"error": "forbidden"}, status=403)
        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "bad json"}, status=400)
        # پاسخ فوری بده، پردازش رو async انجام بده — گپ منتظرِ ۲۰۰ سریع می‌مونه
        await dispatcher.feed_update(payload)
        return web.json_response({"ok": True})

    async def health(request: web.Request):
        return web.json_response({"status": "ok", "service": "astral-abyss-gap"})

    app.router.add_post("/gap/webhook/{secret}", handle_webhook)
    app.router.add_get("/health", health)
    return app


async def run_gap_webhook(dispatcher, port: int):
    app = build_gap_app(dispatcher)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    log.info("🟣 Gap webhook روی پورت %s بالا اومد (/gap/webhook/%s)", port, GAP_WEBHOOK_SECRET)
    return runner
