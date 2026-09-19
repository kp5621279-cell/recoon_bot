import asyncio
import math
import secrets
import time

import discord
from discord.ext import commands

import database

# Banner image URL (Discord CDN for emoji 473)
BANNER_URL = "https://cdn.discordapp.com/emojis/1550526211388612608.png?size=512"

# Custom server emoji shown wherever the bot mentions coins
COIN = "<:coin:1550545065397584066>"

ROCKET = "🚀"
TICK = 1.2      # seconds between animation frames (Discord allows ~5 edits / 5s)
GROWTH = 0.15   # multiplier grows as e^(GROWTH * elapsed): 2x in ~4.6s, 10x in ~15s
MAX_CRASH = 10.0   # the rocket can never fly higher than 10x (~15s), luck decides how far it gets

WIDTH = 17      # cells per sky row: long horizontal lines, room for the diagonal climb
ROWS = 7        # six climbable rows plus the ground line
# Progress at which the rocket reaches the top row (~7.9x). Keeping this close
# to 1 means the rocket climbs almost all the way to the 10x ceiling instead of
# parking on the top row halfway through the round.
CLIMB_TOP = 0.9

# The sky is deliberately bare: no sparkles, no flames, no smoke. The rocket is
# the only thing drawn on it, so there is nothing to confuse it with.
GROUND = "▁" * WIDTH

def multiplier_at(elapsed: float) -> float:
    """Rocket height after `elapsed` seconds."""
    return math.exp(GROWTH * elapsed)

def roll_crash_point(luck_shift: float = 0.0) -> float:
    """Pick where the rocket blows up.

    The classic crash curve, capped at MAX_CRASH: ~1% of rounds die instantly at
    1.00x, ~50% reach 2x, ~20% reach 5x and ~10% reach the 10x ceiling. Because
    the curve is cut at 10x, cashing out at any target x always returns 0.99 * x
    on average - the 99 (instead of 100) is a flat 1% house edge, no matter where
    players cash out.

    luck_shift (-0.35..+0.35) biases the draw: at +0.35 the ~15s flight time
    before an average crash roughly doubles (rocket lasts noticeably longer),
    at -0.35 it halves. Consumed per game, so it never stacks.
    """
    r = secrets.randbelow(1_000_000) / 1_000_000
    r = min(1.0, max(1e-6, r - luck_shift))
    return min(MAX_CRASH, max(1.0, round(99 / (1 - r)) / 100))

def sky_frame(multiplier: float, rocket=ROCKET, blast=False) -> str:
    """One animation frame: the rocket climbs diagonally across a bare sky.

    Height is logarithmic, so 1x-2x already lifts it a row, 5x gets it two thirds
    of the way up and MAX_CRASH reaches the top row. On top of that the rocket
    drifts sideways as it climbs, which is what makes the climb read as motion
    instead of the rocket simply blinking between rows.
    """
    canvas = [["·"] * WIDTH for _ in range(ROWS - 1)]
    canvas.append(list(GROUND))

    ground_row = len(canvas) - 1          # the ground line is never climbed on
    progress = 0.0 if multiplier <= 1.0 else min(1.0, math.log(multiplier) / math.log(MAX_CRASH))
    # 0 = still on the pad, climb_rows - 1 = top row
    level = min(ground_row - 1, int(progress / CLIMB_TOP * (ground_row - 1)))
    rocket_row = ground_row - 1 - level

    # Diagonal: the rocket also drifts across the sky while it climbs, and stays
    # away from both edges so it never looks clipped.
    margin = WIDTH // 5
    column = int(round(margin + progress * (WIDTH - 1 - 2 * margin)))

    if blast:
        canvas[rocket_row] = ["💥"] * WIDTH
    else:
        canvas[rocket_row][column] = rocket

    return "\n".join("".join(row) for row in canvas)


class AviatorRound:
    def __init__(self, cog, user, bet, coins_before, crash_point):
        self.cog = cog
        self.user = user
        self.bet = bet
        self.coins_before = coins_before
        self.crash_point = crash_point
        self.lock = asyncio.Lock()
        self.state = "running"  # running | cashed | crashed
        self.start = 0.0
        self.cash_multiplier = None
        self.message = None
        self.view = None

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.start

    def base_embed(self, multiplier: float) -> discord.Embed:
        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_thumbnail(url=BANNER_URL)
        embed.add_field(name="Bet", value=f"{self.bet} {COIN}", inline=True)
        embed.add_field(name="Cash out now", value=f"**{int(self.bet * multiplier)}** {COIN}", inline=True)
        return embed

    def flying_embed(self, multiplier: float) -> discord.Embed:
        """Mid-flight frame: big multiplier and the rocket climbing a bare sky."""
        embed = self.base_embed(multiplier)
        embed.title = f"{ROCKET} Aviator · {multiplier:.2f}x"
        embed.description = f"## {multiplier:.2f}x\n{sky_frame(multiplier)}"
        embed.set_footer(text=f"Cash out before it crashes! · max {MAX_CRASH:.0f}x")
        return embed

    def crash_embed(self, exploded: bool = True) -> discord.Embed:
        """Crash frame: the rocket's row goes up in flames."""
        embed = self.base_embed(self.crash_point)
        embed.color = discord.Color.dark_red()
        if exploded:
            embed.title = "💥 CRASHED!"
            embed.description = f"## {self.crash_point:.2f}x\n{sky_frame(self.crash_point, blast=True)}"
        else:
            embed.title = f"💥 Crashed at {self.crash_point:.2f}x"
            embed.description = (
                f"## {self.crash_point:.2f}x\n"
                f"{sky_frame(self.crash_point, rocket='💥')}\n"
                f"The rocket blew up! You lost **{self.bet}** {COIN}."
            )
        return embed

    def cashout_embed(self, multiplier: float) -> discord.Embed:
        """Win frame: the rocket stops safely where it got to."""
        winnings = int(self.bet * multiplier)
        embed = self.base_embed(multiplier)
        embed.color = discord.Color.green()
        embed.title = f"💰 CASHED OUT at {multiplier:.2f}x"
        embed.description = (
            f"## {multiplier:.2f}x\n"
            f"{sky_frame(multiplier)}\n"
            f"You won **{winnings}** {COIN}!\nNew balance: **{self.coins_before - self.bet + winnings}**"
        )
        return embed

    async def finish_crash(self):
        """Blow the rocket up (two frames), then show the result."""
        self.state = "crashed"
        for child in self.view.children:
            child.disabled = True

        await self.message.edit(embed=self.crash_embed(exploded=True), view=self.view)
        await asyncio.sleep(0.7)
        await self.message.edit(embed=self.crash_embed(exploded=False), view=self.view)


class AviatorView(discord.ui.View):
    def __init__(self, round_):
        super().__init__(timeout=None)
        self.round = round_

    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.success, emoji="💰")
    async def cashout(self, interaction: discord.Interaction, button: discord.ui.Button):
        round_ = self.round

        if interaction.user.id != round_.user.id:
            return await interaction.response.send_message("This isn't your rocket! 🚀", ephemeral=True)

        async with round_.lock:
            if round_.state != "running":
                message = "You already cashed out." if round_.state == "cashed" else "Too late — the rocket already crashed! 💥"
                return await interaction.response.send_message(message, ephemeral=True)

            multiplier = multiplier_at(round_.elapsed)
            if multiplier >= round_.crash_point:
                # The rocket is already dead but the loop has not ticked yet.
                return await interaction.response.send_message("Too late — the rocket crashed! 💥", ephemeral=True)

            round_.state = "cashed"
            round_.cash_multiplier = multiplier
            winnings = int(round_.bet * multiplier)
            await database.update_coins(round_.user.id, winnings)

            for child in round_.view.children:
                child.disabled = True
            await interaction.response.edit_message(embed=round_.cashout_embed(multiplier), view=round_.view)


class Aviator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active = {}  # user_id: AviatorRound

    @commands.command(name="aviator", aliases=["av", "crash"])
    async def aviator(self, ctx: commands.Context, bet: int):
        f"""
        Bet {COIN} on the rocket and cash out before it crashes!
        Usage: <prefix>aviator <bet_amount>
        Example: !aviator 500
        """
        if bet <= 0:
            return await ctx.send("❌ Bet must be greater than 0.")

        if ctx.author.id in self.active:
            return await ctx.send("🚀 Your rocket is still flying! Cash out first.")

        user_data = await database.get_user(ctx.author.id)
        if not user_data or user_data["coins"] < bet:
            return await ctx.send(f"❌ You don't have enough {COIN}! Your balance: {user_data['coins'] if user_data else 0}")

        # Take the bet up front, like the coin flip does.
        await database.update_coins(ctx.author.id, -bet)
        try:
            await database.record_game(ctx.author.id)
        except Exception:
            pass
        try:
            from bot import game_xp
            await game_xp(ctx)
        except Exception:
            pass

        shift = database.luck_shift(await database.consume_luck(ctx.author.id))
        round_ = AviatorRound(self, ctx.author, bet, user_data["coins"], roll_crash_point(shift))
        self.active[ctx.author.id] = round_
        round_.view = AviatorView(round_)
        round_.message = await ctx.send(embed=round_.flying_embed(1.0), view=round_.view)

        self.bot.loop.create_task(self.run_round(round_))

    async def run_round(self, round_):
        """Animate the rocket until it crashes or the player cashes out."""
        round_.start = time.monotonic()
        try:
            while True:
                await asyncio.sleep(TICK)

                async with round_.lock:
                    if round_.state != "running":
                        return  # cashed out in the meantime

                    multiplier = multiplier_at(round_.elapsed)
                    if multiplier >= round_.crash_point:
                        await round_.finish_crash()
                        return

                    await round_.message.edit(embed=round_.flying_embed(multiplier))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"Error running aviator round: {e}")
        finally:
            self.active.pop(round_.user.id, None)


async def setup(bot):
    await bot.add_cog(Aviator(bot))
