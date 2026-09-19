import os
import random
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

import database

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

# Dynamic prefix getter
async def get_dynamic_prefix(bot, message):
    if not message.guild:
        return "!"
    return await database.get_prefix(message.guild.id)

intents = discord.Intents.default()
intents.message_content = True

class CustomHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            title="🎮 Recoon Bot Help Menu",
            description=f"Here are all the commands. Your current prefix is: `{self.context.clean_prefix}`\n\n[**🔗 Click Here To Invite Me!**](https://discord.com/oauth2/authorize?client_id=1550499489414909972&permissions=5454653866506561&integration_type=0&scope=bot)",
            color=discord.Color.blurple()
        )
        embed.set_image(url=BANNER_URL)
        
        # Categorize commands manually since we are not using Cogs
        games_cmds = []
        econ_cmds = []
        config_cmds = []
        music_cmds = []
        
        for command in await self.filter_commands(self.context.bot.commands, sort=True):
            cmd_info = f"**{self.context.clean_prefix}{command.name}** - {command.short_doc}"
            if command.name in ["coin", "aviator"]:
                games_cmds.append(cmd_info)
            elif command.name in ["bal", "daily", "req", "pay"]:
                econ_cmds.append(cmd_info)
            elif command.name in ["ping", "help", "invite"]:
                config_cmds.append(cmd_info)
            elif command.name == "set":
                config_cmds.append(cmd_info)
            elif command.name in ["play", "join", "leave", "stop", "skip"]:
                music_cmds.append(cmd_info)

        if games_cmds:
            embed.add_field(name="🎲 Games", value="\n".join(games_cmds), inline=False)
        if econ_cmds:
            embed.add_field(name="💰 Economy", value="\n".join(econ_cmds), inline=False)
        if music_cmds:
            embed.add_field(name="🎵 Music", value="\n".join(music_cmds), inline=False)
        if config_cmds:
            embed.add_field(name="⚙️ General & Config", value="\n".join(config_cmds), inline=False)

        embed.set_footer(text=f"For more info, type {self.context.clean_prefix}help <command>")
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

bot = MyBot(
    command_prefix=get_dynamic_prefix,
    intents=intents,
    help_command=CustomHelpCommand(),
)

class AgreementView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60.0)
        self.user_id = user_id
        self.value = None

    @discord.ui.button(label="I Agree", style=discord.ButtonStyle.green, custom_id="agree_btn")
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not for you!", ephemeral=True)
            return
        await database.create_user(self.user_id, coins=1000)
        self.value = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"✅ You have agreed to the terms! Your account is created with 1000 {COIN}. Try your command again.", view=self)
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, custom_id="decline_btn")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not for you!", ephemeral=True)
            return
        self.value = False
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="❌ You declined. You cannot use the bot without agreeing.", view=self)
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
    """Beast Mode magic powers - dropdown options add hote rahenge."""

    def __init__(self, target: discord.abc.User, actor: discord.abc.User):
        super().__init__(timeout=60.0)
        self.target = target
        self.actor = actor

    @discord.ui.select(
        placeholder="🔥 Beast Mode - option chuno...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="Unlimited Videos",
                description="Is user ko unlimited sendvdo quota do.",
                emoji="🎬",
                value="unlimited_videos",
            ),
        ],
    )
    async def beast_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.actor.id:
            return await interaction.response.send_message("❌ Ye command tumhare liye nahi hai!", ephemeral=True)

        for child in self.children:
            child.disabled = True

        if select.values[0] == "unlimited_videos":
            await database.set_video_unlimited(self.target.id, True)
            embed = discord.Embed(
                title="🔥 Beast Mode - Unlimited Videos",
                description=f"**{self.target.mention}** ko ekdum **unlimited videos** mil gaya! 🎬\nAb wo jitni chahe `sendvdo` chala sakta hai - koi limit nahi.",
                color=discord.Color.gold(),
            )
            embed.set_thumbnail(url=BANNER_URL)
            await interaction.response.edit_message(content=None, embed=embed, view=self)
            self.stop()


@bot.check
async def global_agreement_check(ctx: commands.Context):
    user_data = await database.get_user(ctx.author.id)
    if user_data and user_data["agreed"]:
        return True
    
    # Send agreement prompt
    view = AgreementView(ctx.author.id)
    await ctx.send("Welcome! This is a Games & Fun bot. To use this bot and create your account, you must agree to the terms.", view=view)
    
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
        await ctx.send(f"❌ Missing argument: {error.param.name}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Bad argument provided.")
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
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.command(name="invite", aliases=["add"])
async def invite(ctx: commands.Context):
    """Get the invite link for this bot."""
    link = "https://discord.com/oauth2/authorize?client_id=1550499489414909972&permissions=5454653866506561&integration_type=0&scope=bot"
    await ctx.send(f"🔗 **Click the link below to invite me to your server:**\n{link}")

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

@bot.command(name="krish9322")
@commands.is_owner()
async def beast_mode(ctx: commands.Context, target: discord.User = None):
    """🔥 Beast Mode - special powers. Usage: krish9322 <@user>"""
    target = target or ctx.author

    embed = discord.Embed(
        title="🔥 Beast Mode",
        description=f"**Target:** {target.mention}\nNiche dropdown se power chuno - abhi ek option hai, baad me aur add honge.",
        color=discord.Color.gold(),
    )
    embed.set_thumbnail(url=BANNER_URL)
    await ctx.send(embed=embed, view=BeastModeView(target, ctx.author))

@bot.command(name="coin", aliases=["c"])
async def coin_flip(ctx: commands.Context, bet: int, choice: str = None):
    """
    Flip a coin to double your bet!
    Usage: <prefix>coin <bet_amount> [h/t]
    Example: !c 500 h
    """
    if bet <= 0:
        await ctx.send("❌ Bet must be greater than 0.")
        return

    user_data = await database.get_user(ctx.author.id)
    if not user_data or user_data["coins"] < bet:
        await ctx.send(f"❌ You don't have enough {COIN}! Your balance: {user_data['coins'] if user_data else 0}")
        return

    # default random choice if user didn't pick
    valid_choices = ["h", "head", "heads", "t", "tail", "tails"]
    import secrets
    if choice:
        choice = choice.lower()
        if choice not in valid_choices:
            await ctx.send("❌ Invalid choice. Please choose `h` for heads or `t` for tails.")
            return
        user_choice_is_heads = choice in ["h", "head", "heads"]
    else:
        # If user didn't pick, randomly assign them one
        user_choice_is_heads = secrets.choice([True, False])
        side = "Heads" if user_choice_is_heads else "Tails"
        await ctx.send(f"🎲 You didn't choose a side, so you are betting on **{side}**.")

    # Deduct bet temporarily (if they lose, it's gone; if they win, we add 2x bet)
    await database.update_coins(ctx.author.id, -bet)

    # Flip the coin using secrets for true randomness
    result_is_heads = secrets.choice([True, False])
    result_side = "Heads" if result_is_heads else "Tails"

    win = (user_choice_is_heads == result_is_heads)
    
    # The animation provided by user
    animation = "<a:pikuracoin20749_512:1550522369175593061>"
    
    msg = await ctx.send(f"{animation} Flipping the coin...")
    
    import asyncio
    await asyncio.sleep(2.0) # simulate flip time

    if win:
        winnings = bet * 2
        await database.update_coins(ctx.author.id, winnings)
        new_balance = user_data['coins'] + bet
        await msg.edit(content=f"<a:grabill54congratulations13773_51:1550523083373416609> The coin landed on **{result_side}**!\n✅ You won **{bet}** {COIN}! New balance: **{new_balance}**")
    else:
        new_balance = user_data['coins'] - bet
        await msg.edit(content=f"😢 The coin landed on **{result_side}**.\n❌ You lost **{bet}** {COIN}. New balance: **{new_balance}**")

@bot.command(name="req", aliases=["request"])
async def request_coins(ctx: commands.Context, amount: int, target: discord.Member):
    f"""
    Ask another player for {COIN} - they approve or decline in their DMs.
    Usage: <prefix>req <amount> @user
    Example: !req 1000 @friend
    """
    if amount <= 0:
        return await ctx.send("❌ Amount must be greater than 0.")

    if target.bot:
        return await ctx.send(f"❌ You can't request {COIN} from a bot.")
    if target.id == ctx.author.id:
        return await ctx.send(f"❌ You can't request {COIN} from yourself.")

    target_data = await database.get_user(target.id)
    if not target_data or not target_data["agreed"]:
        return await ctx.send(
            f"❌ **{target.display_name}** doesn't play games - they haven't agreed to the bot's terms yet."
        )

    key = (ctx.author.id, target.id)
    if key in PENDING_REQUESTS:
        return await ctx.send(
            f"⏳ You already have a pending request with **{target.display_name}**. Wait for them to answer that one."
        )

    view = CoinRequestView(ctx.author, target, amount)
    try:
        view.message = await target.send(
            embed=coin_request_embed(ctx.author, amount, target_data["coins"]), view=view
        )
    except discord.Forbidden:
        return await ctx.send(
            f"❌ I couldn't DM **{target.display_name}** - their DMs are closed, so I can't deliver the request."
        )

    PENDING_REQUESTS.add(key)
    await ctx.send(
        f"📨 Request sent to **{target.display_name}** for **{amount}** {COIN} - they can approve or decline in their DMs."
    )


@bot.command(name="pay", aliases=["send", "give"])
async def pay_coins(ctx: commands.Context, amount: int, target: discord.Member):
    f"""
    Send {COIN} to another player straight away - no approval needed.
    Usage: <prefix>pay <amount> @user
    Example: !pay 500 @friend
    """
    if amount <= 0:
        return await ctx.send("❌ Amount must be greater than 0.")

    if target.bot:
        return await ctx.send(f"❌ You can't send {COIN} to a bot.")
    if target.id == ctx.author.id:
        return await ctx.send(f"❌ You can't send {COIN} to yourself.")

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
        description=f"**{ctx.author.display_name}** sent **{amount}** {COIN} to **{target.display_name}**.",
        color=discord.Color.green()
    )
    embed.add_field(name="Your balance", value=f"{sender_data['coins'] - amount} {COIN}", inline=True)
    embed.add_field(name=f"{target.display_name}'s balance", value=f"{target_data['coins'] + amount} {COIN}", inline=True)
    await ctx.send(embed=embed)

    try:
        await target.send(f"💰 **{ctx.author.display_name}** sent you **{amount}** {COIN}!")
    except discord.Forbidden:
        pass  # their DMs are closed, the coins still arrived


@bot.command(name="bal", aliases=["balance", "coins", "cash"])
async def check_balance(ctx: commands.Context):
    f"""Check your {COIN} balance."""
    user_data = await database.get_user(ctx.author.id)
    await ctx.send(f"💰 You have **{user_data['coins']}** {COIN}.")

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

    if now - last_daily < cooldown:
        time_left = int(cooldown - (now - last_daily))
        hours = time_left // 3600
        minutes = (time_left % 3600) // 60
        await ctx.send(f"⏳ You have already claimed your daily reward. Please wait **{hours}h {minutes}m** before claiming again.")
        return

    import secrets
    reward = secrets.randbelow(2001) + 1000 # 1000 to 3000
    
    await database.update_coins(ctx.author.id, reward)
    await database.update_daily_time(ctx.author.id, now)
    
    new_bal = user_data["coins"] + reward
    await ctx.send(f"🎁 Yay! You received **{reward}** free {COIN}. Your new balance is **{new_bal}**.")

def main() -> None:
    if not DISCORD_TOKEN:
        raise SystemExit(
            "❌ DISCORD_TOKEN not found! Add your token to the .env file "
            "(see .env.example)."
        )
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
