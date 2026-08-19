# ============================================================
#  ASTRAL ABYSS — Gap Messenger API Client
# ------------------------------------------------------------
#  لایه‌ی خام ارتباط با api.gap.im . هیچ منطق بازی اینجا نیست،
#  فقط wrapper دور متدهای رسمی مستندات گپ (sendMessage, upload,
#  editMessage, deleteMessage, answerCallback, invoice, ...).
#
#  همه‌ی متدها async هستن و از یک aiohttp.ClientSession مشترک
#  استفاده می‌کنن (باید با GapClient.start() ساخته و با
#  GapClient.close() بسته بشه — دقیقاً مثل بستن session ربات
#  تلگرام).
# ============================================================
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import aiohttp

log = logging.getLogger("gap.client")

GAP_API_BASE = "https://api.gap.im"


class GapAPIError(Exception):
    """خطای برگردانده‌شده از سمت سرور گپ (status != 200/2xx)."""

    def __init__(self, status: int, payload: Any):
        self.status = status
        self.payload = payload
        super().__init__(f"Gap API error {status}: {payload}")


class GapClient:
    def __init__(self, token: str, session: Optional[aiohttp.ClientSession] = None):
        if not token:
            raise ValueError("Gap bot token خالیه — BOT_TOKEN_GAP رو ست کن.")
        self.token = token
        self._session = session
        self._owns_session = session is None

    # ─── چرخه‌ی عمر ────────────────────────────────────────
    async def start(self) -> "GapClient":
        if self._session is None:
            self._session = aiohttp.ClientSession(
                headers={"token": self.token},
                timeout=aiohttp.ClientTimeout(total=25),
            )
        return self

    async def close(self):
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def _post(self, path: str, json_body: Optional[dict] = None,
                     data: Optional[aiohttp.FormData] = None) -> dict:
        assert self._session is not None, "GapClient.start() فراخوانی نشده"
        url = f"{GAP_API_BASE}{path}"
        async with self._session.post(url, json=json_body, data=data) as resp:
            text = await resp.text()
            try:
                payload = json.loads(text) if text else {}
            except json.JSONDecodeError:
                payload = {"raw": text}
            if resp.status not in (200, 201):
                log.warning("Gap API %s -> %s: %s", path, resp.status, payload)
                raise GapAPIError(resp.status, payload)
            return payload

    # ─── ارسال پیام ────────────────────────────────────────
    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        inline_keyboard: Optional[list] = None,
        reply_keyboard: Optional[dict] = None,
        form: Optional[list] = None,
    ) -> int:
        body: dict = {"chat_id": chat_id, "type": "text", "data": text}
        if inline_keyboard is not None:
            body["inline_keyboard"] = json.dumps(inline_keyboard, ensure_ascii=False)
        if reply_keyboard is not None:
            body["reply_keyboard"] = json.dumps(reply_keyboard, ensure_ascii=False)
        if form is not None:
            body["form"] = json.dumps(form, ensure_ascii=False)
        result = await self._post("/sendMessage", json_body=body)
        return result.get("id")

    async def send_media(
        self,
        chat_id: int | str,
        media_type: str,  # "image" | "video" | "audio" | "voice" | "file"
        uploaded_data: str,
        *,
        inline_keyboard: Optional[list] = None,
        reply_keyboard: Optional[dict] = None,
    ) -> int:
        body: dict = {"chat_id": chat_id, "type": media_type, "data": uploaded_data}
        if inline_keyboard is not None:
            body["inline_keyboard"] = json.dumps(inline_keyboard, ensure_ascii=False)
        if reply_keyboard is not None:
            body["reply_keyboard"] = json.dumps(reply_keyboard, ensure_ascii=False)
        result = await self._post("/sendMessage", json_body=body)
        return result.get("id")

    async def upload_file(self, chat_id: int | str, field: str, file_path: str,
                           desc: str = "") -> str:
        """
        field باید یکی از: image, video, voice, audio, file باشه.
        خروجی: رشته‌ی encode‌شده‌ای که باید بعداً به send_media بدی.
        """
        assert self._session is not None
        form = aiohttp.FormData()
        form.add_field("chat_id", str(chat_id))
        if desc:
            form.add_field("desc", desc)
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        form.add_field(field, file_bytes, filename=file_path.split("/")[-1])
        url = f"{GAP_API_BASE}/upload"
        async with self._session.post(url, data=form) as resp:
            text = await resp.text()
            payload = json.loads(text) if text else {}
            if resp.status not in (200, 201):
                raise GapAPIError(resp.status, payload)
            # مستندات گپ رشته‌ی encode‌شده رو داخل یکی از این کلیدها برمی‌گردونه
            return payload.get(field) or payload.get("data") or payload

    async def edit_message(self, chat_id: int | str, message_id: int, text: str,
                            *, inline_keyboard: Optional[list] = None) -> None:
        body: dict = {"chat_id": chat_id, "message_id": message_id, "data": text}
        if inline_keyboard is not None:
            body["inline_keyboard"] = json.dumps(inline_keyboard, ensure_ascii=False)
        await self._post("/editMessage", json_body=body)

    async def delete_message(self, chat_id: int | str, message_id: int) -> None:
        await self._post("/deleteMessage", json_body={"chat_id": chat_id, "message_id": message_id})

    async def send_action_typing(self, chat_id: int | str) -> None:
        await self._post("/sendAction", json_body={"chat_id": chat_id, "type": "typing"})

    async def answer_callback(self, chat_id: int, callback_id: str, text: str,
                               show_alert: bool = False) -> None:
        await self._post("/answerCallback", json_body={
            "chat_id": chat_id, "callback_id": callback_id,
            "text": text, "show_alert": show_alert,
        })

    # ─── پرداخت / صورتحساب ─────────────────────────────────
    async def send_invoice(self, chat_id: int, amount: int, description: str,
                            currency: str = "IRR", expire_time: int = 86400) -> str:
        result = await self._post("/invoice", json_body={
            "chat_id": chat_id, "amount": amount, "currency": currency,
            "description": description, "expire_time": expire_time,
        })
        return result.get("id")

    async def verify_invoice(self, chat_id: int, ref_id: str) -> dict:
        return await self._post("/invoice/verify", json_body={"chat_id": chat_id, "ref_id": ref_id})

    async def inquiry_invoice(self, chat_id: int, ref_id: str) -> dict:
        return await self._post("/invoice/inquiry", json_body={"chat_id": chat_id, "ref_id": ref_id})

    async def verify_payment(self, chat_id: int, ref_id: str) -> dict:
        return await self._post("/payment/verify", json_body={"chat_id": chat_id, "ref_id": ref_id})

    async def inquiry_payment(self, chat_id: int, ref_id: str) -> dict:
        return await self._post("/payment/inquiry", json_body={"chat_id": chat_id, "ref_id": ref_id})

    # ─── گیم‌سنتر (اختیاری - جدول امتیازات) ────────────────
    async def save_game_data(self, chat_id: int, type_: str, data: Any, force: bool = False) -> None:
        await self._post("/gameData", json_body={
            "chat_id": chat_id, "type": type_,
            "data": data if isinstance(data, str) else json.dumps(data, ensure_ascii=False),
            "force": force,
        })

    async def get_game_data(self, chat_id: int, type_: str) -> dict:
        return await self._post("/getGameData", json_body={"chat_id": chat_id, "type": type_})

    async def leaderboard(self, chat_id: int, time: str = "all") -> list:
        return await self._post("/leaderBoard", json_body={"chat_id": chat_id, "time": time})
