import asyncio
import io
import os
import time
from datetime import datetime, timezone

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import database
import i18n

# Banner image URL (Discord CDN)
BANNER_URL = "https://cdn.discordapp.com/emojis/1550526211388612608.png?size=512"
COIN = "<:coin:1550545065397584066>"

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
CARD_W, CARD_H = 1000, 520
PANEL_TOP = 310  # iske niche solid stats panel hai - banner area lamba (details ke liye)
CARD_QUALITY = 88  # JPG quality (chhoti file, achha look)

# Custom banners (repo me shipped) - (name, price, file_path, source_url)
# url = emoji/banner ka direct CDN link (shop preview + profile card render ke liye)
URLS = {
    "recoon":   "https://cdn.discordapp.com/emojis/1550526211388612608.png?size=512",
    "mystery":  "https://cdn.discordapp.com/emojis/1550904280897159188.png?size=512",
    "blue":     "https://cdn.discordapp.com/emojis/1550904299213557790.png?size=512",
    "aureus":   "https://cdn.discordapp.com/emojis/1550913740550049883.png?size=512",
    "crimson":  "https://cdn.discordapp.com/emojis/1550913713991585973.png?size=512",
    "skyline":  "https://cdn.discordapp.com/emojis/1550913672241746020.png?size=512",
    "verdant":  "https://cdn.discordapp.com/emojis/1550913632228081695.png?size=512",
    "ember":    "https://cdn.discordapp.com/emojis/1550913597431873676.png?size=512",
    "oceanic":  "https://cdn.discordapp.com/emojis/1550913476749295716.png?size=512",
    "aurora":   "https://cdn.discordapp.com/emojis/1550913434542149733.gif?size=512",
    "sapphire": "https://cdn.discordapp.com/emojis/1550913413499195432.png?size=512",
    "noir":     "https://cdn.discordapp.com/emojis/1550913448827682826.png?size=512",
}

CUSTOM_BANNERS = [
    ("Recoon",   100,   "banner_images/banner_emote.png",    URLS["recoon"]),
    ("Mystery",  5000,  "banner_images/banner_mystery.png",  URLS["mystery"]),
    ("Blue",     10000, "banner_images/banner_blue.png",     URLS["blue"]),
    ("Aureus",   3000,  "banner_images/banner_911.png",      URLS["aureus"]),
    ("Crimson",  3000,  "banner_images/banner_301.png",      URLS["crimson"]),
    ("Skyline",  3000,  "banner_images/banner_159.png",      URLS["skyline"]),
    ("Verdant",  3000,  "banner_images/banner_422.png",      URLS["verdant"]),
    ("Ember",    3000,  "banner_images/banner_1.png",        URLS["ember"]),
    ("Oceanic",  3000,  "banner_images/banner_563.png",      URLS["oceanic"]),
    ("Aurora",   7500,  "banner_images/banner_150.gif",      URLS["aurora"]),
    ("Sapphire", 7500,  "banner_images/banner_113.png",      URLS["sapphire"]),
    ("Noir",     7500,  "banner_images/banner__.png",        URLS["noir"]),
]

# URL-banners ka PIL render cache: {url: Image.Image} - har card render par download na ho
_URL_IMG_CACHE = {}


def _load_image_from_url(url: str):
    """URL se image download/render karo (cache ke saath). None = fail."""
    if url in _URL_IMG_CACHE:
        return _URL_IMG_CACHE[url]
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        _URL_IMG_CACHE[url] = img
        return img
    except Exception:
        return None


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _hex(c: str):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def render_gradient(w: int, h: int, spec: str) -> Image.Image:
    """'c1|c2|c3' hex spec se smooth vertical gradient image."""
    colors = [_hex(c) for c in spec.split("|")]
    img = Image.new("RGB", (w, h))
    dr = ImageDraw.Draw(img)
    stops = len(colors) - 1
    for y in range(h):
        t = y / max(1, h - 1) * stops
        seg = min(stops - 1, int(t))
        dr.line([(0, y), (w, y)], fill=_lerp(colors[seg], colors[seg + 1], t - seg))
    return img


def banner_image(banner: dict, w: int = CARD_W, h: int = CARD_H):
    """Banner row -> PIL Image (url / file / gradient).

    URL/file banners: blurred cover background + height-fit sharp image centered
    in the visible (top) area - chhoti/wide images bhi achhi dikhti hain.
    """
    source = None
    if banner and banner.get("url"):
        source = _load_image_from_url(banner["url"])
    if source is None and banner and banner.get("file_path") and os.path.exists(banner["file_path"]):
        try:
            source = Image.open(banner["file_path"]).convert("RGBA")
        except Exception:
            source = None
    if source is not None:
        try:
            img = source.resize((w, h)).filter(ImageFilter.GaussianBlur(16))
            # Foreground: height fit to visible banner area, centered (wide image puri dikhe)
            scale = PANEL_TOP / source.height
            fg_w = max(1, int(source.width * scale))
            fg = source.resize((fg_w, PANEL_TOP))
            x = (w - fg_w) // 2
            img.paste(fg, (x, 0), fg if fg.mode == "RGBA" else None)
            return img
        except Exception:
            pass
    spec = (banner or {}).get("gradient") or "0f0c29|302b63|24243e"
    return render_gradient(w, h, spec)


def avatar_bytes(avatar_url: str) -> bytes:
    import urllib.request
    req = urllib.request.Request(avatar_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read()


def render_profile_card(
    display_name: str,
    avatar_url: str,
    level: int,
    rank: int,
    coins: int,
    streak: int,
    luck: float,
    created_ts: float,
    about_me: str,
    banner: dict,
    texts: dict,
) -> bytes:
    """owo-style profile card -> JPG bytes.

    texts = card ke labels (translated): xp_lbl, rank_lbl, coins_lbl,
    streak_lbl, luck_lbl, about_lbl, joined_lbl
    """
    img = banner_image(banner).convert("RGB")

    # Dark overlay taaki text readable rahe (owo jaisa translucent panel)
    overlay = Image.new("RGBA", img.size, (10, 10, 14, 150))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)

    # Neeche wala solid panel (stats ka area)
    dr = ImageDraw.Draw(img)
    panel_top = PANEL_TOP
    dr.rectangle([0, panel_top, CARD_W, CARD_H], fill=(15, 15, 22, 235))

    # ---------------- Avatar circle ----------------
    AV = 170
    ax, ay = 40, 40
    try:
        raw = Image.open(io.BytesIO(avatar_bytes(avatar_url))).convert("RGB").resize((AV, AV))
    except Exception:
        raw = Image.new("RGB", (AV, AV), (40, 40, 50))
    mask = Image.new("L", (AV * 4, AV * 4), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, AV * 4, AV * 4], fill=255)
    mask = mask.resize((AV, AV))
    # orange ring
    ring = Image.new("RGBA", (AV + 12, AV + 12), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse([0, 0, AV + 12, AV + 12], fill=(255, 140, 40, 255))
    img.paste(ring, (ax - 6, ay - 6), ring)
    img.paste(raw, (ax, ay), mask)

    # ---------------- Name + level ----------------
    f_name = _font(52, bold=True)
    f_big = _font(64, bold=True)
    f_med = _font(30, bold=True)
    f_small = _font(24)
    f_tiny = _font(21)

    name = display_name[:20]
    tw = dr.textlength(name, font=f_name)
    # Name avatar ke right me
    img.paste(img, (0, 0))  # no-op keeps type checkers calm
    dr = ImageDraw.Draw(img)
    nx, ny = ax + AV + 30, 52
    dr.text((nx, ny), name, font=f_name, fill=(255, 255, 255))

    # Level big number
    lv_txt = str(level)
    dr.text((nx, ny + 66), f"{texts.get('level_lbl', 'Level')}", font=f_med, fill=(180, 180, 190))
    dr.text((nx + 110, ny + 52), lv_txt, font=f_big, fill=(255, 255, 255))

    # ---------------- XP bar (owO style: name level ke niche) ----------------
    xp = texts.get("xp_val", "")
    bar_x, bar_y, bar_w, bar_h = nx, ny + 118, 520, 22
    dr.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=11, fill=(60, 60, 70), outline=(90, 90, 100), width=2)
    # xp_val = "15467 / 35625" jaisa "cur/total"
    try:
        cur_s, tot_s = xp.split("/")
        cur, tot = float(cur_s), max(1.0, float(tot_s))
        frac = max(0.0, min(1.0, cur / tot))
    except Exception:
        frac = 0.0
    if frac > 0:
        dr.rounded_rectangle([bar_x, bar_y, bar_x + int(bar_w * frac), bar_y + bar_h], radius=11, fill=(120, 190, 90))
    rank_txt = f"{texts.get('rank_lbl', 'Rank')}: #{rank}"
    dr.text((bar_x + bar_w + 25, bar_y - 6), rank_txt, font=f_med, fill=(255, 255, 255))

    # XP hint line: level up ke liye kitna bacha hai
    hint = texts.get("xp_left", "")
    if hint:
        dr.text((bar_x, bar_y + bar_h + 8), hint, font=f_tiny, fill=(160, 200, 255))

    # ---------------- Bottom stats panel ----------------
    sy = panel_top + 34
    coin_name = texts.get("coin_txt", "")
    stats = [
        (texts.get("coins_lbl", "Balance"), f"{coins} {coin_name}"),
        (texts.get("streak_lbl", "Daily Streak"), f"{streak}"),
        (texts.get("luck_lbl", "Luck"), f"{luck:.0f}%"),
    ]
    col_w = CARD_W // 3
    for i, (lbl, val) in enumerate(stats):
        cx = col_w * i + 40
        dr.text((cx, sy), lbl.upper(), font=f_small, fill=(150, 150, 160))
        dr.text((cx, sy + 36), val, font=f_med, fill=(255, 255, 255))

    # Join date (right side)
    joined = datetime.fromtimestamp(created_ts, tz=timezone.utc).strftime("%d %b %Y")
    j_txt = f"{texts.get('joined_lbl', 'Joined')}: {joined}"
    jw = dr.textlength(j_txt, font=f_small)
    dr.text((CARD_W - jw - 40, CARD_H - 44), j_txt, font=f_small, fill=(170, 170, 180))

    # About me (left-bottom)
    about = (about_me or "").strip() or texts.get("about_default", "...")
    dr.text((40, CARD_H - 96), texts.get("about_lbl", "About me"), font=f_small, fill=(150, 150, 160))
    dr.text((40, CARD_H - 62), about[:60], font=f_tiny, fill=(230, 230, 235))

    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=CARD_QUALITY)
    buf.seek(0)
    return buf.getvalue()


# ---------------- Discord commands ----------------

class LeaderboardView(discord.ui.View):
    """Dropdown wala leaderboard - har category ka top 10."""

    MEDALS = {"1": "🥇", "2": "🥈", "3": "🥉"}

    def __init__(self, ctx: commands.Context, lang: str):
        super().__init__(timeout=120.0)
        self.ctx = ctx
        self.lang = lang
        self.message = None
        self._name_cache = {}  # uid -> display name (fetch ek hi baar)

    async def _display_name(self, uid: int) -> str:
        if uid in self._name_cache:
            return self._name_cache[uid]
        name = None
        guild = self.ctx.guild
        if guild:
            member = guild.get_member(uid)
            if member is None:
                try:
                    member = await guild.fetch_member(uid)  # cache me nahi to REST se
                except (discord.NotFound, discord.HTTPException):
                    member = None
            if member:
                name = member.display_name
        if not name:
            name = i18n.t(self.lang, "lb_unknown_user", mention=f"<@{uid}>")
        self._name_cache[uid] = name
        return name

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                i18n.t(self.lang, "lb_not_yours", mention=interaction.user.mention), ephemeral=True
            )
            return False
        return True

    @discord.ui.select(
        placeholder="🏆 Choose a leaderboard...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Level", value="level", description="Highest level players", emoji="🏆"),
            discord.SelectOption(label="Coins", value="coins", description="Richest players", emoji="💰"),
            discord.SelectOption(label="Streak", value="streak", description="Longest daily streaks", emoji="🔥"),
            discord.SelectOption(label="Games (7d)", value="games", description="Most games in the last 7 days", emoji="🎮"),
        ],
    )
    async def category_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        key = select.values[0]
        embed = await self.build_embed(key)
        await interaction.response.edit_message(embed=embed, view=self)

    async def build_embed(self, key: str) -> discord.Embed:
        lang = self.lang
        title = i18n.t(lang, f"lb_title_{key}")
        embed = discord.Embed(title=title, color=discord.Color.gold())
        embed.set_thumbnail(url=BANNER_URL)

        if key == "games":
            data = await database.get_all_games_7d()
            rows = sorted(data.items(), key=lambda kv: kv[1], reverse=True)[:10]
            entries = [(uid, n) for uid, n in rows]
            fmt = lambda v: i18n.t(lang, "lb_games_val", n=v)
        elif key == "coins":
            entries = await database.get_top_coins(10)
            fmt = lambda v: f"{v} {COIN}"
        elif key == "streak":
            entries = await database.get_top_streaks(10)
            fmt = lambda v: i18n.t(lang, "lb_streak_val", n=v)
        else:  # level
            entries = await database.get_top_xp(10)
            entries = [(uid, database.level_from_xp(xp)) for uid, xp in entries]
            fmt = lambda v: i18n.t(lang, "lb_level_val", n=v)

        if not entries:
            embed.description = i18n.t(lang, "lb_empty")
            return embed

        lines = []
        for i, (uid, val) in enumerate(entries, start=1):
            name = await self._display_name(uid)
            medal = self.MEDALS.get(str(i), f"`#{i}`")
            lines.append(f"{medal} **{name}** — {fmt(val)}")
        embed.description = "\n".join(lines)
        embed.set_footer(text=i18n.t(lang, "lb_footer", prefix=self.ctx.clean_prefix))
        return embed

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass


class ShopView(discord.ui.View):
    """Dropdown se shop ke sections switch karo - banners/animals/food/abilities."""

    SECTIONS = [
        ("banners", "bs_title", "🖼️"),
        ("animals", "an_shop_animals", "🐾"),
        ("food", "an_shop_food", "🍖"),
        ("abilities", "an_shop_abilities", "⚡"),
    ]

    def __init__(self, ctx: commands.Context, lang: str, cog, current: str = "banners"):
        super().__init__(timeout=120.0)
        self.ctx = ctx
        self.lang = lang
        self.cog = cog
        self.message = None
        # Har instance ke liye FRESH options (default highlight current section)
        self.shop_select.options = [
            discord.SelectOption(
                label=i18n.t(lang, key)[:100], value=value, emoji=emoji,
                default=(value == current),
            )
            for value, key, emoji in self.SECTIONS
        ]

    @discord.ui.select(
        placeholder="📂 Section chuno...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Banners", value="banners", emoji="🖼️"),
            discord.SelectOption(label="Animals", value="animals", emoji="🐾"),
            discord.SelectOption(label="Food", value="food", emoji="🍖"),
            discord.SelectOption(label="Abilities", value="abilities", emoji="⚡"),
        ],
    )
    async def shop_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(i18n.t("en", "not_for_you"), ephemeral=True)
        section = select.values[0]
        for opt in self.shop_select.options:
            opt.default = (opt.value == section)
        # Icon downloads block kar sakte hain - pehle ACK, phir edit
        await interaction.response.defer()
        try:
            embed, file = await self.cog.shop_payload(self.ctx, self.lang, section)
            if file:
                await interaction.followup.edit_message(
                    interaction.message.id, embed=embed, view=self,
                    files=[file], attachments=[])
            else:
                await interaction.followup.edit_message(
                    interaction.message.id, embed=embed, view=self, attachments=[])
        except discord.HTTPException:
            pass

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass


class Profile(commands.Cog):
    """Profile card + banner store."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="profile", aliases=["pf"])
    async def profile(self, ctx: commands.Context, member: discord.Member = None):
        """owo-style profile card - apna ya kisi aur ka."""
        member = member or ctx.author
        lang = await database.get_lang(ctx.author.id)

        user = await database.get_user(member.id)
        if not user:
            return await ctx.send(i18n.t(lang, "pf_no_account", user=member.display_name, mention=ctx.author.mention))

        xp = user["xp"]
        level = database.level_from_xp(xp)
        cur_base = database.xp_for_level(level)
        next_base = database.xp_for_level(level + 1)
        # Progress: current level ke andar ka XP vs next level tak ka gap
        in_level = xp - cur_base
        need = max(1, next_base - cur_base)
        left = max(0, next_base - xp)
        xp_val = f"{in_level} / {need}"

        banner = await database.get_equipped_banner(member.id)
        texts = {
            "level_lbl": i18n.t(lang, "pc_level"),
            "rank_lbl": i18n.t(lang, "pc_rank"),
            "coins_lbl": i18n.t(lang, "pc_coins"),
            "streak_lbl": i18n.t(lang, "pc_streak"),
            "luck_lbl": i18n.t(lang, "pc_luck"),
            "about_lbl": i18n.t(lang, "pc_about"),
            "about_default": i18n.t(lang, "pc_about_default"),
            "joined_lbl": i18n.t(lang, "pc_joined"),
            "xp_val": xp_val,
            "xp_left": i18n.t(lang, "pc_xp_left", left=left),
            "coin_txt": "\U0001FA99",
        }

        async with ctx.typing():
            rank = await database.get_rank(member.id)
            created_ts = await database.get_created_at(member.id)
            try:
                jpg = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: render_profile_card(
                        display_name=member.display_name,
                        avatar_url=member.display_avatar.replace(size=256, format="png").url,
                        level=level,
                        rank=rank,
                        coins=user["coins"],
                        streak=user["daily_streak"],
                        luck=user["luck"],
                        created_ts=created_ts,
                        about_me=user["about_me"],
                        banner=banner,
                        texts=texts,
                    ),
                )
            except Exception as e:
                print(f"Profile render error: {e}")
                return await ctx.send(i18n.t(lang, "pf_render_fail", mention=ctx.author.mention))

        f = discord.File(io.BytesIO(jpg), filename="profile.jpg")
        await ctx.send(file=f)

    @commands.command(name="top", aliases=["lb", "leaderboard"])
    async def top(self, ctx: commands.Context):
        """Leaderboard - dropdown se category chuno (level/coins/streak/games 7d)."""
        lang = await database.get_lang(ctx.author.id)
        view = LeaderboardView(ctx, lang)
        msg = await ctx.send(embed=await view.build_embed("level"), view=view)
        view.message = msg

    @commands.command(name="shop", aliases=["banners", "astore"])
    async def banners(self, ctx: commands.Context, section: str = None):
        """Unified shop - dropdown se banners/animals/food/abilities switch karo."""
        lang = await database.get_lang(ctx.author.id)
        section = (section or "banners").lower()
        if section in ("animal",):
            section = "animals"
        if section in ("ability",):
            section = "abilities"
        if section not in ("banners", "animals", "food", "abilities"):
            section = "banners"
        from animals import render_collection_card_async
        embed, file = await self.shop_payload(ctx, lang, section, render_collection_card_async)
        view = ShopView(ctx, lang, self, section)
        if file:
            msg = await ctx.send(file=file, embed=embed, view=view)
        else:
            msg = await ctx.send(embed=embed, view=view)
        view.message = msg

    async def shop_payload(self, ctx, lang, section: str, render_fn=None):
        """(embed, file|None) - animals/food/abilities image card ke saath (bade icons).
        render_fn async ho sakta hai (thread me chalta hai) - loop block na ho."""
        from animals import FOODS, ABILITIES
        if render_fn is None:
            from animals import render_collection_card as render_fn_sync
            async def render_fn(t, s, f):
                return render_fn_sync(t, s, f)
        if section == "animals":
            species = [s for s in await database.get_all_species() if s["in_store"]]
            cells = [{"emoji": s["emoji"], "count": f"#{i}", "star": False}
                     for i, s in enumerate(species, 1)]
            title = i18n.t(lang, "an_shop_animals")
            buf = await render_fn(
                title,
                [{"label": i18n.t(lang, "an_shop_rarity_line"), "cells": cells}],
                i18n.t(lang, "an_shop_buy", prefix=ctx.clean_prefix),
            )
            embed = discord.Embed(title=title, color=discord.Color.orange())
            embed.set_image(url="attachment://shop.png")
            return embed, discord.File(buf, "shop.png")
        if section == "food":
            title = i18n.t(lang, "an_shop_food")
            cells = [{"emoji": f["emoji"], "count": str(f["price"]), "star": False}
                     for f in FOODS.values()]
            buf = await render_fn(
                title,
                [{"label": i18n.t(lang, "an_shop_price_line"), "cells": cells}],
                i18n.t(lang, "an_shop_buy", prefix=ctx.clean_prefix),
            )
            embed = discord.Embed(title=title, color=discord.Color.red())
            embed.set_image(url="attachment://shop.png")
            return embed, discord.File(buf, "shop.png")
        if section == "abilities":
            title = i18n.t(lang, "an_shop_abilities")
            cells = [{"emoji": a["emoji"], "count": str(a["price"]), "star": False}
                     for a in ABILITIES.values()]
            buf = await render_fn(
                title,
                [{"label": i18n.t(lang, "an_shop_price_line"), "cells": cells}],
                i18n.t(lang, "an_shop_buy", prefix=ctx.clean_prefix),
            )
            embed = discord.Embed(title=title, color=discord.Color.blurple())
            embed.set_image(url="attachment://shop.png")
            return embed, discord.File(buf, "shop.png")
        return await self._banner_embed(ctx, lang), None

    async def _banner_embed(self, ctx, lang):
        all_b = await database.get_all_banners()
        owned = {b["id"] for b in await database.get_owned_banners(ctx.author.id)}

        embed = discord.Embed(
            title=i18n.t(lang, "bs_title"),
            description=i18n.t(lang, "bs_desc", prefix=ctx.clean_prefix, coin=COIN)
            + "\n\n" + i18n.t(lang, "an_shop_hint", prefix=ctx.clean_prefix),
            color=discord.Color.purple(),
        )
        for b in all_b:
            price = f"{b['price']} {COIN}"
            if b["id"] in owned:
                status = i18n.t(lang, "bs_owned")
            else:
                status = price
            preview = i18n.t(lang, "bs_preview", url=b["url"]) if b.get("url") else ""
            # gradient preview strip
            grad = (b.get("gradient") or "0f0c29|302b63|24243e").replace("|", " ")
            embed.add_field(
                name=f"#{b['id']} {b['name']}",
                value=f"{status}\n{preview}\n`{grad}` — `{ctx.clean_prefix}buy banner {b['id']}`".strip(),
                inline=False,
            )
        embed.set_thumbnail(url=BANNER_URL)
        embed.set_footer(text=i18n.t(lang, "bs_footer", prefix=ctx.clean_prefix))
        return embed

    @commands.command(name="buy")
    async def buy(self, ctx: commands.Context, item: str = None, ref=None):
        """Buy: wbuy banner <id> | wbuy animal <#> | wbuy food <name> | wbuy ability <name>"""
        lang = await database.get_lang(ctx.author.id)
        item = (item or "").lower()

        # Shortcut: wbuy <food|ability-name>  (hotdog, pizza, lightning, ...)
        from animals import FOODS as _FOODS, ABILITIES as _ABILITIES
        if item in _FOODS:
            from animals import handle_buy
            return await handle_buy(ctx, lang, "food", item)
        if item in _ABILITIES:
            from animals import handle_buy
            return await handle_buy(ctx, lang, "ability", item)

        # Shortcut: wbuy <number> = animal store index (banners ko banner likhna zaroori)
        if item.isdigit() and ref is None:
            from animals import handle_buy
            return await handle_buy(ctx, lang, "animal", item)

        if item in ("animal", "food", "ability"):
            from animals import handle_buy
            return await handle_buy(ctx, lang, item, ref)
        if item != "banner" or ref is None:
            return await ctx.send(i18n.t(lang, "bs_usage", prefix=ctx.clean_prefix, mention=ctx.author.mention))
        banner_id = ref
        try:
            banner_id = int(banner_id)
        except (TypeError, ValueError):
            return await ctx.send(i18n.t(lang, "bs_usage", prefix=ctx.clean_prefix, mention=ctx.author.mention))

        banner = await database.get_banner(banner_id)
        if not banner:
            return await ctx.send(i18n.t(lang, "bs_not_found", mention=ctx.author.mention))

        result = await database.buy_banner(ctx.author.id, banner_id, banner["price"])
        if result == "owned":
            return await ctx.send(i18n.t(lang, "bs_already", name=banner["name"], mention=ctx.author.mention))
        if result == "poor":
            user = await database.get_user(ctx.author.id)
            return await ctx.send(i18n.t(lang, "m_poor", coin=COIN, balance=user["coins"] if user else 0, mention=ctx.author.mention))

        await database.add_xp(ctx.author.id, 10)
        await ctx.send(i18n.t(lang, "bs_bought", name=banner["name"], price=banner["price"], coin=COIN, prefix=ctx.clean_prefix, mention=ctx.author.mention))

    @commands.command(name="equipb", aliases=["banner"])
    async def banner(self, ctx: commands.Context, banner_id: int = None):
        """Equip banner: !equipb <id> (bina id = current banner dikhao)."""
        lang = await database.get_lang(ctx.author.id)

        if banner_id is None:
            cur = await database.get_equipped_banner(ctx.author.id)
            if cur:
                return await ctx.send(i18n.t(lang, "bs_current", name=cur["name"], id=cur["id"], mention=ctx.author.mention))
            return await ctx.send(i18n.t(lang, "bs_none", prefix=ctx.clean_prefix, mention=ctx.author.mention))

        if not await database.owns_banner(ctx.author.id, banner_id):
            return await ctx.send(i18n.t(lang, "bs_not_owned", prefix=ctx.clean_prefix, mention=ctx.author.mention))

        await database.equip_banner(ctx.author.id, banner_id)
        b = await database.get_banner(banner_id)
        await ctx.send(i18n.t(lang, "bs_equipped", name=b["name"], mention=ctx.author.mention))

    @commands.command(name="addbanner")
    @commands.is_owner()
    async def add_banner(self, ctx: commands.Context, name: str = None, price: int = None):
        """(Owner) Attach ki hui image se naya banner add karo: !addbanner <name> <price>"""
        lang = await database.get_lang(ctx.author.id)
        if not name or price is None or price < 0:
            return await ctx.send(i18n.t(lang, "bs_add_usage", mention=ctx.author.mention))
        if not ctx.message.attachments:
            return await ctx.send(i18n.t(lang, "bs_add_attach", mention=ctx.author.mention))

        att = ctx.message.attachments[0]
        if att.size > 4 * 1024 * 1024:
            return await ctx.send(i18n.t(lang, "bs_add_too_big", mention=ctx.author.mention))

        os.makedirs("banner_images", exist_ok=True)
        ext = os.path.splitext(att.filename)[1].lower() or ".png"
        if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            ext = ".png"
        fname = f"banner_images/banner_{int(time.time())}{ext}"
        await att.save(fname)

        banner_id = await database.add_banner(name[:20], price, gradient=None, file_path=fname, url=att.url)
        await ctx.send(i18n.t(lang, "bs_added", name=name, id=banner_id, mention=ctx.author.mention))

    @commands.command(name="setabout")
    async def set_about(self, ctx: commands.Context, *, text: str = None):
        """Profile card par apni 'About me' line set karo."""
        lang = await database.get_lang(ctx.author.id)
        if not text:
            return await ctx.send(i18n.t(lang, "ab_usage", prefix=ctx.clean_prefix, mention=ctx.author.mention))
        await database.set_about_me(ctx.author.id, text[:60])
        await ctx.send(i18n.t(lang, "ab_set", text=text[:60], mention=ctx.author.mention))


async def setup(bot):
    # init_db pehle (tables honi chahiye - startup hook se pehle setup chal sakta hai)
    await database.init_db()
    # Purane default gradient banners hatao (ye ab nahi bikte)
    for b in await database.get_all_banners():
        if b["gradient"]:
            await database.remove_banner(b["id"])
    # Custom file banners ensure karo (sirf pehli baar - name match karke)
    existing = {b["name"]: b for b in await database.get_all_banners()}
    for name, price, path, url in CUSTOM_BANNERS:
        if name not in existing and os.path.exists(path):
            await database.add_banner(name, price, gradient=None, file_path=path, url=url)
        elif name in existing and not existing[name].get("url") and url:
            # purane entries me URL backfill (shop preview links ke liye)
            await database.set_banner_url(existing[name]["id"], url)
    await bot.add_cog(Profile(bot))
