import discord
from discord.ext import commands
import secrets

import database
import i18n

BANNER_URL = "https://cdn.discordapp.com/emojis/1550526211388612608.png?size=512"
COIN = "<:coin:1550545065397584066>"

# Reels ke symbols (brinjal sabse common)
SYMBOLS = ["🍆", "🍆", "🍆", "🍆", "🍒", "💜", "🍌", "💔"]

# 3-match payouts (bet ka multiplier) - tumhare rules
PAYOUT_3 = {"💔": 100, "🍒": 9, "💜": 3, "🍌": 2, "🍆": 0}
# 2-match (pehli do reels same) ka consolation
PAYOUT_2 = {"💔": 40, "🍒": 14, "💜": 8, "🍌": 5, "🍆": 0}

# Weighted spin: brinjal common,💔 rare (jackpot feel)
WEIGHTS = {"🍆": 10, "🍌": 6, "💜": 5, "🍒": 4, "💔": 2}


def _weighted() -> str:
    total = sum(WEIGHTS.values())
    r = secrets.randbelow(total)
    upto = 0
    for sym, w in WEIGHTS.items():
        upto += w
        if r < upto:
            return sym
    return "🍆"

SLOTS_ACTIVE = set()  # ek user ka ek spin ek time par


def spin() -> list:
    return [_weighted() for _ in range(3)]


def evaluate(reels: list, bet: int):
    """Return (multiplier, win_key) - win_key message ke liye."""
    a, b, c = reels
    if a == b == c:
        m = PAYOUT_3.get(a, 0)
        if a == "🍆":
            return 0, "slots_jackpot_eggplant"  # lol: 3 brinjal = sab loss
        return m, "slots_triple"
    if a == b:
        return PAYOUT_2.get(a, 0), "slots_pair"
    return 0, "slots_lose"


class Slots(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="slots", aliases=["slot"])
    async def slots(self, ctx: commands.Context, bet: int):
        """🎰 Slots - 3 reels spin karo, symbols milao!

        Payouts: 3x💔 = 100x | 3x🍒 = 9x | 3x💜 = 3x | 3x🍌 = 2x
        3x🍆 = sab loss 💀 | 2 same = chhota consolation
        """
        lang = await database.get_lang(ctx.author.id)
        if ctx.author.id in SLOTS_ACTIVE:
            return await ctx.send(i18n.t(lang, "s_busy"))
        if bet <= 0:
            return await ctx.send(i18n.t(lang, "s_bet_invalid"))

        user = await database.get_user(ctx.author.id)
        if not user or user["coins"] < bet:
            return await ctx.send(i18n.t(lang, "m_poor", coin=COIN, balance=user["coins"] if user else 0))

        SLOTS_ACTIVE.add(ctx.author.id)
        try:
            await database.update_coins(ctx.author.id, -bet)

            reels = spin()
            mult, win_key = evaluate(reels, bet)
            win_amount = int(bet * mult)

            animation = "<a:pikuracoin20749_512:1550522369175593061>"
            msg = await ctx.send(i18n.t(lang, "s_spinning", animation=animation))

            await asyncio.sleep(2.0)

            board = f"┃ {reels[0]} │ {reels[1]} │ {reels[2]} ┃"
            if win_amount > 0:
                await database.update_coins(ctx.author.id, win_amount)
                new_bal = user["coins"] - bet + win_amount
                desc = i18n.t(lang, win_key, bet=bet, coin=COIN) + "\n"
                desc += i18n.t(lang, "s_win_amount", amount=win_amount, mult=mult, coin=COIN, balance=new_bal)
                color = discord.Color.gold() if mult >= 9 else discord.Color.green()
            else:
                new_bal = user["coins"] - bet
                if win_key == "slots_jackpot_eggplant":
                    desc = i18n.t(lang, "slots_jackpot_eggplant", bet=bet, coin=COIN) + "\n"
                else:
                    desc = ""
                desc += i18n.t(lang, "s_lose", bet=bet, coin=COIN, balance=new_bal)
                color = discord.Color.red()

            embed = discord.Embed(title=i18n.t(lang, "s_title"), description=f"{board}\n\n{desc}", color=color)
            embed.set_thumbnail(url=BANNER_URL)
            await msg.edit(content=None, embed=embed)
        finally:
            SLOTS_ACTIVE.discard(ctx.author.id)


import asyncio  # noqa: E402  (bottom import keeps cog load light)


async def setup(bot):
    await bot.add_cog(Slots(bot))
