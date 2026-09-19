import os
import random
import asyncio
import time
import discord
from discord.ext import commands
from dotenv import load_dotenv

import database
import i18n

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Banner image URL (Discord CDN for emoji 473)
BANNER_URL = "https://cdn.discordapp.com/emojis/1550526211388612608.png?size=512"

# Some hosts disconnect requests without a browser-like User-Agent
UA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

# Custom server emoji shown wherever the bot mentions coins
COIN = "<:coin:1550545065397584066>"

# Prayer emoji (pray command + luck messages)
PRAY_EMOJI = "<:praying:1550871729289695352>"

# ------------------- Luck system (shared by all games) -------------------
LUCK_PER_PRAY = 15.0   # ek prayer kitna luck deta hai
LUCK_FREE_DAILY = 10.0  # lkf (daily free luck)
LUCK_PER_GAME = 35.0    # ek game khelne par kitna luck consume hota hai
XP_PER_GAME = 10        # har game khelne par XP

async def game_xp(user_id: int):
    """Game start par XP do (profile level ke liye). Fire-and-forget."""
    try:
        await database.add_xp(user_id, XP_PER_GAME)
    except Exception:
        pass

# Dynamic prefix getter
async def get_dynamic_prefix(bot, message):
    if not message.guild:
        return "!"
    return await database.get_prefix(message.guild.id)

intents = discord.Intents.default()
intents.message_content = True

class CustomHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        lang = await database.get_lang(self.context.author.id)
        p = self.context.clean_prefix
        embed = discord.Embed(
            title=i18n.t(lang, "help_title"),
            description=i18n.t(lang, "help_prefix", prefix=p) + f"\n\n[**🔗 Click Here To Invite Me!**](https://discord.com/oauth2/authorize?client_id=1550499489414909972&permissions=5454653866506561&integration_type=0&scope=bot)",
            color=discord.Color.blurple()
        )
        embed.set_image(url=BANNER_URL)
        
        # Categorize commands manually since we are not using Cogs
        games_cmds = []
        econ_cmds = []
        config_cmds = []
        music_cmds = []
        admin_cmds = []
        is_owner = await self.context.bot.is_owner(self.context.author)

        for command in await self.filter_commands(self.context.bot.commands, sort=True):
            # Help description pehle user ki language se, fallback docstring
            desc = i18n.t(lang, f"h_{command.name}")
            if desc == f"h_{command.name}":
                desc = command.short_doc
            cmd_info = f"**{self.context.clean_prefix}{command.name}** - {desc}"
            if command.name in ["coin", "aviator", "mine", "slots"]:
                games_cmds.append(cmd_info)
            elif command.name in ["bal", "daily", "req", "pay", "pray", "luck", "lkf"]:
                econ_cmds.append(cmd_info)
            elif command.name in ["afk", "profile", "banners", "buy", "banner", "setabout"]:
                econ_cmds.append(cmd_info)
            elif command.name in ["ping", "help", "invite", "lang"]:
                config_cmds.append(cmd_info)
            elif command.name == "set":
                config_cmds.append(cmd_info)
            elif command.name in ["play", "join", "leave", "stop", "skip"]:
                music_cmds.append(cmd_info)
            elif command.name == "ds":
                # ds admin-only hai - sirf admins/owner ko dikhao
                if self.context.author.guild_permissions.manage_guild or is_owner:
                    admin_cmds.append(cmd_info)

        if games_cmds:
            embed.add_field(name=i18n.t(lang, "help_games"), value="\n".join(games_cmds), inline=False)
        if econ_cmds:
            embed.add_field(name=i18n.t(lang, "help_economy"), value="\n".join(econ_cmds), inline=False)
        if music_cmds:
            embed.add_field(name=i18n.t(lang, "help_music"), value="\n".join(music_cmds), inline=False)
        if config_cmds:
            embed.add_field(name=i18n.t(lang, "help_config"), value="\n".join(config_cmds), inline=False)
        if admin_cmds:
            embed.add_field(name="🛡️ Admin", value="\n".join(admin_cmds), inline=False)

        embed.set_footer(text=i18n.t(lang, "help_footer", prefix=p))
        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(
            title=f"Command: {command.name}",
            description=command.help or "No description available.",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=BANNER_URL)
        if command.aliases:
            embed.add_field(name="Aliases", value=", ".join(command.aliases), inline=False)
        embed.add_field(name="Usage", value=f"`{self.context.clean_prefix}{command.name} {command.signature}`", inline=False)
        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group):
        embed = discord.Embed(
            title=f"Group: {group.name}",
            description=group.help or "No description available.",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=BANNER_URL)
        for command in await self.filter_commands(group.commands, sort=True):
            embed.add_field(name=command.name, value=command.short_doc or "No description", inline=False)
        await self.get_destination().send(embed=embed)

class MyBot(commands.Bot):
    async def setup_hook(self):
        await self.load_extension("music")
        await self.load_extension("aviator")
        await self.load_extension("mines")
        await self.load_extension("slots")
        await self.load_extension("profile")

bot = MyBot(
    command_prefix=get_dynamic_prefix,
    intents=intents,
    help_command=CustomHelpCommand(),
)

LANG_FLAGS = {
    "en": "🇬🇧", "hi": "🇮🇳", "mr": "🇮🇳", "fr": "🇫🇷",
    "id": "🇮🇩", "ar": "🇸🇦", "zh": "🇨🇳", "ja": "🇯🇵",
}

class LanguageView(discord.ui.View):
    """Language picker - agreement ke baad aur !lang se bhi."""

    def __init__(self, user_id: int, current: str = None):
        super().__init__(timeout=120.0)
        self.user_id = user_id
        # Har instance ke liye FRESH options (default highlight per-user chahiye)
        self.lang_select.options = [
            discord.SelectOption(
                label=name, value=code, emoji=LANG_FLAGS.get(code),
                default=(code == current),
            )
            for code, name in i18n.LANG_NAMES.items()
        ]

    @staticmethod
    def prompt_embed(cur_lang: str, prefix: str = "!") -> discord.Embed:
        embed = discord.Embed(
            title=i18n.t(cur_lang, "lang_title"),
            description=i18n.t(cur_lang, "lang_desc", cur_lang=i18n.LANG_NAMES.get(cur_lang, cur_lang), prefix=prefix),
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=BANNER_URL)
        return embed

    @discord.ui.select(
        placeholder="🌐 Language chuno...",
        min_values=1,
        max_values=1,
        options=[discord.SelectOption(label=name, value=code) for code, name in i18n.LANG_NAMES.items()],
    )
    async def lang_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(i18n.t("en", "not_for_you"), ephemeral=True)
        code = select.values[0]
        await database.set_lang(self.user_id, code)
        for child in self.children:
            child.disabled = True
        embed = discord.Embed(
            title=i18n.t(code, "lang_set", cur_lang=i18n.LANG_NAMES[code]),
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=BANNER_URL)
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


class AgreementView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60.0)
        self.user_id = user_id
        self.value = None

    @discord.ui.button(label="I Agree", style=discord.ButtonStyle.green, custom_id="agree_btn")
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(i18n.t("en", "not_for_you"), ephemeral=True)
            return
        await database.create_user(self.user_id, coins=1000)
        self.value = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=i18n.t("en", "agreed", coin=COIN), view=self
        )
        self.stop()
        # Agreement ke baad language chuno
        try:
            await interaction.followup.send(
                embed=LanguageView.prompt_embed("en"), view=LanguageView(self.user_id),
            )
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, custom_id="decline_btn")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(i18n.t("en", "not_for_you"), ephemeral=True)
            return
        self.value = False
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=i18n.t("en", "declined"), view=self)
        self.stop()

# (requester_id, target_id) pairs still waiting for an answer in DMs
PENDING_REQUESTS = set()
REQUEST_TIMEOUT = 180.0


def coin_request_embed(requester: discord.abc.User, amount: int, balance: int) -> discord.Embed:
    embed = discord.Embed(
        title=f"💰 {COIN} Request",
        description=f"**{requester.display_name}** is requesting **{amount}** {COIN} from you.",
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=requester.display_avatar.url)
    embed.add_field(name="Your balance", value=f"{balance} {COIN}")
    embed.set_footer(text=f"Approve or decline - this request expires in {int(REQUEST_TIMEOUT / 60)} minutes.")
    return embed


class CoinRequestView(discord.ui.View):
    """Approve/Decline buttons that arrive in the target's DMs."""

    def __init__(self, requester: discord.abc.User, target: discord.abc.User, amount: int):
        super().__init__(timeout=REQUEST_TIMEOUT)
        self.requester = requester
        self.target = target
        self.amount = amount
        self.message = None
        self.answered = False

    @property
    def key(self):
        return (self.requester.id, self.target.id)

    def _lock(self):
        for child in self.children:
            child.disabled = True

    async def on_timeout(self):
        PENDING_REQUESTS.discard(self.key)
        self._lock()
        if self.message:
            embed = discord.Embed(
                title="⌛ Request expired",
                description=f"**{self.requester.display_name}** never got an answer for their **{self.amount}** {COIN} request.",
                color=discord.Color.dark_grey()
            )
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✅")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("This request isn't for you!", ephemeral=True)
        if self.answered:
            return await interaction.response.send_message("You already answered this request.", ephemeral=True)

        if not await database.transfer_coins(self.target.id, self.requester.id, self.amount):
            return await interaction.response.send_message(
                f"❌ You don't have **{self.amount}** {COIN} to give.", ephemeral=True
            )

        self.answered = True
        PENDING_REQUESTS.discard(self.key)
        self._lock()
        embed = discord.Embed(
            title="✅ Request approved",
            description=f"You gave **{self.amount}** {COIN} to **{self.requester.display_name}**.",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

        try:
            await self.requester.send(f"✅ **{self.target.display_name}** approved your request - you received **{self.amount}** {COIN}.")
        except discord.Forbidden:
            pass  # the requester has DMs closed, the coins still moved

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("This request isn't for you!", ephemeral=True)
        if self.answered:
            return await interaction.response.send_message("You already answered this request.", ephemeral=True)

        self.answered = True
        PENDING_REQUESTS.discard(self.key)
        self._lock()
        embed = discord.Embed(
            title="❌ Request declined",
            description=f"You kept your {COIN}. **{self.requester.display_name}** was told you declined.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

        try:
            await self.requester.send(f"❌ **{self.target.display_name}** declined your request for **{self.amount}** {COIN}.")
        except discord.Forbidden:
            pass


class BeastModeView(discord.ui.View):
    """Beast Mode magic powers - owner ke liye special controls."""

    def __init__(self, target: discord.abc.User, actor: discord.abc.User):
        super().__init__(timeout=120.0)
        self.target = target
        self.actor = actor

    @discord.ui.select(
        placeholder="🔥 Beast Mode - option chuno...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="Give Coins",
                description="Is user ko apne hisab se coins do (ya lo).",
                emoji="💰",
                value="give_coins",
            ),
            discord.SelectOption(
                label="Reset Balance",
                description="Is user ka balance wapas default 1000 par set karo.",
                emoji="🔄",
                value="reset_balance",
            ),
            discord.SelectOption(
                label="Ban / Unban User",
                description="Is user ko bot se ban karo (ya unban).",
                emoji="⛔",
                value="ban_user",
            ),
        ],
    )
    async def beast_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.actor.id:
            return await interaction.response.send_message("❌ Ye command tumhare liye nahi hai!", ephemeral=True)

        if select.values[0] == "give_coins":
            await interaction.response.send_modal(GiveCoinsModal(self.target, self))
        elif select.values[0] == "reset_balance":
            await interaction.response.send_modal(BeastConfirmModal(
                f"Reset {self.target.display_name[:25]}", "reset_balance", self
            ))
        elif select.values[0] == "ban_user":
            if self.target.id == self.actor.id:
                return await interaction.response.send_message("❌ Khud ko ban nahi kar sakte!", ephemeral=True)
            if self.target.bot:
                return await interaction.response.send_message("❌ Bot ko ban nahi kar sakte!", ephemeral=True)
            await interaction.response.send_modal(BeastConfirmModal(
                f"Ban/Unban {self.target.display_name[:25]}", "ban_user", self
            ))


class GiveCoinsModal(discord.ui.Modal):
    """Beast Mode: target ko jitne chaho coins do (negative = wapas lo)."""

    def __init__(self, target: discord.abc.User, beast_view: BeastModeView):
        super().__init__(title=f"💰 {target.display_name[:20]} ko coins do", timeout=300)
        self.target = target
        self.beast_view = beast_view
        self.amount_input = discord.ui.TextInput(
            label="Amount (negative = coins wapas lo)",
            placeholder="Jaise: 5000",
            min_length=1,
            max_length=12,
            required=True,
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.amount_input.value.strip().replace(",", "").replace(" ", "")
        try:
            amount = int(raw)
        except ValueError:
            return await interaction.response.send_message(
                "❌ Amount sirf pura number hona chahiye (jaise `5000`).", ephemeral=True
            )
        if amount == 0:
            return await interaction.response.send_message("❌ 0 coins ka kya hi karna... 😅", ephemeral=True)

        new_balance = await database.give_coins(self.target.id, amount)

        for child in self.beast_view.children:
            child.disabled = True

        sign = "+" if amount > 0 else ""
        embed = discord.Embed(
            title="✅ Beast Mode - Coins transferred",
            description=(
                f"**{self.target.mention}** ko **{sign}{amount}** coins diye gaye.\n"
                f"Naya balance: **{new_balance}** {COIN}"
            ),
            color=discord.Color.gold(),
        )
        embed.set_thumbnail(url=BANNER_URL)
        await interaction.response.edit_message(embed=embed, view=self.beast_view)


@bot.event
async def on_message(message: discord.Message):
    # DMs/bots skip
    if message.guild is None or message.author.bot:
        await bot.process_commands(message)
        return

    # 1) AFK user ne khud message bheja -> AFK clear
    if await database.clear_afk(message.author.id):
        lang = await database.get_lang(message.author.id)
        mins = max(1, int((asyncio.get_event_loop().time() - _afk_since.get(message.author.id, 0)) // 60))
        try:
            await message.channel.send(i18n.t(lang, "afk_back", user=message.author.mention, time=f"{mins}m"))
        except discord.HTTPException:
            pass

    # 2) Message me AFK kisi aur ka mention hai -> AFK notice bhejo (har mention par, no cooldown)
    for mentioned in message.mentions:
        if mentioned.id == message.author.id or mentioned.bot:
            continue
        afk = await database.get_afk(mentioned.id)
        if afk:
            reason, since = afk
            mins = max(1, int((time.time() - since) // 60))
            if mins >= 60:
                ago = f"{mins // 60}h {mins % 60}m"
            else:
                ago = f"{mins}m"
            lang = await database.get_lang(message.author.id)
            try:
                await message.channel.send(i18n.t(lang, "afk_notice", user=mentioned.mention, reason=reason, time=ago))
            except discord.HTTPException:
                pass
            break  # ek notice per message kaafi hai

    await bot.process_commands(message)

_afk_since = {}  # user_id: monotonic time jab AFK laga (approx session ke liye)

@bot.check
async def global_agreement_check(ctx: commands.Context):
    # Disabled channel/server me bot kuch nahi karega (ignore commands silently)
    if ctx.guild and not await bot.is_owner(ctx.author):
        if await database.is_channel_disabled(ctx.guild.id, ctx.channel.id):
            raise commands.CheckFailure("Channel disabled.")

    # Banned users ko sabse pehle rok do (owner chhod kar)
    if not await bot.is_owner(ctx.author) and await database.is_banned(ctx.author.id):
        lang = await database.get_lang(ctx.author.id)
        await ctx.send(i18n.t(lang, "banned", mention=ctx.author.mention))
        raise commands.CheckFailure("User is banned.")

    user_data = await database.get_user(ctx.author.id)
    if user_data and user_data["agreed"]:
        return True
    
    # Send agreement prompt
    lang = await database.get_lang(ctx.author.id)
    view = AgreementView(ctx.author.id)
    await ctx.send(i18n.t(lang, "welcome", mention=ctx.author.mention), view=view)
    
    # We raise an error so the current command stops executing. 
    # The user has to run the command again after agreeing.
    raise commands.CheckFailure("User must agree to terms first.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        # Already handled by the check
        pass
    elif isinstance(error, commands.CommandNotFound):
        pass
    elif isinstance(error, commands.MissingRequiredArgument):
        lang = await database.get_lang(ctx.author.id)
        await ctx.send(i18n.t(lang, "missing_arg", param=error.param.name, mention=ctx.author.mention))
    elif isinstance(error, commands.BadArgument):
        lang = await database.get_lang(ctx.author.id)
        await ctx.send(i18n.t(lang, "bad_arg", mention=ctx.author.mention))
    elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, discord.Forbidden):
        print(f"Missing permissions: {error.original}")
        try:
            lang = await database.get_lang(ctx.author.id)
            await ctx.send(i18n.t(lang, "no_perm_bot", mention=ctx.author.mention))
        except discord.HTTPException:
            pass  # channel me bolne ki bhi permission nahi - kuch aur nahi kar sakta
    else:
        print(f"Error: {error}")
        await ctx.send(f"❌ An error occurred: {error}")

@bot.event
async def on_ready() -> None:
    await database.init_db()
    await bot.change_presence(status=discord.Status.dnd)
    print(f"✅ Bot logged in as {bot.user} (ID: {bot.user.id})")

@bot.group(name="set", invoke_without_command=True)
async def set_group(ctx: commands.Context):
    """Configuration commands. Usage: !set p <prefix>"""
    await ctx.send_help(ctx.command)

@set_group.command(name="p")
@commands.has_permissions(administrator=True)
async def set_prefix(ctx: commands.Context, new_prefix: str):
    """Change the bot's prefix for this server."""
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return
    await database.set_prefix(ctx.guild.id, new_prefix)
    await ctx.send(f"✅ Prefix successfully changed to `{new_prefix}`")

@bot.command(name="ping")
async def ping(ctx: commands.Context) -> None:
    """Check bot latency."""
    lang = await database.get_lang(ctx.author.id)
    await ctx.send(i18n.t(lang, "ping", ms=round(bot.latency * 1000), mention=ctx.author.mention))

@bot.command(name="invite", aliases=["add"])
async def invite(ctx: commands.Context):
    """Get the invite link for this bot."""
    lang = await database.get_lang(ctx.author.id)
    link = "https://discord.com/oauth2/authorize?client_id=1550499489414909972&permissions=5454653866506561&integration_type=0&scope=bot"
    await ctx.send(i18n.t(lang, "invite", link=link, mention=ctx.author.mention))

@bot.group(name="ds", invoke_without_command=True)
@commands.has_permissions(manage_guild=True)
async def ds_group(ctx: commands.Context):
    """🔇 Bot ko is channel me disable/enable karo. Usage: ds all | ds off"""
    await ctx.send_help(ctx.command)

@ds_group.command(name="all")
@commands.has_permissions(manage_guild=True)
async def ds_all(ctx: commands.Context):
    """Is channel me bot ko band karo (commands ignore karega)."""
    await database.set_channel_disabled(ctx.guild.id, ctx.channel.id, True)
    await ctx.send(f"🔇 Bot **is channel me disable** ho gaya. Ab yahan commands ignore hongi.\nWapas chalu karne ke liye: `{ctx.clean_prefix}ds off`")

@ds_group.command(name="off")
@commands.has_permissions(manage_guild=True)
async def ds_off(ctx: commands.Context):
    """Is channel me bot ko wapas chalu karo."""
    await database.set_channel_disabled(ctx.guild.id, ctx.channel.id, False)
    await ctx.send("🔊 Bot **is channel me wapas enable** ho gaya!")

@ds_group.command(name="server")
@commands.has_permissions(administrator=True)
async def ds_server(ctx: commands.Context):
    """Pura server me bot band (sirf admin)."""
    await database.set_channel_disabled(ctx.guild.id, 0, True)
    await ctx.send(f"🔇 Bot **pura server me disable** ho gaya!\nWapas: `{ctx.clean_prefix}ds serveroff`")

@ds_group.command(name="serveroff")
@commands.has_permissions(administrator=True)
async def ds_serveroff(ctx: commands.Context):
    """Pura server me bot wapas chalu (sirf admin)."""
    await database.set_channel_disabled(ctx.guild.id, 0, False)
    await ctx.send("🔊 Bot **pura server me wapas enable** ho gaya!")

@ds_group.command(name="reset")
@commands.has_permissions(administrator=True)
async def ds_reset(ctx: commands.Context):
    """Server ke saare disables ek saath hatao."""
    await database.clear_all_disabled(ctx.guild.id)
    await ctx.send("🔊 Saare channel disables **reset** ho gaye!")

@bot.command(name="lang", aliases=["language"])
async def language(ctx: commands.Context):
    """🌐 Apni language chuno - bot ke saare messages isi me aayenge."""
    lang = await database.get_lang(ctx.author.id)
    view = LanguageView(ctx.author.id, lang)
    await ctx.send(
        embed=LanguageView.prompt_embed(lang, await database.get_prefix(ctx.guild.id) if ctx.guild else "!"),
        view=view,
    )

@set_group.command(name="lang")
@commands.is_owner()
async def set_lang(ctx: commands.Context, user: discord.User, code: str):
    """Owner: kisi user ki language set karo. Usage: !set lang @user hi"""
    code = code.lower()
    if code not in i18n.LANG_NAMES:
        return await ctx.send(f"❌ Unknown language code. Options: {', '.join(i18n.LANG_NAMES)}")
    await database.set_lang(user.id, code)
    await ctx.send(f"✅ {user.mention} ki language ab **{i18n.LANG_NAMES[code]}** hai.")

# Read the txt file in this folder: each line is a URL to a file that holds links
def read_source_urls() -> list:
    sources = []
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "github repository .txt")
    try:
        with open(path, encoding="utf-8") as f:
            raw_lines = [line.strip() for line in f if line.strip() and not line.lstrip().startswith("#")]
    except OSError:
        return sources
    for line in raw_lines:
        if line.lower().startswith(("http://", "https://")):
            sources.append(line)
    return sources


async def load_video_links() -> list:
    """Fetch the link lists from every source URL in the txt file."""
    import aiohttp

    links = []
    sources = read_source_urls()
    if not sources:
        return links

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(headers=UA_HEADERS, timeout=timeout) as session:
        for url in sources:
            for attempt in (1, 2):
                try:
                    async with session.get(url, allow_redirects=True) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            for line in text.splitlines():
                                line = line.strip()
                                if line and not line.lstrip().startswith("#"):
                                    links.append(line)
                            break
                except Exception:
                    if attempt >= 2:
                        continue
    return links


def is_url(line: str) -> bool:
    return line.lower().startswith(("http://", "https://"))


@bot.command(name="links")
async def show_links(ctx: commands.Context):
    """Show links from the GitHub links file."""
    links = await load_video_links()
    if not links:
        await ctx.send("❌ Koi link nahi mila. Pehle txt file me source URL daalo.")
        return

    await ctx.send(f"**📁 Kuch links hain...** ({len(links)} total)")

    MAX_SHOW = 10
    for line in links:
        if MAX_SHOW <= 0:
            await ctx.send("ℹ️ Bahut saare links hain - main sirf pehle 10 dikha raha hoon.")
            break
        MAX_SHOW -= 1
        if is_url(line):
            # Direct URL: Discord khud media/video preview render karega
            await ctx.send(line)
        else:
            await ctx.send(f"**{line}**")

@bot.command(name="krish9322", hidden=True)
@commands.is_owner()
async def beast_mode(ctx: commands.Context, target: discord.User = None):
    """🔥 Beast Mode - secret owner powers. Usage: krish9322 <@user>"""
    # Secret command: tumhara message turant delete - koi command na dekhe
    try:
        await ctx.message.delete()
    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
        pass  # Manage Messages permission nahi to message rehne do

    target = target or ctx.author

    embed = discord.Embed(
        title="🔥 Beast Mode",
        description=f"**Target:** {target.mention}\nNiche dropdown se power chuno.",
        color=discord.Color.gold(),
    )
    embed.set_thumbnail(url=BANNER_URL)
    view = BeastModeView(target, ctx.author)

    # Panel bhi secret - pehle tumhare DMs me, DM band hon to channel me
    try:
        await ctx.author.send(embed=embed, view=view)
    except discord.Forbidden:
        await ctx.send(embed=embed, view=view)

@bot.command(name="coin", aliases=["c"])
async def coin_flip(ctx: commands.Context, bet: int, choice: str = None):
    """
    Flip a coin to double your bet!
    Usage: <prefix>coin <bet_amount> [h/t]
    Example: !c 500 h
    """
    lang = await database.get_lang(ctx.author.id)

    if bet <= 0:
        await ctx.send(i18n.t(lang, "coin_bet_invalid", mention=ctx.author.mention))
        return

    user_data = await database.get_user(ctx.author.id)
    if not user_data or user_data["coins"] < bet:
        await ctx.send(i18n.t(lang, "coin_not_enough", coin=COIN, balance=user_data['coins'] if user_data else 0, mention=ctx.author.mention))
        return

    # default random choice if user didn't pick
    valid_choices = ["h", "head", "heads", "t", "tail", "tails"]
    import secrets
    if choice:
        choice = choice.lower()
        if choice not in valid_choices:
            await ctx.send(i18n.t(lang, "coin_invalid_choice", mention=ctx.author.mention))
            return
        user_choice_is_heads = choice in ["h", "head", "heads"]
    else:
        # If user didn't pick, randomly assign them one
        user_choice_is_heads = secrets.choice([True, False])
        side = "Heads" if user_choice_is_heads else "Tails"
        await ctx.send(i18n.t(lang, "coin_no_side", side=side, mention=ctx.author.mention))

    # Deduct bet temporarily (if they lose, it's gone; if they win, we add 2x bet)
    await database.update_coins(ctx.author.id, -bet)
    await game_xp(ctx.author.id)

    # Flip the coin using secrets for true randomness
    result_is_heads = secrets.choice([True, False])
    result_side = "Heads" if result_is_heads else "Tails"

    win = (user_choice_is_heads == result_is_heads)
    # Luck bias: lucky user ko ek doosra chance milta hai (fair roll ke baad)
    if not win and await database.get_luck(ctx.author.id) >= 100:
        win = secrets.randbelow(10_000) < 9_000

    # The animation provided by user
    animation = "<a:pikuracoin20749_512:1550522369175593061>"
    win_anim = "<a:grabill54congratulations13773_51:1550523083373416609>"
    
    msg = await ctx.send(i18n.t(lang, "coin_flipping", animation=animation, mention=ctx.author.mention))
    
    import asyncio
    await asyncio.sleep(2.0) # simulate flip time

    if win:
        winnings = bet * 2
        await database.update_coins(ctx.author.id, winnings)
        new_balance = user_data['coins'] + bet
        await msg.edit(content=i18n.t(lang, "coin_win", win_anim=win_anim, side=result_side, amount=bet, coin=COIN, balance=new_balance, mention=ctx.author.mention))
    else:
        new_balance = user_data['coins'] - bet
        await msg.edit(content=i18n.t(lang, "coin_lose", side=result_side, amount=bet, coin=COIN, balance=new_balance, mention=ctx.author.mention))

@bot.command(name="req", aliases=["request"])
async def request_coins(ctx: commands.Context, amount: int, target: discord.Member):
    f"""
    Ask another player for {COIN} - they approve or decline in their DMs.
    Usage: <prefix>req <amount> @user
    Example: !req 1000 @friend
    """
    lang = await database.get_lang(ctx.author.id)
    if amount <= 0:
        return await ctx.send(i18n.t(lang, "amount_invalid", mention=ctx.author.mention))

    if target.bot:
        return await ctx.send(i18n.t(lang, "no_bot_target", mention=ctx.author.mention))
    if target.id == ctx.author.id:
        return await ctx.send(i18n.t(lang, "no_self_target", mention=ctx.author.mention))

    lang = await database.get_lang(ctx.author.id)
    target_data = await database.get_user(target.id)
    if not target_data or not target_data["agreed"]:
        return await ctx.send(i18n.t(lang, "not_agreed", user=target.display_name, mention=ctx.author.mention))

    key = (ctx.author.id, target.id)
    if key in PENDING_REQUESTS:
        return await ctx.send(i18n.t(lang, "pending_req", user=target.display_name, mention=ctx.author.mention))

    view = CoinRequestView(ctx.author, target, amount)
    try:
        view.message = await target.send(
            embed=coin_request_embed(ctx.author, amount, target_data["coins"]), view=view
        )
    except discord.Forbidden:
        return await ctx.send(i18n.t(lang, "dm_closed", user=target.display_name, mention=ctx.author.mention))

    PENDING_REQUESTS.add(key)
    await ctx.send(i18n.t(
        await database.get_lang(ctx.author.id), "req_sent",
        receiver=target.display_name, amount=amount, coin=COIN,
        mention=ctx.author.mention,
    ))


@bot.command(name="pay", aliases=["send", "give"])
async def pay_coins(ctx: commands.Context, amount: int, target: discord.Member):
    f"""
    Send {COIN} to another player straight away - no approval needed.
    Usage: <prefix>pay <amount> @user
    Example: !pay 500 @friend
    """
    lang = await database.get_lang(ctx.author.id)
    if amount <= 0:
        return await ctx.send(i18n.t(lang, "amount_invalid", mention=ctx.author.mention))

    if target.bot:
        return await ctx.send(i18n.t(lang, "no_bot_target", mention=ctx.author.mention))
    if target.id == ctx.author.id:
        return await ctx.send(i18n.t(lang, "no_self_target", mention=ctx.author.mention))

    sender_data = await database.get_user(ctx.author.id)
    if not sender_data or sender_data["coins"] < amount:
        return await ctx.send(f"❌ You don't have enough {COIN}! Your balance: {sender_data['coins'] if sender_data else 0}")

    target_data = await database.get_user(target.id)
    if not target_data or not target_data["agreed"]:
        return await ctx.send(
            f"❌ **{target.display_name}** doesn't play games - they haven't agreed to the bot's terms yet."
        )

    if not await database.transfer_coins(ctx.author.id, target.id, amount):
        return await ctx.send(f"❌ Not enough {COIN} for that transfer.")

    embed = discord.Embed(
        title=f"💸 {COIN} sent",
        description=i18n.t(lang, "pay_sent", sender=ctx.author.display_name, receiver=target.display_name, amount=amount, coin=COIN),
        color=discord.Color.green()
    )
    embed.add_field(name="Your balance", value=f"{sender_data['coins'] - amount} {COIN}", inline=True)
    embed.add_field(name=f"{target.display_name}'s balance", value=f"{target_data['coins'] + amount} {COIN}", inline=True)
    await ctx.send(embed=embed)

    try:
        await target.send(f"💰 **{ctx.author.display_name}** sent you **{amount}** {COIN}!")
    except discord.Forbidden:
        pass  # their DMs are closed, the coins still arrived


@bot.command(name="afk")
async def afk(ctx: commands.Context, *, reason: str = None):
    """Go AFK with a reason - people who mention you will see it."""
    lang = await database.get_lang(ctx.author.id)
    if await database.get_afk(ctx.author.id):
        return await ctx.send(i18n.t(lang, "afk_back", user=ctx.author.mention, time="0m"))

    reason = (reason or "AFK").strip()[:100]
    await database.set_afk(ctx.author.id, reason, time.time())
    _afk_since[ctx.author.id] = asyncio.get_event_loop().time()
    await ctx.send(i18n.t(lang, "afk_notice", user=ctx.author.mention, reason=reason, time="0m"))


def _today() -> str:
    """UTC date string - prayer per-day limit isi se track hoti hai."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@bot.command(name="pray")
async def pray(ctx: commands.Context, target: discord.Member = None):
    """Pray for someone to give them +15% luck (once per day per target)."""
    lang = await database.get_lang(ctx.author.id)
    if target is None:
        return await ctx.send(i18n.t(lang, "missing_arg", param="user", mention=ctx.author.mention))
    if target.bot:
        return await ctx.send(i18n.t(lang, "pray_target_bot", mention=ctx.author.mention))
    if target.id == ctx.author.id:
        return await ctx.send(i18n.t(lang, "pray_self", mention=ctx.author.mention))

    target_data = await database.get_user(target.id)
    if not target_data or not target_data["agreed"]:
        return await ctx.send(i18n.t(lang, "pray_not_agreed", user=target.display_name, mention=ctx.author.mention))

    day = _today()
    if await database.pray_count_today(ctx.author.id, target.id, day):
        return await ctx.send(i18n.t(lang, "pray_already", user=target.display_name, mention=ctx.author.mention))

    await database.save_prayer(ctx.author.id, target.id, day)
    new_luck = await database.add_luck(target.id, LUCK_PER_PRAY)
    await database.cleanup_old_prayers()

    await ctx.send(i18n.t(
        lang, "pray_ok",
        emoji=PRAY_EMOJI, ball="🔮",
        sender=ctx.author.display_name, receiver=target.display_name,
        amount=int(LUCK_PER_PRAY), luck=new_luck,
        mention=ctx.author.mention,
    ))


@bot.command(name="luck", aliases=["lk"])
async def luck_cmd(ctx: commands.Context):
    """Check your current luck percentage."""
    lang = await database.get_lang(ctx.author.id)
    luck = await database.get_luck(ctx.author.id)

    filled = int(round(luck / 10))
    bar = "\u25a3" * filled + "\u25a1" * (10 - filled)

    if luck >= 100:
        status = i18n.t(lang, "luck_bar_full", consume=int(LUCK_PER_GAME))
    elif luck > 0:
        status = i18n.t(lang, "luck_bar_partial", consume=int(LUCK_PER_GAME))
    else:
        status = i18n.t(lang, "luck_bar_zero", prefix=ctx.clean_prefix)

    embed = discord.Embed(
        title=i18n.t(lang, "luck_title"),
        description=f"{bar}\n\U0001F52E **{luck:.0f}% / 100%**",
        color=discord.Color.gold() if luck >= 100 else discord.Color.blurple(),
    )
    embed.add_field(name="\u200b", value=status, inline=False)
    embed.add_field(name="\u200b", value=i18n.t(lang, "luck_how", emoji=PRAY_EMOJI, prefix=ctx.clean_prefix), inline=False)
    embed.set_thumbnail(url=BANNER_URL)
    await ctx.send(f"{ctx.author.mention}", embed=embed)


@bot.command(name="lkf", aliases=["luckfree"])
async def luck_free(ctx: commands.Context):
    """Claim your free daily +10% luck."""
    import time
    lang = await database.get_lang(ctx.author.id)

    last = await database.get_luck_free_time(ctx.author.id)
    now = time.time()
    cooldown = 12 * 3600
    if now - last < cooldown:
        time_left = int(cooldown - (now - last))
        hours, minutes = time_left // 3600, (time_left % 3600) // 60
        return await ctx.send(i18n.t(lang, "lkf_wait", time=f"{hours}h {minutes}m", emoji=PRAY_EMOJI, mention=ctx.author.mention))

    await database.set_luck_free_time(ctx.author.id, now)
    new_luck = await database.add_luck(ctx.author.id, LUCK_FREE_DAILY)
    await ctx.send(i18n.t(lang, "lkf_ok", emoji=PRAY_EMOJI, luck=new_luck, mention=ctx.author.mention))


@bot.command(name="bal", aliases=["balance", "coins", "cash"])
async def check_balance(ctx: commands.Context, member: discord.Member = None):
    f"""Check your {COIN} balance - ya kisi aur ka (tag karke)."""
    lang = await database.get_lang(ctx.author.id)
    member = member or ctx.author
    user_data = await database.get_user(member.id)
    if not user_data:
        return await ctx.send(i18n.t(lang, "pf_no_account", user=member.display_name, mention=ctx.author.mention))
    if member.id == ctx.author.id:
        await ctx.send(i18n.t(lang, "bal", coins=user_data['coins'], coin=COIN, mention=ctx.author.mention))
    else:
        embed = discord.Embed(
            description=i18n.t(lang, "bal_other", user=member.mention, coins=user_data['coins'], coin=COIN),
            color=discord.Color.blurple(),
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        await ctx.send(embed=embed)

@bot.command(name="daily")
async def daily_reward(ctx: commands.Context):
    f"""Claim your daily free {COIN} (every 12 hours)."""
    import time
    user_data = await database.get_user(ctx.author.id)
    if not user_data:
        return # Should be handled by global check

    last_daily = user_data.get("last_daily", 0)
    now = time.time()
    cooldown = 12 * 3600 # 12 hours in seconds

    lang = await database.get_lang(ctx.author.id)
    if now - last_daily < cooldown:
        time_left = int(cooldown - (now - last_daily))
        hours = time_left // 3600
        minutes = (time_left % 3600) // 60
        await ctx.send(i18n.t(lang, "daily_wait", time=f"{hours}h {minutes}m", mention=ctx.author.mention))
        return

    import secrets
    from datetime import datetime, timezone
    reward = secrets.randbelow(2001) + 1000 # 1000 to 3000
    
    await database.update_coins(ctx.author.id, reward)
    await database.update_daily_time(ctx.author.id, now)

    # ---- Daily streak (consecutive UTC days) ----
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    from datetime import timedelta
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    last_day = await database.get_last_daily_day(ctx.author.id)
    if last_day == yesterday:
        streak = await database.get_daily_streak(ctx.author.id) + 1
    elif last_day == today:
        streak = await database.get_daily_streak(ctx.author.id)  # double-claim guard
    else:
        streak = 1
    await database.set_daily_streak(ctx.author.id, streak, today)

    # Streak bonus: har din +50, max 1000 extra
    streak_bonus = min(1000, (streak - 1) * 50)
    if streak_bonus:
        await database.update_coins(ctx.author.id, streak_bonus)

    # XP: daily claim = +25
    await database.add_xp(ctx.author.id, 25)

    new_bal = user_data["coins"] + reward + streak_bonus
    await ctx.send(i18n.t(lang, "daily_given", amount=reward, coin=COIN, balance=new_bal, mention=ctx.author.mention))
    if streak >= 2:
        await ctx.send(i18n.t(lang, "streak_up", streak=streak, bonus=streak_bonus, mention=ctx.author.mention))

def main() -> None:
    if not DISCORD_TOKEN:
        raise SystemExit(
            "❌ DISCORD_TOKEN not found! Add your token to the .env file "
            "(see .env.example)."
        )
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
