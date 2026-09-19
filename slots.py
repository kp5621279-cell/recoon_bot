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


def _weighted(luck_shift: float = 0.0) -> str:
    """Weighted spin; luck_shift (+0..0.35) rare symbols ki taraf khiskata hai."""
    total = sum(WEIGHTS.values())
    r = secrets.randbelow(total)
    r = int(max(0.0, 1.0 + luck_shift) * r)  # luck positive -> r chhota -> rare (pehle) symbol zyada
    upto = 0
    for sym, w in WEIGHTS.items():
        upto += w
        if r < upto:
            return sym
    return "🍆"

SLOTS_ACTIVE = set()  # ek user ka ek spin ek time par


def spin(luck_shift: float = 0.0) -> list:
    return [_weighted(luck_shift) for _ in range(3)]


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
            return await ctx.send(i18n.t(lang, "s_busy", mention=ctx.author.mention))
        if bet <= 0:
            return await ctx.send(i18n.t(lang, "s_bet_invalid", mention=ctx.author.mention))

        user = await database.get_user(ctx.author.id)
        if not user or user["coins"] < bet:
            return await ctx.send(i18n.t(lang, "m_poor", coin=COIN, balance=user["coins"] if user else 0, mention=ctx.author.mention))

        SLOTS_ACTIVE.add(ctx.author.id)
        try:
            await database.update_coins(ctx.author.id, -bet)
            from bot import game_xp
            await game_xp(ctx)

            reels = spin(max(0.0, database.luck_shift(await database.consume_luck(ctx.author.id))))
            mult, win_key = evaluate(reels, bet)
            win_amount = int(bet * mult)

            animation = "<a:pikuracoin20749_512:1550522369175593061>"
            msg = await ctx.send(embed=discord.Embed(
                title=i18n.t(lang, "s_title"),
                description=i18n.t(lang, "s_spinning", animation=animation, mention=ctx.author.mention),
                color=discord.Color.blurple(),
            ))

            await asyncio.sleep(2.0)

            board = f"# ┃ {reels[0]} ┃ {reels[1]} ┃ {reels[2]} ┃"

            if win_amount > 0:
                await database.update_coins(ctx.author.id, win_amount)
                new_bal = user["coins"] - bet + win_amount
                color = discord.Color.gold() if mult >= 9 else discord.Color.green()
                result = i18n.t(lang, win_key, sym=reels[0])
                payout_val = i18n.t(lang, "s_f_won", amount=win_amount, mult=mult, coin=COIN)
            else:
                new_bal = user["coins"] - bet
                color = discord.Color.red()
                if win_key == "slots_jackpot_eggplant":
                    result = i18n.t(lang, "slots_jackpot_eggplant")
                else:
                    result = i18n.t(lang, "s_f_nomatch")
                payout_val = i18n.t(lang, "s_f_lost", bet=bet, coin=COIN)

            embed = discord.Embed(title=i18n.t(lang, "s_title"), color=color)
            embed.set_thumbnail(url=BANNER_URL)
            embed.add_field(name="\u200b", value=board, inline=False)
            if win_key != "slots_lose":
                embed.add_field(name=i18n.t(lang, "s_f_result_name"), value=result, inline=False)
            embed.add_field(name=i18n.t(lang, "s_f_payout_name"), value=payout_val, inline=False)
            embed.add_field(name=i18n.t(lang, "s_f_balance_name"), value=i18n.t(lang, "s_f_balance", balance=new_bal, coin=COIN), inline=False)
            embed.set_footer(text=i18n.t(lang, "s_footer"))
            await msg.edit(content=None, embed=embed)
        finally:
            SLOTS_ACTIVE.discard(ctx.author.id)


import asyncio  # noqa: E402  (bottom import keeps cog load light)


async def setup(bot):
    await bot.add_cog(Slots(bot))
