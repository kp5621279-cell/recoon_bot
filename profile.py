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

# Default banners: gradient hex colors (top->bottom). Prices in coins.
DEFAULT_BANNERS = [
    ("Sunset",   5000,  "ff7e5f|feb47b|ffcf6f", None),
    ("Ocean",    5000,  "2193b0|6dd5ed|b8e6f5", None),
    ("Neon",     12000, "8e2de2|4a00e0|ff2a6d", None),
    ("Forest",   12000, "134e5e|71b280|c9e4a5", None),
    ("Midnight", 25000, "0f0c29|302b63|24243e", None),
    ("Gold",     50000, "b8860b|ffd700|fff3b0", None),
]

# Custom file banners (repo me shipped) - (name, price, file_path)
CUSTOM_BANNERS = [
    ("Recoon", 100, "banner_images/banner_emote.png"),
]


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


def banner_image(banner: dict, w: int = CARD_W, h: int = CARD_H) -> Image.Image:
    """Banner row -> PIL Image (file ya gradient).

    File banners: blurred cover background + fit-width sharp image centered
    in the visible (top) area - chhoti/wide images bhi achhi dikhti hain.
    """
    if banner and banner.get("file_path") and os.path.exists(banner["file_path"]):
        try:
            img = Image.open(banner["file_path"]).convert("RGB")
            # Background: pura card cover, blur
            bg = img.resize((w, h)).filter(ImageFilter.GaussianBlur(16))
            # Foreground: height fit to visible banner area, centered (wide image puri dikhe)
            scale = PANEL_TOP / img.height
            fg_w = int(img.width * scale)
            fg = img.resize((fg_w, PANEL_TOP))
            x = (w - fg_w) // 2
            bg.paste(fg, (x, 0))
            return bg
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

    @commands.command(name="banners")
    async def banners(self, ctx: commands.Context):
        """Banner shop - dekho, kharido, equippo."""
        lang = await database.get_lang(ctx.author.id)
        all_b = await database.get_all_banners()
        owned = {b["id"] for b in await database.get_owned_banners(ctx.author.id)}

        embed = discord.Embed(
            title=i18n.t(lang, "bs_title"),
            description=i18n.t(lang, "bs_desc", prefix=ctx.clean_prefix, coin=COIN),
            color=discord.Color.purple(),
        )
        for b in all_b:
            price = f"{b['price']} {COIN}"
            if b["id"] in owned:
                status = i18n.t(lang, "bs_owned")
            else:
                status = price
            # gradient preview strip
            grad = (b.get("gradient") or "0f0c29|302b63|24243e").replace("|", " ")
            embed.add_field(
                name=f"#{b['id']} {b['name']}",
                value=f"{status}\n`{grad}` — `{ctx.clean_prefix}buy banner {b['id']}`",
                inline=False,
            )
        embed.set_thumbnail(url=BANNER_URL)
        embed.set_footer(text=i18n.t(lang, "bs_footer", prefix=ctx.clean_prefix))
        await ctx.send(embed=embed)

    @commands.command(name="buy")
    async def buy(self, ctx: commands.Context, item: str = None, banner_id: int = None):
        """Buy banner: !buy banner <id>"""
        lang = await database.get_lang(ctx.author.id)
        if item is None or item.lower() != "banner" or banner_id is None:
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

        banner_id = await database.add_banner(name[:20], price, gradient=None, file_path=fname)
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
    # Default gradient banners ensure karo (sirf pehli baar - name match karke)
    existing = {b["name"] for b in await database.get_all_banners()}
    for name, price, grad, _ in DEFAULT_BANNERS:
        if name not in existing:
            await database.add_banner(name, price, gradient=grad)
    # Custom file banners (repo ke saath shipped)
    for name, price, path in CUSTOM_BANNERS:
        if name not in existing and os.path.exists(path):
            await database.add_banner(name, price, gradient=None, file_path=path)
    await bot.add_cog(Profile(bot))
