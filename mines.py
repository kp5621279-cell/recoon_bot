import discord
from discord.ext import commands
import secrets

import database
import i18n

BANNER_URL = "https://cdn.discordapp.com/emojis/1550526211388612608.png?size=512"
COIN = "<:coin:1550545065397584066>"

MINES_ACTIVE = {}  # user_id -> MinesGame (ek user ka ek hi chalu game)
GAME_TIMEOUT = 600  # 10 min me game apne aap settle ho jata hai

LETTERS = "ABCDEFGHI"


def fair_multiplier(total: int, bombs: int, picks: int) -> float:
    """Stake-style fair mines multiplier (1% house edge).

    Har safe pick ke baad: 0.99 * C(total, picks) / C(total - bombs, picks).
    """
    gems = total - bombs
    mult = 1.0
    for i in range(picks):
        mult *= (total - i) / (gems - i)
    return round(0.99 * mult, 2)


def parse_spec(spec: str):
    """`!mine <bet> <spec>` ka spec parse karo -> (size, bombs, label) ya None.

    - small / s / 3      -> 3x3 board, 3 bombs
    - bigt / t / 5       -> 5x5 board, 5 bombs
    - bigl / l / 9       -> 9x9 board, 9 bombs (sabse bada board = chhote multipliers)
    """
    if spec is None:
        return (5, 5, "Bigt 5x5 - 5 bombs")
    s = spec.strip().lower()
    if s in ("small", "s", "3"):
        return (3, 3, "Small 3x3 - 3 bombs")
    if s in ("bigt", "t", "5"):
        return (5, 5, "Bigt 5x5 - 5 bombs")
    if s in ("bigl", "l", "9"):
        return (9, 9, "Bigl 9x9 - 9 bombs")
    return None


class MinesGame:
    """Ek chalu mines game ka pure logic - discord layer ise render karta hai."""

    def __init__(self, player_id: int, bet: int, size: int, bombs: int, label: str, luck_shift: float = 0.0):
        self.player_id = player_id
        self.bet = bet
        self.size = size
        self.total = size * size
        self.bombs = bombs
        self.gems = self.total - bombs
        self.label = label
        self.lang = "en"  # game start hone par player ki language set hoti hai

        # Luck bias: +35 luck ke saath ~33% chance ki bomb swap ho kar safe tile ban jaye
        self.bomb_set = set(secrets.SystemRandom().sample(range(self.total), bombs))
        if luck_shift > 0 and bombs < self.total:
            safe = [i for i in range(self.total) if i not in self.bomb_set]
            for i in list(self.bomb_set):
                if secrets.randbelow(10_000) < int(luck_shift * 10_000):
                    swap = secrets.choice(safe)
                    self.bomb_set.discard(i)
                    self.bomb_set.add(swap)
                    safe.append(i)
        self.revealed = set()
        self.hit = None          # jis tile par bomb phata
        self.over = False
        self.message = None      # board message
        self.control = None      # control message (9x9 me same hota hai)
        self.view = None
        self.control_view = None

    @property
    def picks(self) -> int:
        return len(self.revealed)

    def multiplier(self) -> float:
        return fair_multiplier(self.total, self.bombs, self.picks)

    def cashout_amount(self) -> int:
        return int(self.bet * self.multiplier())

    def open_tile(self, idx: int) -> str:
        """Tile kholo (pure logic). Returns: 'bomb' | 'gem' | 'autowin'."""
        if self.over or idx in self.revealed:
            return "gone"
        if idx in self.bomb_set:
            self.hit = idx
            self.over = True
            return "bomb"
        self.revealed.add(idx)
        if len(self.revealed) == self.gems:
            self.over = True
            return "autowin"
        return "gem"

    def cleanup(self):
        MINES_ACTIVE.pop(self.player_id, None)

    @property
    def mention(self) -> str:
        """Player ka mention - notes me user ko tag karne ke liye."""
        return f"<@{self.player_id}>"

    # ------------------- rendering helpers -------------------

    def control_embed(self, note: str = None) -> discord.Embed:
        mult = self.multiplier()
        cash = self.cashout_amount()
        lang = self.lang
        desc = note or i18n.t(lang, "m_how")
        embed = discord.Embed(
            title=f"💣 {i18n.t(lang, 'm_title')} — {self.label}",
            description=desc,
            color=discord.Color.gold() if self.over else discord.Color.blurple(),
        )
        embed.set_thumbnail(url=BANNER_URL)
        embed.add_field(name=i18n.t(lang, "bet_label"), value=f"{self.bet} {COIN}")
        embed.add_field(name=i18n.t(lang, "multiplier_label"), value=f"**{mult:.2f}x**")
        embed.add_field(
            name=i18n.t(lang, "cashout_label"),
            value=f"**{cash}** {COIN}" if self.picks > 0 else i18n.t(lang, "m_cashout_none"),
        )
        embed.add_field(
            name=i18n.t(lang, "tiles_label"),
            value=i18n.t(lang, "m_tiles_left", gems=self.gems - self.picks, bombs=self.bombs),
            inline=False,
        )
        embed.set_footer(text=i18n.t(lang, "m_footer"))
        return embed

    def big_board_text(self) -> str:
        """9x9 board emoji-grid ke roop me."""
        rows = []
        for r in range(self.size):
            cells = []
            for c in range(self.size):
                i = r * self.size + c
                if i in self.revealed:
                    cells.append("💎")
                elif self.over and i in self.bomb_set:
                    cells.append("💥" if i == self.hit else "💣")
                elif self.over:
                    cells.append("💎" if i not in self.bomb_set else "💣")
                else:
                    cells.append("⬜")
            rows.append(f"{LETTERS[r]} " + " ".join(cells))
        header = "  " + "".join(f"{n}\u20e3" for n in range(1, self.size + 1))
        return header + "\n" + "\n".join(rows)

    def big_embed(self, note: str = None) -> discord.Embed:
        embed = self.control_embed(note)
        embed.description = f"{self.big_board_text()}\n\n{embed.description or ''}".strip()
        return embed

    # ------------------- discord flow -------------------

    async def start(self, ctx: commands.Context):
        self.lang = await database.get_lang(self.player_id)
        if self.size <= 5:
            self.view = BoardView(self)
            self.message = await ctx.send(
                content=i18n.t(self.lang, "m_board_btn", mode=self.label, bet=self.bet, coin=COIN),
                view=self.view,
            )
            self.control_view = ControlView(self)
            self.control = await ctx.send(embed=self.control_embed(), view=self.control_view)
        else:
            self.view = BigBoardView(self)
            self.message = await ctx.send(embed=self.big_embed(), view=self.view)
            self.control = self.message
            self.control_view = self.view

    def _disable_all(self):
        if self.view:
            for child in self.view.children:
                child.disabled = True
        if self.control_view:
            for child in self.control_view.children:
                child.disabled = True

    def _reveal_bombs_on_buttons(self):
        if not isinstance(self.view, BoardView):
            return
        for i, btn in enumerate(self.view.tiles):
            if i in self.bomb_set:
                btn.style = discord.ButtonStyle.danger
                btn.label = "💥" if i == self.hit else "💣"
                btn.disabled = True

    async def _end_edits(self, interaction: discord.Interaction, note: str):
        """Game khatam - dono messages update karo aur state saaf karo."""
        self._disable_all()
        self._reveal_bombs_on_buttons()
        try:
            if isinstance(self.view, BoardView):
                await interaction.response.edit_message(view=self.view)
                await self.control.edit(embed=self.control_embed(note), view=self.control_view)
            else:
                await interaction.response.edit_message(embed=self.big_embed(note), view=self.view)
        except discord.HTTPException:
            pass
        self.cleanup()

    async def pick(self, interaction: discord.Interaction, idx: int, btn: discord.ui.Button = None):
        if interaction.user.id != self.player_id:
            return await interaction.response.send_message(i18n.t(self.lang, "m_not_yours"), ephemeral=True)
        if self.over:
            return await interaction.response.send_message(i18n.t(self.lang, "m_game_over"), ephemeral=True)

        result = self.open_tile(idx)
        if result == "gone":
            return await interaction.response.send_message(i18n.t(self.lang, "m_pick_open", mention=f"<@{interaction.user.id}>"), ephemeral=True)

        if result == "bomb":
            note = i18n.t(self.lang, "m_bomb", bet=self.bet, coin=COIN, mention=self.mention)
            return await self._end_edits(interaction, note)

        if result == "autowin":
            amount = self.cashout_amount()
            await database.update_coins(self.player_id, amount)
            note = i18n.t(self.lang, "m_autowin", amount=amount, coin=COIN, mention=self.mention)
            return await self._end_edits(interaction, note)

        # safe pick: button ko gem bana do
        if btn is not None:
            btn.style = discord.ButtonStyle.success
            btn.label = "💎"
            btn.disabled = True
        try:
            if isinstance(self.view, BoardView):
                await interaction.response.edit_message(view=self.view)
                await self.control.edit(embed=self.control_embed())
            else:
                await interaction.response.edit_message(embed=self.big_embed())
        except discord.HTTPException:
            pass

    async def cashout(self, interaction: discord.Interaction):
        if interaction.user.id != self.player_id:
            return await interaction.response.send_message(i18n.t(self.lang, "m_not_yours", mention=f"<@{interaction.user.id}>"), ephemeral=True)
        if self.over:
            return await interaction.response.send_message("❌ Game khatam ho chuka hai.", ephemeral=True)

        if self.picks == 0:
            # kuch khola hi nahi - bet wapas
            self.over = True
            await database.update_coins(self.player_id, self.bet)
            return await self._end_edits(interaction, i18n.t(self.lang, "m_cashout_zero", bet=self.bet, coin=COIN, mention=self.mention))

        self.over = True
        amount = self.cashout_amount()
        await database.update_coins(self.player_id, amount)
        note = i18n.t(self.lang, "m_cashout", picks=self.picks, amount=amount, coin=COIN, mult=f"{self.multiplier():.2f}", mention=self.mention)
        await self._end_edits(interaction, note)

    async def finish_timeout(self):
        """View timeout - chalu game ko auto-settle karo (fair: khela hua to cashout)."""
        if self.over:
            return
        self.over = True
        if self.picks == 0:
            await database.update_coins(self.player_id, self.bet)
            note = i18n.t(self.lang, "m_timeout_zero", bet=self.bet, coin=COIN, mention=self.mention)
        else:
            amount = self.cashout_amount()
            await database.update_coins(self.player_id, amount)
            note = i18n.t(self.lang, "m_timeout_cash", amount=amount, coin=COIN, mult=f"{self.multiplier():.2f}", mention=self.mention)
        self._disable_all()
        self._reveal_bombs_on_buttons()
        try:
            if isinstance(self.view, BoardView):
                await self.message.edit(view=self.view)
                await self.control.edit(embed=self.control_embed(note), view=self.control_view)
            else:
                await self.message.edit(embed=self.big_embed(note), view=self.view)
        except discord.HTTPException:
            pass
        self.cleanup()


class BoardView(discord.ui.View):
    """3x3 / 5x5 boards: har tile ek button."""

    def __init__(self, game: MinesGame):
        super().__init__(timeout=GAME_TIMEOUT)
        self.game = game
        self.tiles = []
        for i in range(game.total):
            btn = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="\u200b",
                row=i // game.size,
            )
            btn.callback = self._make_cb(i, btn)
            self.add_item(btn)
            self.tiles.append(btn)

    def _make_cb(self, idx: int, btn: discord.ui.Button):
        async def cb(interaction: discord.Interaction):
            await self.game.pick(interaction, idx, btn)
        return cb

    async def on_timeout(self):
        await self.game.finish_timeout()


class ControlView(discord.ui.View):
    """Board message ke niche cash-out panel."""

    def __init__(self, game: MinesGame):
        super().__init__(timeout=GAME_TIMEOUT)
        self.game = game

    @discord.ui.button(label="💰 Cash Out", style=discord.ButtonStyle.success)
    async def cashout_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.game.cashout(interaction)

    async def on_timeout(self):
        await self.game.finish_timeout()


class BigBoardView(discord.ui.View):
    """9x9: Discord me 81 buttons fit nahi hote - tile modal se khologe."""

    def __init__(self, game: MinesGame):
        super().__init__(timeout=GAME_TIMEOUT)
        self.game = game

    @discord.ui.button(label="🔷 Tile kholo", style=discord.ButtonStyle.primary)
    async def pick_tile(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PickTileModal(self.game))

    @discord.ui.button(label="💰 Cash Out", style=discord.ButtonStyle.success)
    async def cashout_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.game.cashout(interaction)

    async def on_timeout(self):
        await self.game.finish_timeout()


class PickTileModal(discord.ui.Modal):
    def __init__(self, game: MinesGame):
        super().__init__(title=i18n.t(game.lang, "m_pick_how")[:45], timeout=120)
        self.game = game
        self.tile = discord.ui.TextInput(
            label=i18n.t(game.lang, "m_pick_label"),
            placeholder="B4",
            min_length=2,
            max_length=2,
            required=True,
        )
        self.add_item(self.tile)

    async def on_submit(self, interaction: discord.Interaction):
        game = self.game
        if game.over:
            return await interaction.response.send_message(i18n.t(game.lang, "m_game_over"), ephemeral=True)
        raw = self.tile.value.strip().upper().replace(" ", "")
        r, c = raw[0], raw[1:]
        if r not in LETTERS[: game.size] or not c.isdigit() or not (1 <= int(c) <= game.size):
            return await interaction.response.send_message(
                i18n.t(game.lang, "m_pick_bad", rows=LETTERS[: game.size], size=game.size, mention=f"<@{interaction.user.id}>"),
                ephemeral=True,
            )
        idx = LETTERS.index(r) * game.size + (int(c) - 1)
        await game.pick(interaction, idx)


class ModeSelectView(discord.ui.View):
    """!mine <bet> ke baad mode dropdown - select karte hi game shuru."""

    MODES = [
        ("small", "Small 3x3", "3 bombs - badhiya multipliers", "🟩"),
        ("bigt", "BigT 5x5", "5 bombs - balanced", "🟨"),
        ("bigl", "BigL 9x9", "9 bombs - chhote multipliers, lamba khel", "🟥"),
    ]

    def __init__(self, ctx: commands.Context, bet: int):
        super().__init__(timeout=60.0)
        self.ctx = ctx
        self.bet = bet
        self.message = None  # dropdown wala message

    @discord.ui.select(
        placeholder="💣 Mode chuno...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label=label, description=desc, emoji=emoji, value=value)
            for value, label, desc, emoji in MODES
        ],
    )
    async def mode_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(i18n.t("en", "m_mode_not_you", mention=interaction.user.mention), ephemeral=True)
        if self.ctx.author.id in MINES_ACTIVE:
            return await interaction.response.send_message(i18n.t("en", "m_mode_active", mention=interaction.user.mention), ephemeral=True)

        spec = select.values[0]
        size, bombs, label = parse_spec(spec)
        user = await database.get_user(self.ctx.author.id)
        if not user or user["coins"] < self.bet:
            bal = user["coins"] if user else 0
            return await interaction.response.edit_message(
                content=i18n.t("en", "m_mode_poor", balance=bal, mention=self.ctx.author.mention),
                embed=None, view=None,
            )

        for child in self.children:
            child.disabled = True

        game = MinesGame(
            self.ctx.author.id, self.bet, size, bombs, label,
            luck_shift=database.luck_shift(await database.consume_luck(self.ctx.author.id)),
        )
        MINES_ACTIVE[self.ctx.author.id] = game
        await database.update_coins(self.ctx.author.id, -self.bet)
        try:
            from bot import game_xp
            await game_xp(self.ctx)
        except Exception:
            pass

        await interaction.response.edit_message(
            content=f"🎮 **{label}** | Bet: {self.bet} {COIN}", embed=None, view=None
        )
        await game.start(self.ctx)

    async def on_timeout(self):
        try:
            for child in self.children:
                child.disabled = True
            if self.message:
                lang = await database.get_lang(self.ctx.author.id)
                await self.message.edit(content=i18n.t(lang, "m_mode_cancel", mention=self.ctx.author.mention), view=self)
        except discord.HTTPException:
            pass


class Mines(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="mine", aliases=["mines"])
    async def mine(self, ctx: commands.Context, bet: int, spec: str = None):
        """💣 Mines - diamonds kholo, bomb se bacho!

        Usage:
          !mine 500        -> mode dropdown se chuno
          !mine 500 small  -> direct 3x3 (3 bombs)
          !mine 500 bigt   -> direct 5x5 (5 bombs)
          !mine 500 bigl   -> direct 9x9 (9 bombs)
        """
        if ctx.author.id in MINES_ACTIVE:
            return await ctx.send(i18n.t(await database.get_lang(ctx.author.id), "m_one_game", mention=ctx.author.mention))
        if bet <= 0:
            return await ctx.send(i18n.t(await database.get_lang(ctx.author.id), "m_bet_invalid", mention=ctx.author.mention))

        # Mode nahi diya? Dropdown dikhao - wahi se select karke game shuru
        if spec is None:
            lang = await database.get_lang(ctx.author.id)
            user = await database.get_user(ctx.author.id)
            if not user or user["coins"] < bet:
                return await ctx.send(i18n.t(lang, "m_poor", coin=COIN, balance=user['coins'] if user else 0, mention=ctx.author.mention))
            view = ModeSelectView(ctx, bet)
            msg = await ctx.send(
                i18n.t(lang, "m_mode_msg", bet=bet, coin=COIN, mention=ctx.author.mention),
                view=view,
            )
            view.message = msg
            return

        lang = await database.get_lang(ctx.author.id)
        parsed = parse_spec(spec)
        if parsed is None:
            return await ctx.send(i18n.t(lang, "m_bad_mode", prefix=ctx.clean_prefix, mention=ctx.author.mention))

        user = await database.get_user(ctx.author.id)
        if not user or user["coins"] < bet:
            return await ctx.send(i18n.t(lang, "m_poor", coin=COIN, balance=user['coins'] if user else 0, mention=ctx.author.mention))

        size, bombs, label = parsed
        game = MinesGame(
            ctx.author.id, bet, size, bombs, label,
            luck_shift=database.luck_shift(await database.consume_luck(ctx.author.id)),
        )
        MINES_ACTIVE[ctx.author.id] = game
        await database.update_coins(ctx.author.id, -bet)
        try:
            from bot import game_xp
            await game_xp(ctx)
        except Exception:
            pass
        await game.start(ctx)


async def setup(bot):
    await bot.add_cog(Mines(bot))
