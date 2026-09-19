import aiohttp
import discord
from discord.ext import commands

import database
import i18n

BANNER_URL = "https://cdn.discordapp.com/emojis/1550526211388612608.png?size=512"

# nekos.best categories - sab cute anime gifs, no API key chahiye
# (key, emoji) - URL pattern common hai
ACTIONS = [
    # pyaar wale
    ("kiss",     "💋"),
    ("hug",      "🤗"),
    ("pat",      "🖐️"),
    ("cuddle",   "🫂"),
    ("poke",     "👉"),
    ("bite",     "🦷"),
    ("slap",     "👋"),
    ("wave",     "👋"),
    # action/dhamaka wale (user ke maange)
    ("kick",     "🦵"),
    ("punch",    "👊"),
    ("bonk",     "🔨"),
    ("shoot",    "🔫"),
    ("yeet",     "🚀"),
    # aur bhi mast
    ("highfive", "🙌"),
    ("feed",     "🍚"),
    ("tickle",   "🪶"),
    ("carry",    "🧸"),
    ("facepalm", "🤦"),
    ("tableflip", "(╯°□°）╯︵ ┻━┻"),
    ("handhold", "🤝"),
    ("shrug",    "🤷"),
    ("wink",     "😉"),
    ("blush",    "😊"),
    ("smug",     "😏"),
    ("laugh",    "😂"),
    ("cry",      "😭"),
    ("angry",    "😠"),
    ("dance",    "💃"),
]

_api_lock = None  # lazily created


async def fetch_action_gif(category: str) -> str:
    """nekos.best se random gif URL nikalo. None = fail."""
    global _api_lock
    if _api_lock is None:
        import asyncio
        _api_lock = asyncio.Lock()
    async with _api_lock:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://nekos.best/api/v2/{category}?amount=1",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json(content_type=None)
                    results = data.get("results") or []
                    return results[0].get("url") if results else None
        except Exception:
            return None


def build_action_embed(key: str, emoji: str, sender, target, gif_url: str, lang: str) -> discord.Embed:
    """Roleplay action embed: sender ne target ko kiya."""
    desc = i18n.t(lang, f"gif_{key}", sender=sender.display_name, target=target.display_name, mention=sender.mention)
    embed = discord.Embed(description=desc, color=discord.Color.pink())
    embed.set_image(url=gif_url)
    embed.set_footer(text=i18n.t(lang, "gif_footer", emoji=emoji))
    return embed


class Gifs(commands.Cog):
    """Cute roleplay GIF commands - kiss @user, hug @user etc."""

    def __init__(self, bot):
        self.bot = bot

    async def _do_action(self, ctx, key: str, emoji: str, target):
        lang = await database.get_lang(ctx.author.id)
        if target is None:
            return await ctx.send(i18n.t(lang, "gif_need_target", prefix=ctx.clean_prefix, cmd=key, mention=ctx.author.mention))
        if target.id == ctx.author.id:
            return await ctx.send(i18n.t(lang, f"gif_self_{key}", mention=ctx.author.mention))

        gif_url = await fetch_action_gif(key)
        if not gif_url:
            return await ctx.send(i18n.t(lang, "gif_fail", mention=ctx.author.mention))

        embed = build_action_embed(key, emoji, ctx.author, target, gif_url, lang)
        await ctx.send(target.mention, embed=embed)

    @commands.command(name="kiss", aliases=["kis"])
    async def kiss(self, ctx, target: discord.Member = None):
        """Kiss someone with a cute gif!"""
        await self._do_action(ctx, "kiss", "💋", target)

    # Baaki sab actions dynamic generate (ACTIONS list se)
    # 'fuck' user-maanga punch variant hai (Discord-safe command name)
    def _make_action(key: str, emoji: str, aliases=()):
        async def action_cmd(self, ctx, target: discord.Member = None):
            await self._do_action(ctx, key, emoji, target)
        action_cmd.__name__ = f"gif_{key}"
        action_cmd.__doc__ = f"{key.title()} someone with a gif!"
        return commands.command(name=key, aliases=list(aliases))(action_cmd)

    hug = _make_action("hug", "🤗")
    pat = _make_action("pat", "🖐️")
    cuddle = _make_action("cuddle", "🫂")
    poke = _make_action("poke", "👉")
    bite = _make_action("bite", "🦷")
    slap = _make_action("slap", "👋")
    wave = _make_action("wave", "👋")
    kick = _make_action("kick", "🦵")
    punch = _make_action("punch", "👊", aliases=["fuck"])
    bonk = _make_action("bonk", "🔨")
    shoot = _make_action("shoot", "🔫")
    yeet = _make_action("yeet", "🚀")
    highfive = _make_action("highfive", "🙌")
    feed = _make_action("feed", "🍚")
    tickle = _make_action("tickle", "🪶")
    carry = _make_action("carry", "🧸")
    facepalm = _make_action("facepalm", "🤦")
    tableflip = _make_action("tableflip", "🫠")
    handhold = _make_action("handhold", "🤝")
    shrug = _make_action("shrug", "🤷")
    wink = _make_action("wink", "😉")
    blush = _make_action("blush", "😊")
    smug = _make_action("smug", "😏")
    laugh = _make_action("laugh", "😂")
    cry = _make_action("cry", "😭")
    angry = _make_action("angry", "😠")
    dance = _make_action("dance", "💃")


async def setup(bot):
    await bot.add_cog(Gifs(bot))
