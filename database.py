import aiosqlite
import os

# Hosted (Render) par DATA_DIR env set hota hai (persistent disk);
# local PC par ye normal bot_data.db hi rehta hai.
DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(__file__))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "bot_data.db")

# Startup par saaf dikhe ki data kahan save ho raha hai (Railway logs me check karna easy)
if os.getenv("DATA_DIR"):
    print(f"Persistent storage ON: {DB_PATH}")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id INTEGER PRIMARY KEY,
                prefix TEXT NOT NULL DEFAULT '!'
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                coins INTEGER DEFAULT 1000,
                agreed BOOLEAN DEFAULT FALSE
            )
        ''')
        
        try:
            await db.execute('ALTER TABLE users ADD COLUMN last_daily REAL DEFAULT 0')
        except Exception:
            pass

        try:
            await db.execute('ALTER TABLE users ADD COLUMN video_count INTEGER DEFAULT 0')
        except Exception:
            pass

        try:
            await db.execute('ALTER TABLE users ADD COLUMN video_window REAL DEFAULT 0')
        except Exception:
            pass

        try:
            await db.execute('ALTER TABLE users ADD COLUMN video_unlimited INTEGER DEFAULT 0')
        except Exception:
            pass

        try:
            await db.execute('ALTER TABLE users ADD COLUMN banned INTEGER DEFAULT 0')
        except Exception:
            pass

        try:
            await db.execute("ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'en'")
        except Exception:
            pass

        try:
            await db.execute('ALTER TABLE users ADD COLUMN luck REAL DEFAULT 0')
        except Exception:
            pass

        try:
            await db.execute('ALTER TABLE users ADD COLUMN last_luck_free REAL DEFAULT 0')
        except Exception:
            pass

        try:
            await db.execute('ALTER TABLE users ADD COLUMN xp INTEGER DEFAULT 0')
        except Exception:
            pass

        try:
            await db.execute('ALTER TABLE users ADD COLUMN daily_streak INTEGER DEFAULT 0')
        except Exception:
            pass

        try:
            await db.execute('ALTER TABLE users ADD COLUMN last_daily_day TEXT')
        except Exception:
            pass

        try:
            await db.execute('ALTER TABLE users ADD COLUMN banner_id INTEGER')
        except Exception:
            pass

        try:
            await db.execute("ALTER TABLE users ADD COLUMN about_me TEXT DEFAULT ''")
        except Exception:
            pass

        try:
            await db.execute('ALTER TABLE users ADD COLUMN created_at REAL')
        except Exception:
            pass

        await db.execute('''
            CREATE TABLE IF NOT EXISTS prayers (
                pray_from INTEGER NOT NULL,
                pray_to   INTEGER NOT NULL,
                day       TEXT NOT NULL,
                PRIMARY KEY (pray_from, pray_to, day)
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS afk (
                user_id INTEGER PRIMARY KEY,
                reason  TEXT NOT NULL,
                since   REAL NOT NULL
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS banners (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT NOT NULL,
                price     INTEGER NOT NULL,
                gradient  TEXT,
                file_path TEXT
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_banners (
                user_id   INTEGER NOT NULL,
                banner_id INTEGER NOT NULL,
                PRIMARY KEY (user_id, banner_id)
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS voice_channels (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS disabled_channels (
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, channel_id)
            )
        ''')
            
        await db.commit()

async def get_prefix(guild_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT prefix FROM guilds WHERE guild_id = ?', (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else "!"

async def set_prefix(guild_id: int, prefix: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO guilds (guild_id, prefix) 
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET prefix = excluded.prefix
        ''', (guild_id, prefix))
        await db.commit()

async def set_voice_channel(guild_id: int, channel_id: int):
    """Remember the voice channel the bot should stay in (24/7 mode)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO voice_channels (guild_id, channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
        ''', (guild_id, channel_id))
        await db.commit()

async def clear_voice_channel(guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM voice_channels WHERE guild_id = ?', (guild_id,))
        await db.commit()

async def get_voice_channel(guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT channel_id FROM voice_channels WHERE guild_id = ?', (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def get_all_voice_channels():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT guild_id, channel_id FROM voice_channels') as cursor:
            return await cursor.fetchall()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT coins, agreed, last_daily, luck, last_luck_free, xp, daily_streak, last_daily_day, banner_id, about_me, created_at FROM users WHERE user_id = ?',
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "coins": row[0],
                    "agreed": bool(row[1]),
                    "last_daily": row[2] or 0,
                    "luck": row[3] or 0,
                    "last_luck_free": row[4] or 0,
                    "xp": row[5] or 0,
                    "daily_streak": row[6] or 0,
                    "last_daily_day": row[7],
                    "banner_id": row[8],
                    "about_me": row[9] or "",
                    "created_at": row[10],
                }
            return None

async def create_user(user_id: int, coins: int = 1000):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO users (user_id, coins, agreed, last_daily) 
            VALUES (?, ?, TRUE, 0)
            ON CONFLICT(user_id) DO UPDATE SET agreed = TRUE
        ''', (user_id, coins))
        await db.commit()

async def update_coins(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            UPDATE users SET coins = coins + ? WHERE user_id = ?
        ''', (amount, user_id))
        await db.commit()

async def transfer_coins(from_user_id: int, to_user_id: int, amount: int) -> bool:
    """Move coins between two players in one transaction.

    The balance is checked inside the same UPDATE that takes the coins, so two
    approvals landing at once can never push a player below zero. Returns False
    when the sender cannot afford it.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT 1 FROM users WHERE user_id = ?', (to_user_id,)) as cursor:
            if await cursor.fetchone() is None:
                return False

        cursor = await db.execute('''
            UPDATE users SET coins = coins - ? WHERE user_id = ? AND coins >= ?
        ''', (amount, from_user_id, amount))
        if cursor.rowcount == 0:
            await db.rollback()
            return False

        await db.execute('''
            UPDATE users SET coins = coins + ? WHERE user_id = ?
        ''', (amount, to_user_id))
        await db.commit()
        return True

async def update_daily_time(user_id: int, timestamp: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            UPDATE users SET last_daily = ? WHERE user_id = ?
        ''', (timestamp, user_id))
        await db.commit()

async def get_video_usage(user_id: int):
    """Return (video_count, video_window_start) for the sendvdo limit."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT video_count, video_window FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return (row[0] or 0), (row[1] or 0)
            return (0, 0)

async def set_video_usage(user_id: int, count: int, window_start: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            UPDATE users SET video_count = ?, video_window = ? WHERE user_id = ?
        ''', (count, window_start, user_id))
        await db.commit()

async def has_video_unlimited(user_id: int) -> bool:
    """True when the user has unlimited sendvdo access (Beast Mode)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT video_unlimited FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return bool(row and row[0])

async def set_video_unlimited(user_id: int, value: bool):
    """Grant/revoke unlimited sendvdo access. Creates the user if needed."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO users (user_id, coins, agreed, video_unlimited)
            VALUES (?, 1000, TRUE, ?)
            ON CONFLICT(user_id) DO UPDATE SET video_unlimited = excluded.video_unlimited
        ''', (user_id, int(value)))
        await db.commit()

async def is_banned(user_id: int) -> bool:
    """True jab user bot se ban ho (Beast Mode se ban kiya gaya)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT banned FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return bool(row and row[0])

async def set_banned(user_id: int, value: bool):
    """Ban/unban karo. User exist na kare to bana do (default 1000 coins)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO users (user_id, coins, agreed, banned)
            VALUES (?, 1000, TRUE, ?)
            ON CONFLICT(user_id) DO UPDATE SET banned = excluded.banned
        ''', (user_id, int(value)))
        await db.commit()

async def reset_coins(user_id: int) -> int:
    """Balance default 1000 par wapas. User exist na kare to banata hai. Naya balance return."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO users (user_id, coins, agreed)
            VALUES (?, 1000, TRUE)
            ON CONFLICT(user_id) DO UPDATE SET coins = 1000
        ''', (user_id,))
        await db.commit()
        return 1000

async def is_channel_disabled(guild_id: int, channel_id: int) -> bool:
    """Channel ya pura server (channel_id=0) disabled hai?"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT 1 FROM disabled_channels WHERE guild_id = ? AND channel_id IN (?, 0)',
            (guild_id, channel_id),
        ) as cursor:
            return await cursor.fetchone() is not None

async def set_channel_disabled(guild_id: int, channel_id: int, disabled: bool):
    """Channel disable/enable karo. channel_id=0 = pura server."""
    async with aiosqlite.connect(DB_PATH) as db:
        if disabled:
            await db.execute(
                'INSERT OR IGNORE INTO disabled_channels (guild_id, channel_id) VALUES (?, ?)',
                (guild_id, channel_id),
            )
        else:
            await db.execute(
                'DELETE FROM disabled_channels WHERE guild_id = ? AND channel_id = ?',
                (guild_id, channel_id),
            )
        await db.commit()

async def clear_all_disabled(guild_id: int):
    """Server ke saare disable hatayo (channel-wise + server-wide)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM disabled_channels WHERE guild_id = ?', (guild_id,))
        await db.commit()

async def get_luck(user_id: int) -> float:
    """User ka luck percentage (0-100). Bina account ke 0."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT luck FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return (row[0] if row and row[0] else 0) or 0

async def set_luck(user_id: int, value: float):
    """Luck set karo (0-100 range clamp). User exist na kare to bana do."""
    value = max(0.0, min(100.0, value))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO users (user_id, coins, agreed, luck)
            VALUES (?, 1000, TRUE, ?)
            ON CONFLICT(user_id) DO UPDATE SET luck = ?
        ''', (user_id, value, value))
        await db.commit()

async def add_luck(user_id: int, amount: float) -> float:
    """Luck add (positive ya negative), clamp 0-100. Naya luck return karo."""
    current = await get_luck(user_id)
    new_value = max(0.0, min(100.0, current + amount))
    await set_luck(user_id, new_value)
    return new_value


# Ek game start hote waqt itna luck use hota hai (100% luck = ~3 games)
LUCK_PER_GAME = 35.0

async def consume_luck(user_id: int) -> float:
    """Game start par luck ka min(luck, 35)% use karo. Bacha hua luck return."""
    luck = await get_luck(user_id)
    if luck <= 0:
        return 0.0
    return await add_luck(user_id, -min(luck, LUCK_PER_GAME))

def luck_shift(luck: float) -> float:
    """Luck ko -0.35..+0.35 factor me convert karo (games random rolls me mix karte hain)."""
    return max(-0.35, min(0.35, luck / 100.0))

async def get_luck_free_time(user_id: int) -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT last_luck_free FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return (row[0] if row else 0) or 0

async def set_luck_free_time(user_id: int, timestamp: float):
    """Daily free-luck claim time save karo (user banao agar nahi hai)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO users (user_id, coins, agreed, last_luck_free)
            VALUES (?, 1000, TRUE, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_luck_free = excluded.last_luck_free
        ''', (user_id, timestamp))
        await db.commit()

async def pray_count_today(pray_from: int, pray_to: int, day: str) -> int:
    """Aaj is user ne kitni baar target ko pray kiya (0 ya 1)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT 1 FROM prayers WHERE pray_from = ? AND pray_to = ? AND day = ?',
            (pray_from, pray_to, day),
        ) as cursor:
            return 1 if await cursor.fetchone() else 0

async def save_prayer(pray_from: int, pray_to: int, day: str):
    """Prayer record karo (per-day unique - duplicate silently ignore)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT OR IGNORE INTO prayers (pray_from, pray_to, day) VALUES (?, ?, ?)',
            (pray_from, pray_to, day),
        )
        await db.commit()

async def cleanup_old_prayers(days_to_keep: int = 2):
    """Purane prayer records delete (table chhoti rahe). day format: YYYY-MM-DD."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM prayers WHERE day < date('now', ?)",
            (f'-{days_to_keep} days',),
        )
        await db.commit()

# ------------------- XP / Level / Streak / Profile -------------------

def xp_for_level(level: int) -> int:
    """Level `level` tak pahunchne ke liye total XP (100*n^2 curve)."""
    return 100 * level * level

def level_from_xp(xp: int) -> int:
    """Current level nikalo: sabse bada n jiske liye xp >= 100*n^2."""
    level = 0
    while xp_for_level(level + 1) <= xp:
        level += 1
        if level > 1000:  # safety
            break
    return level

async def add_xp(user_id: int, amount: int):
    """XP add karo (user exist na kare to ignore - games me already created hota hai)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET xp = xp + ? WHERE user_id = ?', (amount, user_id))
        await db.commit()

async def get_xp(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT xp FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return (row[0] if row else 0) or 0

async def get_rank(user_id: int) -> int:
    """XP leaderboard me ye user ka position (1 = sabse zyada XP)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT 1 + COUNT(*) FROM users WHERE xp > (SELECT COALESCE(MAX(xp), 0) FROM users WHERE user_id = ?)',
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 1

async def get_daily_streak(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT daily_streak FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return (row[0] if row else 0) or 0

async def set_daily_streak(user_id: int, streak: int, day: str):
    """Streak + aaj ka day save karo (user banao agar nahi hai)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO users (user_id, coins, agreed, daily_streak, last_daily_day)
            VALUES (?, 1000, TRUE, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET daily_streak = ?, last_daily_day = ?
        ''', (user_id, streak, day, streak, day))
        await db.commit()

async def get_last_daily_day(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT last_daily_day FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row and row[0] else None

async def set_about_me(user_id: int, text: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO users (user_id, coins, agreed, about_me)
            VALUES (?, 1000, TRUE, ?)
            ON CONFLICT(user_id) DO UPDATE SET about_me = ?
        ''', (user_id, text, text))
        await db.commit()

async def get_created_at(user_id: int) -> float:
    """Account kab bana (unix ts). Naye users ke liye abhi ka time."""
    import time as _time
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            async with db.execute('SELECT created_at FROM users WHERE user_id = ?', (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    return row[0]
        except Exception:
            pass
    return _time.time()

# ------------------- AFK -------------------

async def set_afk(user_id: int, reason: str, since: float):
    """User ko AFK mark karo (reason + timestamp)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT INTO afk (user_id, reason, since) VALUES (?, ?, ?) '
            'ON CONFLICT(user_id) DO UPDATE SET reason = ?, since = ?',
            (user_id, reason, since, reason, since),
        )
        await db.commit()

async def get_afk(user_id: int):
    """(reason, since) ya None."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT reason, since FROM afk WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return (row[0], row[1]) if row else None

async def clear_afk(user_id: int) -> bool:
    """AFK hatao. True agar AFK tha."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('DELETE FROM afk WHERE user_id = ?', (user_id,))
        await db.commit()
        return cursor.rowcount > 0

# ------------------- Banner store -------------------

async def add_banner(name: str, price: int, gradient: str = None, file_path: str = None) -> int:
    """Naya banner catalog me daalo, banner_id return karo.

    gradient = 'c1|c2|c3' hex colors (procedural), ya file_path = custom image.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'INSERT INTO banners (name, price, gradient, file_path) VALUES (?, ?, ?, ?)',
            (name, price, gradient, file_path),
        )
        await db.commit()
        return cursor.lastrowid

async def get_banner(banner_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT id, name, price, gradient, file_path FROM banners WHERE id = ?', (banner_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "name": row[1], "price": row[2], "gradient": row[3], "file_path": row[4]}
            return None

async def get_all_banners():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT id, name, price, gradient, file_path FROM banners ORDER BY price') as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "name": r[1], "price": r[2], "gradient": r[3], "file_path": r[4]} for r in rows]

async def remove_banner(banner_id: int) -> bool:
    """Catalog se banner hatao (custom banners ke liye)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('DELETE FROM banners WHERE id = ?', (banner_id,))
        await db.execute('DELETE FROM user_banners WHERE banner_id = ?', (banner_id,))
        await db.execute('UPDATE users SET banner_id = NULL WHERE banner_id = ?', (banner_id,))
        await db.commit()
        return cursor.rowcount > 0

async def get_equipped_banner(user_id: int):
    """User ka equipped banner ya None."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT banner_id FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return await get_banner(row[0])
    return None

async def equip_banner(user_id: int, banner_id: int) -> bool:
    """Banner equip karo - sirf owned. True = success."""
    if not await owns_banner(user_id, banner_id):
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET banner_id = ? WHERE user_id = ?', (banner_id, user_id))
        await db.commit()
    return True

async def owns_banner(user_id: int, banner_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT 1 FROM user_banners WHERE user_id = ? AND banner_id = ?',
            (user_id, banner_id),
        ) as cursor:
            return await cursor.fetchone() is not None

async def buy_banner(user_id: int, banner_id: int, price: int) -> str:
    """Banner kharido (coins kat ke). Returns: 'ok' | 'poor' | 'owned' | 'no_banner'.

    Coins check aur deduction ek hi atomic UPDATE me - race-safe (transfer_coins pattern).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT 1 FROM banners WHERE id = ?', (banner_id,)) as cursor:
            if await cursor.fetchone() is None:
                return "no_banner"
        async with db.execute('SELECT 1 FROM user_banners WHERE user_id = ? AND banner_id = ?', (user_id, banner_id)) as cursor:
            if await cursor.fetchone() is not None:
                return "owned"

        cursor = await db.execute(
            'UPDATE users SET coins = coins - ? WHERE user_id = ? AND coins >= ?',
            (price, user_id, price),
        )
        if cursor.rowcount == 0:
            await db.rollback()
            return "poor"

        await db.execute('INSERT OR IGNORE INTO user_banners (user_id, banner_id) VALUES (?, ?)', (user_id, banner_id))
        await db.commit()
        return "ok"

async def get_owned_banners(user_id: int):
    """User ke saare owned banners (catalog rows)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT b.id, b.name, b.price, b.gradient, b.file_path
            FROM user_banners ub JOIN banners b ON b.id = ub.banner_id
            WHERE ub.user_id = ? ORDER BY b.price
        ''', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "name": r[1], "price": r[2], "gradient": r[3], "file_path": r[4]} for r in rows]

async def get_lang(user_id: int) -> str:
    """User ki chosen language (default 'en')."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            async with db.execute('SELECT lang FROM users WHERE user_id = ?', (user_id,)) as cursor:
                row = await cursor.fetchone()
                return (row[0] if row and row[0] else "en")
        except Exception:
            return "en"

async def set_lang(user_id: int, lang: str):
    """Language save karo. User exist na kare to bana do (default 1000 coins, agreed)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO users (user_id, coins, agreed, lang)
            VALUES (?, 1000, TRUE, ?)
            ON CONFLICT(user_id) DO UPDATE SET lang = excluded.lang
        ''', (user_id, lang))
        await db.commit()

async def give_coins(user_id: int, amount: int) -> int:
    """Owner ke Beast Mode se coins add/subtract karo, naya balance return karo.

    Creates the user if needed. Balance kabhi negative nahi hota - jyada
    wapas letne par 0 par settle ho jata hai.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO users (user_id, coins, agreed)
            VALUES (?, MAX(1000 + ?, 0), TRUE)
            ON CONFLICT(user_id) DO UPDATE SET coins = MAX(coins + ?, 0)
        ''', (user_id, amount, amount))
        await db.commit()

        async with db.execute('SELECT coins FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0
