import aiohttp
import discord
from discord.ext import commands

import database
import i18n

BANNER_URL = "https://cdn.discordapp.com/emojis/1550526211388612608.png?size=512"

# nekos.best categories - sab cute anime gifs, no API key chahiye
ACTIONS = [
    ("kiss",   "💋", "https://nekos.best/api/v2/{cat}?amount=1"),
    ("hug",    "🤗", "https://nekos.best/api/v2/{cat}?amount=1"),
    ("pat",    "🖐️", "https://nekos.best/api/v2/{cat}?amount=1"),
    ("cuddle", "🫂", "https://nekos.best/api/v2/{cat}?amount=1"),
    ("poke",   "👉", "https://nekos.best/api/v2/{cat}?amount=1"),
    ("bite",   "🦷", "https://nekos.best/api/v2/{cat}?amount=1"),
    ("slap",   "👋", "https://nekos.best/api/v2/{cat}?amount=1"),
    ("wave",   "👋", "https://nekos.best/api/v2/{cat}?amount=1"),
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

    @commands.command(name="hug")
    async def hug(self, ctx, target: discord.Member = None):
        """Hug someone with a cute gif!"""
        await self._do_action(ctx, "hug", "🤗", target)

    @commands.command(name="pat")
    async def pat(self, ctx, target: discord.Member = None):
        """Head pat someone with a cute gif!"""
        await self._do_action(ctx, "pat", "🖐️", target)

    @commands.command(name="cuddle")
    async def cuddle(self, ctx, target: discord.Member = None):
        """Cuddle someone with a cute gif!"""
        await self._do_action(ctx, "cuddle", "🫂", target)

    @commands.command(name="poke")
    async def poke(self, ctx, target: discord.Member = None):
        """Poke someone with a cute gif!"""
        await self._do_action(ctx, "poke", "👉", target)

    @commands.command(name="bite")
    async def bite(self, ctx, target: discord.Member = None):
        """Playfully bite someone with a cute gif!"""
        await self._do_action(ctx, "bite", "🦷", target)

    @commands.command(name="slap")
    async def slap(self, ctx, target: discord.Member = None):
        """Slap someone with a gif!"""
        await self._do_action(ctx, "slap", "👋", target)

    @commands.command(name="wave")
    async def wave(self, ctx, target: discord.Member = None):
        """Wave at someone with a cute gif!"""
        await self._do_action(ctx, "wave", "👋", target)


async def setup(bot):
    await bot.add_cog(Gifs(bot))
