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

        try:
            await db.execute("ALTER TABLE users ADD COLUMN games_7d TEXT DEFAULT '[]'")
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
                file_path TEXT,
                url       TEXT
            )
        ''')

        try:
            await db.execute('ALTER TABLE banners ADD COLUMN url TEXT')
        except Exception:
            pass

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

        await db.execute('''
            CREATE TABLE IF NOT EXISTS animals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id    INTEGER NOT NULL,
                species_id  TEXT NOT NULL,
                nickname    TEXT,
                level       INTEGER DEFAULT 1,
                xp          INTEGER DEFAULT 0,
                wins        INTEGER DEFAULT 0,
                losses      INTEGER DEFAULT 0,
                hunger      INTEGER DEFAULT 5,
                abilities   TEXT DEFAULT '[]',
                obtained    TEXT DEFAULT 'store',
                created_at  REAL
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS animal_species (
                id       TEXT PRIMARY KEY,
                name     TEXT NOT NULL,
                emoji    TEXT NOT NULL,
                rarity   TEXT NOT NULL,
                hp       INTEGER NOT NULL,
                atk      INTEGER NOT NULL,
                def      INTEGER NOT NULL,
                price    INTEGER DEFAULT 0,
                in_store INTEGER DEFAULT 0,
                image_url TEXT
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                user_id   INTEGER NOT NULL,
                item_type TEXT NOT NULL,
                item_id   TEXT NOT NULL,
                qty       INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, item_type, item_id)
            )
        ''')

        try:
            await db.execute('ALTER TABLE animals ADD COLUMN hunger INTEGER DEFAULT 5')
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE animals ADD COLUMN abilities TEXT DEFAULT '[]'")
        except Exception:
            pass
        try:
            await db.execute('ALTER TABLE users ADD COLUMN active_animal INTEGER')
        except Exception:
            pass
        try:
            await db.execute('ALTER TABLE users ADD COLUMN last_hunt REAL DEFAULT 0')
        except Exception:
            pass

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

async def add_xp_with_levelup(user_id: int, amount: int):
    """XP add karo aur level-up detect karo.

    Returns: (old_level, new_level) - same hone par (n, n).
    """
    old_xp = await get_xp(user_id)
    old_level = level_from_xp(old_xp)
    await add_xp(user_id, amount)
    new_level = level_from_xp(old_xp + amount)
    return (old_level, new_level)

async def get_xp(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT xp FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return (row[0] if row else 0) or 0

async def get_rank(user_id: int) -> int:
    """Coins leaderboard me ye user ka position (1 = sabse zyada coins)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT 1 + COUNT(*) FROM users WHERE coins > (SELECT COALESCE(MAX(coins), 0) FROM users WHERE user_id = ?)',
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 1

async def record_game(user_id: int):
    """Game start record karo (last 7 days rolling window - JSON timestamp list)."""
    import time as _time
    import json as _json
    now = _time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT games_7d FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
        try:
            stamps = _json.loads(row[0]) if row and row[0] else []
        except Exception:
            stamps = []
        cutoff = now - 7 * 86400
        stamps = [s for s in stamps if isinstance(s, (int, float)) and s >= cutoff]
        stamps.append(now)
        await db.execute('UPDATE users SET games_7d = ? WHERE user_id = ?', (_json.dumps(stamps), user_id))
        await db.commit()

async def get_games_7d(user_id: int) -> int:
    """Ye user ne pichhle 7 din me kitne games khelo."""
    import time as _time
    import json as _json
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT games_7d FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
    try:
        stamps = _json.loads(row[0]) if row and row[0] else []
    except Exception:
        return 0
    cutoff = _time.time() - 7 * 86400
    return sum(1 for s in stamps if isinstance(s, (int, float)) and s >= cutoff)

async def get_all_games_7d() -> dict:
    """Sab users ka {user_id: games_played_last_7_days} map."""
    import time as _time
    import json as _json
    cutoff = _time.time() - 7 * 86400
    out = {}
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id, games_7d FROM users WHERE games_7d IS NOT NULL') as cursor:
            async for uid, raw in cursor:
                try:
                    stamps = _json.loads(raw)
                except Exception:
                    continue
                n = sum(1 for s in stamps if isinstance(s, (int, float)) and s >= cutoff)
                if n:
                    out[uid] = n
    return out

async def get_top_coins(limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id, coins FROM users WHERE coins > 0 ORDER BY coins DESC LIMIT ?', (limit,)) as cursor:
            return [(r[0], r[1]) for r in await cursor.fetchall()]

async def get_top_xp(limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id, xp FROM users WHERE xp > 0 ORDER BY xp DESC LIMIT ?', (limit,)) as cursor:
            return [(r[0], r[1]) for r in await cursor.fetchall()]

async def get_top_streaks(limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id, daily_streak FROM users WHERE daily_streak > 0 ORDER BY daily_streak DESC LIMIT ?', (limit,)) as cursor:
            return [(r[0], r[1]) for r in await cursor.fetchall()]

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

async def add_banner(name: str, price: int, gradient: str = None, file_path: str = None, url: str = None) -> int:
    """Naya banner catalog me daalo, banner_id return karo.

    gradient = 'c1|c2|c3' hex colors (procedural), file_path = local image,
    url = direct image link (shop preview + card render ke liye).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'INSERT INTO banners (name, price, gradient, file_path, url) VALUES (?, ?, ?, ?, ?)',
            (name, price, gradient, file_path, url),
        )
        await db.commit()
        return cursor.lastrowid

async def get_banner(banner_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT id, name, price, gradient, file_path, url FROM banners WHERE id = ?', (banner_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "name": row[1], "price": row[2], "gradient": row[3], "file_path": row[4], "url": row[5]}
            return None

async def get_all_banners():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT id, name, price, gradient, file_path, url FROM banners ORDER BY price') as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "name": r[1], "price": r[2], "gradient": r[3], "file_path": r[4], "url": r[5]} for r in rows]

# ------------------- Animals (collect & fight) -------------------

async def upsert_species(species: dict):
    """Species define/replace karo (id unique)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT INTO animal_species (id, name, emoji, rarity, hp, atk, def, price, in_store, image_url) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) '
            'ON CONFLICT(id) DO UPDATE SET name = excluded.name, emoji = excluded.emoji, '
            'rarity = excluded.rarity, hp = excluded.hp, atk = excluded.atk, def = excluded.def, '
            'price = excluded.price, in_store = excluded.in_store, image_url = excluded.image_url',
            (species["id"], species["name"], species["emoji"], species["rarity"],
             species["hp"], species["atk"], species["def"],
             species.get("price", 0), 1 if species.get("in_store") else 0,
             species.get("image_url")),
        )
        await db.commit()

async def get_species(species_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT id, name, emoji, rarity, hp, atk, def, price, in_store, image_url '
            'FROM animal_species WHERE id = ?', (species_id,),
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        return None
    return {"id": row[0], "name": row[1], "emoji": row[2], "rarity": row[3], "hp": row[4],
            "atk": row[5], "def": row[6], "price": row[7], "in_store": bool(row[8]), "image_url": row[9]}

async def get_all_species(in_store_only: bool = False):
    q = ('SELECT id, name, emoji, rarity, hp, atk, def, price, in_store, image_url '
         'FROM animal_species')
    if in_store_only:
        q += ' WHERE in_store = 1'
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(q + ' ORDER BY price DESC') as cursor:
            rows = await cursor.fetchall()
    return [{"id": r[0], "name": r[1], "emoji": r[2], "rarity": r[3], "hp": r[4],
             "atk": r[5], "def": r[6], "price": r[7], "in_store": bool(r[8]), "image_url": r[9]} for r in rows]

async def add_animal(owner_id: int, species_id: str, obtained: str = "store") -> int:
    """Naya animal kisi ke collection me daalo, animal_id return karo."""
    import time as _time
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'INSERT INTO animals (owner_id, species_id, obtained, created_at) VALUES (?, ?, ?, ?)',
            (owner_id, species_id, obtained, _time.time()),
        )
        await db.commit()
        return cursor.lastrowid

async def get_animal(animal_id: int):
    """Animal + uski species ek saath (None = exist nahi karta)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT id, owner_id, species_id, nickname, level, xp, wins, losses, hunger, abilities, obtained '
            'FROM animals WHERE id = ?', (animal_id,),
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        return None
    sp = await get_species(row[2])
    if not sp:
        return None
    import json as _json
    try:
        abilities = _json.loads(row[9]) if row[9] else []
    except Exception:
        abilities = []
    return {"id": row[0], "owner_id": row[1], "species": sp, "nickname": row[3],
            "level": row[4] or 1, "xp": row[5] or 0, "wins": row[6] or 0, "losses": row[7] or 0,
            "hunger": row[8] if row[8] is not None else 5, "abilities": abilities, "obtained": row[10]}

async def get_user_animals(owner_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT id FROM animals WHERE owner_id = ? ORDER BY id', (owner_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    out = []
    for (aid,) in rows:
        a = await get_animal(aid)
        if a:
            out.append(a)
    return out

async def count_user_animals(owner_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT COUNT(*) FROM animals WHERE owner_id = ?', (owner_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] or 0

async def delete_animal(animal_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM animals WHERE id = ?', (animal_id,))
        await db.execute('UPDATE users SET active_animal = NULL WHERE active_animal = ?', (animal_id,))
        await db.commit()

async def set_active_animal(user_id: int, animal_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET active_animal = ? WHERE user_id = ?', (animal_id, user_id))
        await db.commit()

async def get_active_animal(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT active_animal FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
    if not row or not row[0]:
        return None
    animal = await get_animal(row[0])
    if animal and animal["owner_id"] != user_id:
        return None
    return animal

async def animal_gain_xp(animal_id: int, amount: int) -> tuple:
    """Animal XP do, (old_level, new_level) return karo. Level N ke liye 100*N^2 XP."""
    animal = await get_animal(animal_id)
    if not animal:
        return (1, 1)
    old_level = animal["level"]
    new_xp = animal["xp"] + amount
    level = old_level
    while 100 * level * level <= new_xp:
        level += 1
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE animals SET xp = ?, level = ? WHERE id = ?', (new_xp, level, animal_id))
        await db.commit()
    return (old_level, level)

async def animal_record_result(animal_id: int, won: bool):
    col = "wins" if won else "losses"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE animals SET ' + col + ' = ' + col + ' + 1 WHERE id = ?', (animal_id,))
        await db.commit()

async def animal_set_hunger(animal_id: int, hunger: int):
    hunger = max(0, min(5, hunger))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE animals SET hunger = ? WHERE id = ?', (hunger, animal_id))
        await db.commit()

async def animal_add_ability(animal_id: int, ability_id: str) -> bool:
    """Ability add karo (max 3). False = already hai ya limit cross."""
    animal = await get_animal(animal_id)
    if not animal or len(animal["abilities"]) >= 3 or ability_id in animal["abilities"]:
        return False
    import json as _json
    abilities = animal["abilities"] + [ability_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE animals SET abilities = ? WHERE id = ?',
                         (_json.dumps(abilities), animal_id))
        await db.commit()
    return True

async def animal_breed(parent_a: dict, parent_b: dict) -> int:
    """Do parents se naya animal: stats 50/50 mix, species random parent se,
    10% chance rarity ek step up ho jaye. Naya animal_id return karo."""
    import secrets as _secrets
    sp = dict(parent_a["species"] if _secrets.randbelow(100) < 50 else parent_b["species"])
    # 50/50 stat mix
    for key in ("hp", "atk", "def"):
        sp[key] = max(1, round((parent_a["species"][key] + parent_b["species"][key]) / 2))
    # 10% rarity upgrade
    order = ["common", "uncommon", "rare", "mythic", "gold"]
    try:
        idx = order.index(sp["rarity"])
    except ValueError:
        idx = 0
    if _secrets.randbelow(100) < 10 and idx < len(order) - 1:
        sp["rarity"] = order[idx + 1]
        sp["id"] = sp["id"] + "_bred"
        sp["price"] = 0
        sp["in_store"] = False
        await upsert_species(sp)
    return await add_animal(parent_a["owner_id"], sp["id"], obtained="bred")

async def set_nickname(animal_id: int, nickname: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE animals SET nickname = ? WHERE id = ?', (nickname[:30], animal_id))
        await db.commit()

async def set_last_hunt(user_id: int, ts: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET last_hunt = ? WHERE user_id = ?', (ts, user_id))
        await db.commit()

async def get_last_hunt(user_id: int) -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT last_hunt FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return (row[0] if row and row[0] else 0.0)

async def set_animal_image_url(species_id: str, url: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE animal_species SET image_url = ? WHERE id = ?', (url, species_id))
        await db.commit()

async def inv_add(user_id: int, item_type: str, item_id: str, qty: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT INTO inventory (user_id, item_type, item_id, qty) VALUES (?, ?, ?, ?) '
            'ON CONFLICT(user_id, item_type, item_id) DO UPDATE SET qty = qty + ?',
            (user_id, item_type, item_id, qty, qty),
        )
        await db.commit()

async def inv_take(user_id: int, item_type: str, item_id: str, qty: int = 1) -> bool:
    """Item nikalo. False = enough nahi hai."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'UPDATE inventory SET qty = qty - ? WHERE user_id = ? AND item_type = ? AND item_id = ? AND qty >= ?',
            (qty, user_id, item_type, item_id, qty),
        )
        if cursor.rowcount == 0:
            return False
        await db.execute(
            'DELETE FROM inventory WHERE user_id = ? AND item_type = ? AND item_id = ? AND qty <= 0',
            (user_id, item_type, item_id),
        )
        await db.commit()
        return True

async def inv_count(user_id: int, item_type: str, item_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT qty FROM inventory WHERE user_id = ? AND item_type = ? AND item_id = ?',
            (user_id, item_type, item_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def inv_all(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT item_type, item_id, qty FROM inventory WHERE user_id = ? AND qty > 0 ORDER BY item_type',
            (user_id,),
        ) as cursor:
            return [(r[0], r[1], r[2]) for r in await cursor.fetchall()]

async def set_banner_url(banner_id: int, url: str):
    """Banner ka preview URL set/backfill karo."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE banners SET url = ? WHERE id = ?', (url, banner_id))
        await db.commit()

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
