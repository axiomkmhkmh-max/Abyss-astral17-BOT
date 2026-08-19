# نقشه‌ی راه: پورت Astral Abyss به گپ

## چی الان کار می‌کنه (فاز ۱ — همین تحویل)

| فایل | نقش |
|---|---|
| `gap_client.py` | wrapper خام روی `api.gap.im` (sendMessage, upload, editMessage, invoice, ...) |
| `gap_types.py` | شبیه‌ساز `Message` / `CallbackQuery` / `InlineKeyboardMarkup` به سبک aiogram — تا کدهای منطقی بدون تغییرِ زیاد قابل استفاده باشن |
| `gap_dispatcher.py` | جایگزینِ سبکِ `Dispatcher/Router` تلگرام — روی `type` پیامِ گپ (`text`, `triggerButton`, `join`, ...) دیسپچ می‌کنه |
| `gap_webhook.py` | سرور aiohttp که مسیر `/gap/webhook/<secret>` رو گوش می‌ده |
| `gap_core_handlers.py` | `/start`، گرفتن کاراکتر تصادفی، انتخاب جنسیت، پروفایل، منوی اصلی |
| `gap_admin_panel.py` | `/admin`, `/stats`, `/broadcast`, `/ban`, `/unban`, `/givezen`, `/givexp`, `/info` |
| `bot_dual.py` | نقطه‌ی ورود جدید — تلگرام (polling) و گپ (webhook) رو هم‌زمان تو یه process اجرا می‌کنه |

## چیزی که هنوز پورت نشده

سیستم‌های زیر هنوز فقط رو تلگرام کار می‌کنن: `combat_handlers`, `casino_handlers`, `bank_handlers`,
`guild_handlers`, `shop_handlers`, `pvp_handlers`, `raid_handlers`, `boss_handlers`,
`nemesis_handlers`, `auction_handlers`, `trade_handlers`, `katana_handlers`, `quest_handlers`,
و بقیه‌ی حدوداً ۲۵ فایلِ `*_handlers.py`.

## الگوی پورت هر فایل (قدم‌به‌قدم)

هر `xxx_handlers.py` تلگرامی معمولاً یه تابع `register_xxx_handlers(dp, bot)` داره که چند
`@dp.message(...)` و `@dp.callback_query(...)` رجیستر می‌کنه. برای گپ:

1. **فایل جدید بساز**: `gap_xxx_handlers.py`
2. **منطقِ خالص رو مستقیم import کن** — چیزهایی مثل محاسبه‌ی دمیج، اکونومی، دیتابیس،
   لیدربورد و غیره هیچ وابستگی‌ای به aiogram ندارن (مثل `combat_power.py`, `economy.py`,
   `game_data.py`, `item_system.py`) — اینا رو عیناً import کن، صفر تغییر.
3. **کیبورد/پیام رو بازنویسی کن** — هرجا تابعی مستقیم `InlineKeyboardMarkup`/`ReplyKeyboardMarkup`
   با آرگومان‌های اختصاصیِ فورک تلگرام (`style=ButtonStyle...`) می‌ساخت، با
   `from gap_types import InlineKeyboardMarkup, InlineKeyboardButton, InlineKeyboardBuilder`
   جایگزینش کن (پارامترهای `text=`/`callback_data=` عیناً کار می‌کنه، فقط `style` رو حذف کن).
4. **دکوریتور رو عوض کن**:
   ```python
   # قبل (aiogram):
   @dp.callback_query(F.data.startswith("combat:"))
   async def cb_combat(query: CallbackQuery): ...

   # بعد (گپ):
   @dp.callback_query(data_startswith="combat:")
   async def cb_combat(query: CallbackQuery): ...
   ```
5. **signature تابع دست‌نخورده می‌مونه** چون `gap_types.CallbackQuery`/`Message` همون متدهای
   کلیدی (`.answer()`, `.message.edit_text()`, `.from_user.id`) رو دارن.
6. **در `bot_dual.py` رجیستر کن**:
   ```python
   from gap_combat_handlers import register_gap_combat_handlers
   register_gap_combat_handlers(dp)
   ```

## نکات مهم معماری

- **uid دوگانه**: هر پلیرِ گپ با `uid` منفی (`-chat_id`) تو همون کالکشنِ Mongo ذخیره می‌شه —
  یعنی یک نفر که هم گپ هم تلگرام بازی کنه، دو کاراکترِ جداگونه داره. اگه بعداً خواستی
  اکانت‌ها به هم لینک بشن (یه دستور مثل `/link <کد>`)، بگو تا اون سیستم رو هم اضافه کنم.
- **session token / stale callback**: `action_lock.py` مستقل از aiogramه، عیناً قابل‌استفاده‌ست.
- **محدودیت آپلود گپ**: ۵۰ مگابایت (تعاملی) — پروفایل‌کارت‌ها/پوسترها مشکلی ندارن.
- **پرداخت گپ ≠ Telegram Stars**: `bank_system.py`/`exchange_system.py` منطقشون داخلی و
  زنِ بازیه، به پرداخت واقعی ربطی نداره — قابل‌پورتِ مستقیم. اگه بعداً خواستی خریدِ زن با پول
  واقعی از طریق گپ (invoice API) اضافه بشه، اون یه سیستمِ جدیده، جدا صحبت کنیم.
- **گیم‌سنتر گپ**: یه API لیدربورد/امتیاز داره (`gameData`, `leaderBoard`) که با
  `GapClient.save_game_data` / `.leaderboard` پوشش داده شده — می‌شه لیدربورد PvP یا
  بهترین کیل‌استریک رو با این وایر کرد که هم تو گپ خودش (نه فقط تو ربات) دیده بشه.

## پیشنهاد ترتیب پورت (بر اساس اولویت تعامل)

1. Combat (حمله/parry/break) — قلب تجربه‌ی بازی
2. Shop + Bank — اقتصاد پایه
3. Guild + PvP — تعامل اجتماعی
4. Casino + Auction + Trade
5. بقیه (raid, boss, nemesis, katana, quest, ...)

هر کدوم از این‌ها رو بخوای، به همین ترتیب یا هر ترتیبی که بگی، تو پیام‌های بعدی می‌سازم —
فایل‌به‌فایل، جدا از هم، دقیقاً مثل قبل.

## دیپلوی روی Railway

1. `Procfile` رو به این تغییر بده:
   ```
   web: python bot_dual.py
   ```
   (چون Railway فقط به process از نوع `web` دامنه‌ی عمومی می‌ده — لازم برای این‌که گپ
   بتونه webhook بزنه بهت.)
2. Variables جدید تو Railway اضافه کن:
   - `BOT_TOKEN_GAP` — از پنل my.gap.im
   - `GAP_WEBHOOK_SECRET` — یه رشته‌ی رندوم دلخواه (مثلاً با `openssl rand -hex 16`)
   - `GAP_ADMIN_IDS` — chat_id عددیِ ادمین‌های گپ
3. بعدِ دیپلوی، تو پنل my.gap.im آدرسِ callback رو بذار:
   `https://<اسم-اپ-شما>.up.railway.app/gap/webhook/<GAP_WEBHOOK_SECRET>`
4. تست کن: `/start` رو تو گپ به ربات بزن، باید همون فلوی ساختِ کاراکتر بیاد.
