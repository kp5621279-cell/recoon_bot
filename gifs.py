import aiohttp
import discord
from discord.ext import commands

import database
import i18n

BANNER_URL = "https://cdn.discordapp.com/emojis/1550526211388612608.png?size=512"

# nekos.best categories - sab cute anime gifs, no API key chahiye
# (key, emoji, aliases)
ACTIONS = [
    # pyaar wale
    ("kiss",     "💋", ("kis",)),
    ("hug",      "🤗", ()),
    ("pat",      "🖐️", ()),
    ("cuddle",   "🫂", ()),
    ("poke",     "👉", ()),
    ("bite",     "🦷", ()),
    ("slap",     "👋", ()),
    ("wave",     "👋", ()),
    # action/dhamaka wale
    ("kick",     "🦵", ()),
    ("punch",    "👊", ("fuck",)),
    ("bonk",     "🔨", ()),
    ("shoot",    "🔫", ()),
    ("yeet",     "🚀", ()),
    # aur bhi mast
    ("highfive", "🙌", ()),
    ("feed",     "🍚", ()),
    ("tickle",   "🪶", ()),
    ("carry",    "🧸", ()),
    ("facepalm", "🤦", ()),
    ("tableflip", "🫠", ()),
    ("handhold", "🤝", ()),
    ("shrug",    "🤷", ()),
    ("wink",     "😉", ()),
    ("blush",    "😊", ()),
    ("smug",     "😏", ()),
    ("laugh",    "😂", ()),
    ("cry",      "😭", ()),
    ("angry",    "😠", ()),
    ("dance",    "💃", ()),
]


async def fetch_action_gif(category: str):
    """nekos.best se random gif URL nikalo. None = fail."""
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


async def setup(bot):
    cog = Gifs(bot)
    await bot.add_cog(cog)

    # Commands bot-level register karo (cog self-binding issues se bachne ke liye)
    for key, emoji, aliases in ACTIONS:
        def _make(k=key, e=emoji):
            async def action_cmd(ctx, target: discord.Member = None):
                await cog._do_action(ctx, k, e, target)
            action_cmd.__name__ = f"gif_{k}"
            return action_cmd
        bot.add_command(commands.Command(
            _make(key, emoji),
            name=key,
            aliases=list(aliases),
            help=f"{key.title()} someone with a gif! Usage: {key} @user",
        ))
