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
        async with db.execute('SELECT coins, agreed, last_daily FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"coins": row[0], "agreed": bool(row[1]), "last_daily": row[2] or 0}
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
