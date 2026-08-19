# 🌑 ASTRAL ABYSS RPG BOT

ربات MMO RPG تلگرامی با اقتصاد، باس جهانی، مپ، بازار سیاه، و داستان زنده.

---

## 📁 ساختار فایل‌ها

```
astral_abyss_bot/
├── bot.py           ← فایل اصلی ربات
├── characters.py    ← تمام 90 کاراکتر
├── game_data.py     ← مپ‌ها، آیتم‌ها، لور
├── database.py      ← ذخیره‌سازی JSON
├── requirements.txt ← کتابخانه‌ها
├── Procfile         ← برای Railway
└── data/            ← ساخته می‌شه خودکار
    ├── players.json
    └── boss.json
```

---

## 🚀 Deploy روی Railway (از موبایل)

### ۱. آپلود کد به GitHub
1. برو به [github.com](https://github.com)
2. **New Repository** بساز (نام: `astral-abyss-bot`)
3. روی **uploading an existing file** کلیک کن
4. **همه فایل‌ها** رو آپلود کن
5. **Commit** کن

### ۲. Deploy روی Railway
1. برو به [railway.app](https://railway.app)
2. **Sign in with GitHub** کن
3. **New Project** → **Deploy from GitHub repo**
4. ریپوزیتوری `astral-abyss-bot` رو انتخاب کن
5. بعد از deploy، برو به **Variables** و اضافه کن:
   ```
   BOT_TOKEN = توکن_ربانت_از_BotFather
   ```
6. **Redeploy** کن

✅ ربات آنلاین میشه!

---

## ⚙️ دستورات

### کاربران
| دستور | توضیح |
|-------|-------|
| `/start` | شروع بازی + کاراکتر رندوم |
| `/create نام` | تغییر نام |
| `/status` | وضعیت کامل |
| `/attack` | حمله (cooldown 10 ثانیه) |
| `/move` | رفتن به مپ رندوم |
| `/boss` | وضعیت باس جهانی |
| `/bosshit` | ضربه به باس |
| `/pvp` | مبارزه با بازیکن رندوم |
| `/top` | رده‌بندی |
| `/inventory` | کوله‌پشتی |
| `/market` | بازار سیاه (فقط در Abyss Market) |

### ادمین (@hoseinst)
| دستور | توضیح |
|-------|-------|
| `/givechar user_id CharacterName` | دادن کاراکتر ویژه |
| `/givezen user_id amount` | دادن Zen |
| `/spawnboss` | فراخوانی باس جهانی |
| `/killboss` | ریست باس |

---

## 🎴 سیستم کاراکترها

- **15 کاراکتر ویژه** → فقط ادمین می‌تونه بده (`/givechar`)
- **75 کاراکتر رندوم** → به صورت رندوم با `/start`
- ندرت‌ها: ⚔️ عادی | 💠 نادر | 🌟 افسانه‌ای | 👑 ویژه

---

## 💡 نکات مهم

- توکن رو **هرگز** در کد ننویس، فقط در Railway Variables
- فایل `data/` اطلاعات بازیکنان رو نگه می‌داره
- Combo با حرکت بین مپ‌ها ریست میشه
- بازار سیاه فقط در مپ **Abyss Market** کار می‌کنه
