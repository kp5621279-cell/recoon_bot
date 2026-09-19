import asyncio
import io
import json
import os
import re
import secrets
import time
import urllib.request

import discord
from discord.ext import commands

import database
import i18n

BANNER_URL = "https://cdn.discordapp.com/emojis/1550526211388612608.png?size=512"
COIN = "<:coin:1550545065397584066>"
SHARD_ICON = "<:680106fastboats:1550942131164549130>"
SHARD_NAME = "Fuzon Shard"

HUNT_COOLDOWN = 60 * 60  # 1 ghanta
SHARD_CHANCE = 0.35      # hunt par shard milne ka chance

# Rarity system
RARITY_ORDER = ["common", "uncommon", "rare", "mythic", "gold"]
RARITY_META = {
    "common":   {"emoji": "⚪", "hp": 100, "atk": 22, "dfn": 14},
    "uncommon": {"emoji": "🟢", "hp": 130, "atk": 28, "dfn": 18},
    "rare":     {"emoji": "🔵", "hp": 170, "atk": 36, "dfn": 24},
    "mythic":   {"emoji": "🟣", "hp": 220, "atk": 46, "dfn": 32},
    "gold":     {"emoji": "🟡", "hp": 280, "atk": 58, "dfn": 42},
}
HUNT_WEIGHTS = [("common", 55), ("uncommon", 25), ("rare", 12), ("mythic", 6), ("gold", 2)]

# Tumhare emoji stickers - default species catalog
SPECIES_SEED = [
    # ---- Common (12) ----
    ("ylightning", "Yellow Lightning", "<:60751yellowlightning:1550921249780404295>", "common"),
    ("kitsune",    "Crimson Kitsune",  "<:219445crimsonkitsune:1550921273637339287>", "common"),
    ("eedragon",   "Ember East Dragon", "<:151846embereastdragon:1550921295125024788>", "common"),
    ("pain",       "Frustration Pain",  "<:5544frustrationpain:1550921325676331098>", "common"),
    ("redlight",    "Red Lightning",     "<:806092redlighting:1550921474423132251>", "common"),
    ("shadow",     "Shadow Fruit",      "<:55081shadowbloxfruits:1550921550281310398>", "common"),
    ("cbomb",      "Celebration Bomb",  "<:180500celebrationbomb:1550921585563537569>", "common"),
    ("buddha",     "Buddha Fruit",      "<:495500buddhafruit:1550921883992465478>", "common"),
    ("trex",       "T-Rex Fruit",       "<:778421trexfruit:1550921938485116928>", "common"),
    ("sound",      "Sound Fruit",       "<:788832soundfruit:1550921973134008370>", "common"),
    ("tiger",      "Tiger Fruit",       "<:988436tigerfruit:1550922027785920632>", "common"),
    ("blizzard",   "Blizzard Fruit",    "<:864673blizzardfruit:1550922047125721128>", "common"),
    # ---- Rare (8) - 3 store me, baaki hunt ----
    ("quake",      "Quake Fruit",       "<:319399quakefruit:1550921564655059004>", "rare"),
    ("gravity",    "Gravity Fruit",     "<:31479gravityfruit:1550922391176347688>", "rare"),
    ("mammoth",    "Mammoth Fruit",     "<:822085mammothfruit:1550922420993658930>", "rare"),
    ("hellokitty", "Hello Kitty Sweat", "<a:3900hellokittysweat:1550922480632340570>", "rare"),
    ("creation",   "Creation Fruit",    "<:518076creationfruit:1550921857673203732>", "rare"),
    ("control",    "Control Fruit",     "<:589002controlfruit:1550921830749966376>", "rare"),
    ("spirit",     "Spirit Fruit",      "<:478600spiritfruit:1550921710474362900>", "rare"),
    ("magma",      "Magma Fruit",       "<:418086magmafruit:1550921665322418197>", "rare"),
    # ---- Mythic (5) - sirf hunt ----
    ("light",      "Light Fruit",       "<:278693lightfruit:1550922107876020335>", "mythic"),
    ("spike",      "Spike Fruit",       "<:806632spikefruit:1550922213971066960>", "mythic"),
    ("spin",       "Spin Fruit",        "<:709054spinfruit:1550922231583084634>", "mythic"),
    ("eagle",      "Eagle Fruit",       "<:833326eaglefruit:1550922255469383860>", "mythic"),
    ("blade",      "Blade Fruit",       "<:850974bladefruit:1550922308279865434>", "mythic"),
]

# Store catalog: commons 1-5 lakh, rare 1-2M, mythic 3-7 lakh
# (baaki rare hunt-only)
STORE_SPECIES = {
    # commons (1 - 5 lakh)
    "ylightning": 100000, "kitsune": 130000, "eedragon": 160000, "pain": 190000,
    "redlight": 220000, "shadow": 250000, "cbomb": 280000, "buddha": 310000,
    "trex": 340000, "sound": 370000, "tiger": 400000, "blizzard": 500000,
    # rare (1M - 2M)
    "creation": 1000000, "magma": 1500000, "quake": 2000000,
    # mythic (3 - 7 lakh)
    "light": 300000, "spike": 400000, "spin": 500000, "eagle": 600000, "blade": 700000,
}

# Stable store codes - wbuy <code> se kharido (position kabhi nahi badalti)
SPECIES_CODES = {
    # commons 301-312
    "ylightning": 301, "kitsune": 302, "eedragon": 303, "pain": 304,
    "redlight": 305, "shadow": 306, "cbomb": 307, "buddha": 308,
    "trex": 309, "sound": 310, "tiger": 311, "blizzard": 312,
    # rares 321-323
    "creation": 321, "magma": 322, "quake": 323,
    # mythics 341-345
    "light": 341, "spike": 342, "spin": 343, "eagle": 344, "blade": 345,
}
_CODE_TO_SID = {v: k for k, v in SPECIES_CODES.items()}

# Rarity ring colors (tiles/cards ke liye)
RARITY_RING = {
    "common":   (150, 155, 165),
    "uncommon": (87, 242, 135),
    "rare":     (88, 178, 255),
    "mythic":   (200, 120, 255),
    "gold":     (255, 200, 50),
}


def compact_price(n: int) -> str:
    """100000 -> '100K', 1500000 -> '1.5M' (tile par chhota dikhane ke liye)."""
    if n >= 1000000:
        s = f"{n / 1000000:.1f}".rstrip("0").rstrip(".")
        return s + "M"
    if n >= 1000:
        s = f"{n / 1000:.1f}".rstrip("0").rstrip(".")
        return s + "K"
    return str(n)


async def species_by_code(code: int):
    """Store code -> species dict ya None."""
    sid = _CODE_TO_SID.get(code)
    if not sid:
        return None
    return await database.get_species(sid)

# Food items (hunger hearts +1..5)
FOODS = {
    "hotdog":   {"emoji": "<:hotdog:1550944633494704138>",    "name": "Hotdog",   "hearts": 1, "price": 500},
    "fries":    {"emoji": "<:frenchfries:1550944573511958599>", "name": "French Fries", "hearts": 2, "price": 800},
    "burger":   {"emoji": "<:hamburger:1550944606567407978>", "name": "Hamburger", "hearts": 3, "price": 1200},
    "pizza":    {"emoji": "<:pizza:1550944550288228474>",     "name": "Pizza",    "hearts": 5, "price": 2000},
}

# Abilities (fight me passive effect, max 3 per animal)
ABILITIES = {
    "fastrun":   {"emoji": "💨", "name": "Fast Run",   "price": 3000, "desc": "+15% dodge chance"},
    "ironbody":  {"emoji": "🛡️", "name": "Iron Body",  "price": 4000, "desc": "+25% max HP"},
    "lightning": {"emoji": "⚡", "name": "Lightning",  "price": 5000, "desc": "15% chance double attack"},
    "fireball":  {"emoji": "🔥", "name": "Fireball",   "price": 6000, "desc": "20% chance +50% damage"},
}


def species_from_seed(sid, name, emoji, rarity):
    meta = RARITY_META[rarity]
    return {
        "id": sid, "name": name, "emoji": emoji, "rarity": rarity,
        "hp": meta["hp"], "atk": meta["atk"], "def": meta["dfn"],
        "price": STORE_SPECIES.get(sid, 0), "in_store": sid in STORE_SPECIES,
        "image_url": None,
    }


def stat_of(animal, key):
    """Level ke saath +8% per level compound."""
    base = animal["species"][key]
    return round(base * (1.08 ** (animal["level"] - 1)))


def power_mult(animal):
    """Hunger hearts se power: 5 hearts = 100%, 0 = 70%."""
    return 0.70 + 0.06 * animal["hunger"]


def hunger_bar(hunger):
    return "❤️" * hunger + "🖤" * (5 - hunger)


# ---------------- image card renderer (bade icons ke saath) ----------------

_IMG_CACHE = {}
_PER_ROW = 8
_CELL = 98
_ICON = 64


def _emoji_urls(e: str):
    """Custom Discord emoji -> CDN png/gif, unicode emoji -> twemoji png.
    Candidate URLs list me return karo (pehla jo load ho jaye)."""
    m = re.match(r"^<a?:\w+:(\d+)>$", e)
    if m:
        ext = "gif" if e.startswith("<a:") else "png"
        return [f"https://cdn.discordapp.com/emojis/{m.group(1)}.{ext}?size=128"]
    cps = [f"{ord(c):x}" for c in e]
    base = f"https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.0.3/assets/72x72"
    urls = [base + "/" + "-".join(cps) + ".png"]
    if "fe0f" in cps:  # variation selector wale emoji bina fe0f bhi hote hain
        urls.insert(0, base + "/" + "-".join(c for c in cps if c != "fe0f") + ".png")
    return urls


def _load_img(url: str):
    """URL se image (cache ke saath, fail bhi cache hoga). Gif = pehla frame."""
    if url in _IMG_CACHE:
        return _IMG_CACHE[url]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
        from PIL import Image
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        _IMG_CACHE[url] = img
        return img
    except Exception:
        _IMG_CACHE[url] = None  # negative cache - har interaction par retry nahi
        return None


def render_collection_card(title: str, sections: list, footer: str = ""):
    """Aesthetic dark card: tiles + rarity rings + count pills. sections = [{label, cells}].
    cell = {emoji, count, star, ring, badge}. BytesIO(png) return karta hai."""
    from PIL import Image, ImageDraw, ImageFont

    def _font(size, bold=False):
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        return ImageFont.truetype(os.path.join(os.path.dirname(__file__), "fonts", name), size)

    W = 900
    PAD = 28
    TILE_W, TILE_H = 96, 132
    GAP = 10
    ICON = 58
    NEUTRAL = (88, 101, 124)

    def _fit_name(text, font, max_w):
        """Naam ko 2 lines me wrap karo (har line max_w se chhoti)."""
        words = text.split()
        if not words:
            return [""]
        lines, cur = [], words[0]
        for w in words[1:]:
            if d.textlength(cur + " " + w, font=font) <= max_w:
                cur += " " + w
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        # 2 se zyada lines? pehli 2 rakho, dusri truncate
        if len(lines) > 2:
            lines = lines[:2]
            while lines[1] and d.textlength(lines[1] + "…", font=font) > max_w:
                lines[1] = lines[1][:-1]
            lines[1] += "…"
        return lines

    secs = [s for s in sections if s["cells"]]
    H = 84
    for s in secs:
        rows = (len(s["cells"]) + _PER_ROW - 1) // _PER_ROW
        H += 40 + rows * (TILE_H + GAP) + 6
    H += 58 if footer else 26

    card = Image.new("RGBA", (W, H), (24, 26, 31, 255))
    d = ImageDraw.Draw(card)

    # top accent gradient strip
    for x in range(W):
        t = x / (W - 1)
        col = tuple(int(a + (b - a) * t) for a, b in zip((255, 170, 60), (170, 120, 255)))
        d.line([(x, 0), (x, 5)], fill=col + (255,))

    # header
    d.text((PAD, 24), title, font=_font(30, True), fill=(255, 255, 255))
    d.rounded_rectangle([W - 130, 28, W - PAD, 58], radius=15, fill=(35, 38, 45, 255))
    d.text((W - 130 + 16, 33), "ZOo", font=_font(16, True), fill=(255, 170, 60))

    y = 84
    for s in secs:
        d.text((PAD, y), s["label"].upper(), font=_font(16, True), fill=(150, 158, 172))
        y += 36
        rows = (len(s["cells"]) + _PER_ROW - 1) // _PER_ROW
        for i, cell in enumerate(s["cells"]):
            col_i, row_i = i % _PER_ROW, i // _PER_ROW
            x = PAD + col_i * (TILE_W + GAP)
            ty = y + row_i * (TILE_H + GAP)
            ring = tuple(cell.get("ring") or NEUTRAL)
            # tile bg + rarity ring
            d.rounded_rectangle([x, ty, x + TILE_W - 1, ty + TILE_H - 1], radius=14,
                                fill=(42, 46, 55, 255), outline=ring + (255,), width=2)
            # icon
            img = None
            for u in _emoji_urls(cell["emoji"]):
                img = _load_img(u)
                if img:
                    break
            if img:
                card.alpha_composite(img.resize((ICON, ICON)), (x + (TILE_W - ICON) // 2, ty + 10))
            # naam (icon ke niche, 2-line wrap - frame se bahar nahi jayega)
            nm = cell.get("name")
            if nm:
                nf = _font(13, True)
                for li, line in enumerate(_fit_name(nm, nf, TILE_W - 8)[:2]):
                    d.text((x + (TILE_W - d.textlength(line, font=nf)) / 2,
                            ty + 70 + li * 15), line, font=nf, fill=(228, 232, 240))
            # badge (top-left, e.g. store index)
            badge = cell.get("badge")
            if badge:
                bw = d.textlength(badge, font=_font(13, True))
                d.rounded_rectangle([x + 6, ty + 6, x + 6 + bw + 10, ty + 24], radius=8,
                                    fill=(24, 26, 31, 230))
                d.text((x + 11, ty + 8), badge, font=_font(13, True), fill=(190, 197, 210))
            # count pill (bottom center)
            cnt = cell.get("count")
            if cnt:
                fnt = _font(15, True)
                cw = d.textlength(cnt, font=fnt)
                px1 = x + (TILE_W - (cw + 16)) / 2
                py1 = ty + TILE_H - 30
                d.rounded_rectangle([px1, py1, px1 + cw + 16, py1 + 22], radius=11,
                                    fill=(24, 26, 31, 240))
                d.text((px1 + 8, py1 + 2), cnt, font=fnt, fill=(255, 209, 84))
            # star badge (top-right)
            if cell.get("star"):
                d.text((x + TILE_W - 24, ty + 4), "★", font=_font(20, True), fill=(255, 209, 84))
        y += rows * (TILE_H + GAP) + 6

    if footer:
        d.text((PAD, y + 8), footer, font=_font(16), fill=(140, 147, 160))

    buf = io.BytesIO()
    card.convert("RGB").save(buf, "PNG")
    buf.seek(0)
    return buf


async def render_collection_card_async(title: str, sections: list, footer: str = ""):
    """render_collection_card ko thread me chalao - event loop block na ho
    (downloads/PIL blocking hain, interaction 3s me respond karna hota hai)."""
    return await asyncio.to_thread(render_collection_card, title, sections, footer)


def animal_name(animal):
    return animal["nickname"] or animal["species"]["name"]


def pick_hunt_rarity():
    total = sum(w for _, w in HUNT_WEIGHTS)
    roll = secrets.randbelow(total)
    upto = 0
    for rarity, w in HUNT_WEIGHTS:
        upto += w
        if roll < upto:
            return rarity
    return "common"


async def seed_species():
    """Default catalog ensure karo. Naye species insert; purane walo ka
    price/in_store seed se sync (store pricing badle to DB me bhi pahunche)."""
    existing = {s["id"]: s for s in await database.get_all_species()}
    for sid, name, emoji, rarity in SPECIES_SEED:
        spec = species_from_seed(sid, name, emoji, rarity)
        if sid in existing:
            old = existing[sid]
            if old["price"] != spec["price"] or old["in_store"] != spec["in_store"]:
                await database.update_species_store(sid, spec["price"], spec["in_store"])
        else:
            await database.upsert_species(spec)


class FightView(discord.ui.View):
    """Challenge: target Accept/Decline kare."""

    @staticmethod
    async def wager_line(lang, wager):
        """Wager ka display line: coins ya animal reference."""
        if wager["type"] == "coins":
            return f"{wager['value']} {COIN}"
        a = await database.get_animal(wager["value"])
        if not a:
            return f"a{wager['value']}"
        return f"{a['species']['emoji']} {animal_name(a)} (Lv{a['level']})"

    def __init__(self, challenger, target, wager):
        super().__init__(timeout=60.0)
        self.challenger = challenger
        self.target = target
        self.wager = wager  # {"type": "coins"/"animal", "value": int}
        self.message = None
        self.result = None  # "accepted" / "declined" / "timeout"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target.id:
            lang = await database.get_lang(interaction.user.id)
            await interaction.response.send_message(
                i18n.t(lang, "f_not_yours", mention=interaction.user.mention), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="⚔️")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = "accepted"
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="🏳️")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = "declined"
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    async def on_timeout(self):
        self.result = "timeout"
        try:
            for item in self.children:
                item.disabled = True
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass
        self.stop()


class Animals(commands.Cog):
    """Animal collect, hunt, fight, breed, feed system."""

    FIGHT_ACTIVE = set()  # animal ids jo abhi fight me hain

    def __init__(self, bot):
        self.bot = bot

    # ---------------- commands ----------------

    @commands.command(name="zoo", aliases=["animals", "collection", "inv", "inventory", "bag"])
    async def zoo(self, ctx: commands.Context, member: discord.Member = None):
        """Apna (ya kisi aur ka) zoo + inventory ek image card me dekho."""
        member = member or ctx.author
        lang = await database.get_lang(ctx.author.id)
        animals = await database.get_user_animals(member.id)
        active = await database.get_active_animal(member.id)

        # ---- grid cells: species-wise counts ----
        cells = []
        if animals:
            seen = {}
            for a in animals:
                sid = a["species"]["id"]
                ent = seen.setdefault(sid, {"emoji": a["species"]["emoji"], "name": a["species"]["name"],
                                            "n": 0, "star": False,
                                            "rarity": a["species"]["rarity"]})
                ent["n"] += 1
                if active and a["id"] == active["id"]:
                    ent["star"] = True
            cells = [{"emoji": e["emoji"], "name": e["name"],
                      "count": str(e["n"]) if e["n"] > 1 else "",
                      "star": e["star"], "ring": RARITY_RING.get(e["rarity"])}
                     for e in seen.values()]

        # ---- rarity summary + zoo points ----
        counts = {}
        points = 0
        for a in animals:
            r = a["species"]["rarity"]
            counts[r] = counts.get(r, 0) + 1
            points += RARITY_META.get(r, RARITY_META["common"])["hp"] * a["level"]
        rarity_line = " • ".join(
            f"{code}-{counts.get(r, 0)}" for r, code in zip(RARITY_ORDER, ("C", "U", "R", "M", "G"))
        )

        # ---- inventory sections (category-wise) ----
        items = await database.inv_all(member.id)
        food_cells = [{"emoji": FOODS[iid]["emoji"], "name": FOODS[iid]["name"], "count": str(qty), "star": False}
                      for itype, iid, qty in items if itype == "food" and iid in FOODS]
        shard_cells = [{"emoji": SHARD_ICON, "count": str(qty), "star": False}
                       for itype, iid, qty in items if itype == "shard" and iid == "fuzon"]
        abil_cells = [{"emoji": ABILITIES[iid]["emoji"], "name": ABILITIES[iid]["name"], "count": str(qty), "star": False}
                      for itype, iid, qty in items if itype == "ability" and iid in ABILITIES]

        sections = [{"label": i18n.t(lang, "an_zoo_animals"), "cells": cells}]
        if food_cells:
            sections.append({"label": i18n.t(lang, "an_inv_food"), "cells": food_cells,
                             "ring": (255, 130, 130)})
        if shard_cells:
            sections.append({"label": i18n.t(lang, "an_inv_shards"), "cells": shard_cells,
                             "ring": (130, 200, 255)})
        if abil_cells:
            sections.append({"label": i18n.t(lang, "an_inv_abilities"), "cells": abil_cells,
                             "ring": (255, 220, 120)})
        for s in sections:
            for c in s["cells"]:
                c.setdefault("ring", s.get("ring"))

        footer = f"🏅 {i18n.t(lang, 'an_zoo_points_short')}: {points:,}  |  {rarity_line}  |  " \
                 + i18n.t(lang, "an_zoo_footer", n=len(animals), prefix=ctx.clean_prefix)
        buf = await render_collection_card_async(
            i18n.t(lang, "an_zoo_title", user=member.display_name),
            sections, footer,
        )
        await ctx.send(file=discord.File(buf, "zoo.png"))

    @commands.command(name="hunt")
    async def hunt(self, ctx: commands.Context):
        """Jungle me hunt karo - ek time pe 1 animal (1h cooldown)."""
        lang = await database.get_lang(ctx.author.id)
        last = await database.get_last_hunt(ctx.author.id)
        now = time.time()
        if now - last < HUNT_COOLDOWN:
            left = int(HUNT_COOLDOWN - (now - last))
            return await ctx.send(i18n.t(lang, "an_hunt_wait",
                                         time=f"{left // 60}m {left % 60}s",
                                         mention=ctx.author.mention))
        await database.set_last_hunt(ctx.author.id, now)

        rarity = pick_hunt_rarity()
        pool = [s for s in await database.get_all_species() if s["rarity"] == rarity]
        if not pool:
            pool = [s for s in await database.get_all_species() if s["rarity"] == "common"]
        sp = secrets.choice(pool)
        aid = await database.add_animal(ctx.author.id, sp["id"], obtained="hunt")

        meta = RARITY_META[rarity]
        desc = i18n.t(lang, f"an_rarity_{rarity}") + "\n\n" + i18n.t(
            lang, "an_hunt_got",
            emoji=sp["emoji"], name=sp["name"], id=f"a{aid}",
            r_emoji=meta["emoji"], rarity=rarity.title(),
        )
        color = {"common": discord.Color.light_gray(), "uncommon": discord.Color.green(),
                 "rare": discord.Color.blue(), "mythic": discord.Color.purple(),
                 "gold": discord.Color.gold()}[rarity]
        embed = discord.Embed(title=i18n.t(lang, "an_hunt_title"),
                              description=desc, color=color)
        embed.set_thumbnail(url=BANNER_URL)

        # 35% chance: Fuzon Shard bhi mile
        extra = []
        if secrets.randbelow(100) < 35:
            await database.inv_add(ctx.author.id, "shard", "fuzon", 1)
            extra.append(i18n.t(lang, "an_shard_found", icon=SHARD_ICON, name=SHARD_NAME))
        if extra:
            embed.add_field(name=i18n.t(lang, "an_bonus"), value="\n".join(extra), inline=False)

        await ctx.send(embed=embed)

    @commands.command(name="myanimal", aliases=["ma"])
    async def myanimal(self, ctx: commands.Context):
        """Apna active fighting animal + uske stats."""
        lang = await database.get_lang(ctx.author.id)
        a = await database.get_active_animal(ctx.author.id)
        if not a:
            return await ctx.send(i18n.t(lang, "an_no_active", prefix=ctx.clean_prefix,
                                         mention=ctx.author.mention))
        sp = a["species"]
        meta = RARITY_META.get(sp["rarity"], RARITY_META["common"])
        abil = " ".join(ABILITIES[x]["emoji"] for x in a["abilities"] if x in ABILITIES) or "—"
        xp_needed = max(0, 100 * a["level"] * a["level"] - a["xp"])
        embed = discord.Embed(
            title=i18n.t(lang, "an_stats_title",
                         emoji=sp["emoji"], name=animal_name(a)),
            color=discord.Color.orange(),
        )
        embed.add_field(name=i18n.t(lang, "an_f_level"),
                        value=f"{meta['emoji']} {a['level']}", inline=True)
        embed.add_field(name=i18n.t(lang, "an_f_rarity"),
                        value=sp["rarity"].title(), inline=True)
        embed.add_field(name=i18n.t(lang, "an_f_id"), value=f"`a{a['id']}`", inline=True)
        embed.add_field(name=i18n.t(lang, "an_f_hp"), value=str(stat_of(a, "hp")), inline=True)
        embed.add_field(name=i18n.t(lang, "an_f_atk"), value=str(stat_of(a, "atk")), inline=True)
        embed.add_field(name=i18n.t(lang, "an_f_def"), value=str(stat_of(a, "def")), inline=True)
        embed.add_field(name=i18n.t(lang, "an_f_hunger"),
                        value=f"{hunger_bar(a['hunger'])} ({power_mult(a):.0%} "
                              f"{i18n.t(lang, 'an_power')})", inline=True)
        embed.add_field(name=i18n.t(lang, "an_f_abilities"), value=abil, inline=True)
        embed.add_field(name=i18n.t(lang, "an_f_record"),
                        value=f"✅ {a['wins']} • ❌ {a['losses']}", inline=True)
        embed.add_field(name="XP",
                        value=f"{a['xp']} / {100 * a['level'] * a['level']} "
                              f"({xp_needed} {i18n.t(lang, 'an_xp_left')})", inline=False)
        embed.set_thumbnail(url=BANNER_URL)
        await ctx.send(embed=embed)

    @commands.command(name="use")
    async def use_(self, ctx: commands.Context, animal_ref: str = None):
        """Fighting animal chuno: wuse a3"""
        lang = await database.get_lang(ctx.author.id)
        if not animal_ref or not animal_ref.lower().startswith("a") or not animal_ref[1:].isdigit():
            return await ctx.send(i18n.t(lang, "an_use_usage", prefix=ctx.clean_prefix,
                                         mention=ctx.author.mention))
        aid = int(animal_ref[1:])
        a = await database.get_animal(aid)
        if not a or a["owner_id"] != ctx.author.id:
            return await ctx.send(i18n.t(lang, "an_not_yours", mention=ctx.author.mention))
        await database.set_active_animal(ctx.author.id, aid)
        await ctx.send(i18n.t(lang, "an_now_active", emoji=a["species"]["emoji"],
                              name=animal_name(a), ref=f"a{aid}", mention=ctx.author.mention))

    @commands.command(name="feeda")
    async def feed(self, ctx: commands.Context, animal_ref: str = None, food: str = None):
        """Animal ko khilao: wfeed a1 pizza (hunger full = full power)"""
        lang = await database.get_lang(ctx.author.id)
        if not animal_ref or not animal_ref.lower().startswith("a") or not animal_ref[1:].isdigit():
            return await ctx.send(i18n.t(lang, "an_feed_usage", prefix=ctx.clean_prefix,
                                         foods="/".join(FOODS), mention=ctx.author.mention))
        food = (food or "").lower()
        if food not in FOODS:
            return await ctx.send(i18n.t(lang, "an_feed_food",
                                         foods="/".join(FOODS), mention=ctx.author.mention))
        aid = int(animal_ref[1:])
        a = await database.get_animal(aid)
        if not a or a["owner_id"] != ctx.author.id:
            return await ctx.send(i18n.t(lang, "an_not_yours", mention=ctx.author.mention))
        if a["hunger"] >= 5:
            return await ctx.send(i18n.t(lang, "an_already_full",
                                         emoji=a["species"]["emoji"], mention=ctx.author.mention))
        if not await database.inv_take(ctx.author.id, "food", food, 1):
            f = FOODS[food]
            return await ctx.send(i18n.t(lang, "an_no_food", emoji=f["emoji"],
                                         name=f["name"], prefix=ctx.clean_prefix,
                                         mention=ctx.author.mention))
        new_hunger = min(5, a["hunger"] + FOODS[food]["hearts"])
        await database.animal_set_hunger(aid, new_hunger)
        await ctx.send(i18n.t(lang, "an_fed", emoji=a["species"]["emoji"],
                              name=animal_name(a), food=FOODS[food]["emoji"],
                              bar=hunger_bar(new_hunger),
                              power=f"{power_mult(a) * 100:.0f}",
                              mention=ctx.author.mention))

    @commands.command(name="breed")
    async def breed(self, ctx: commands.Context, ref_a: str = None, ref_b: str = None):
        """Do animals breed karo (2 Fuzon Shards lagte hain): wbreed a1 a2"""
        lang = await database.get_lang(ctx.author.id)
        refs = [ref_a, ref_b]
        if not all(r and r.lower().startswith("a") and r[1:].isdigit() for r in refs):
            return await ctx.send(i18n.t(lang, "an_breed_usage", prefix=ctx.clean_prefix,
                                         icon=SHARD_ICON, mention=ctx.author.mention))
        ids = [int(r[1:]) for r in refs]
        if ids[0] == ids[1]:
            return await ctx.send(i18n.t(lang, "an_breed_same", mention=ctx.author.mention))
        parents = []
        for aid in ids:
            a = await database.get_animal(aid)
            if not a or a["owner_id"] != ctx.author.id:
                return await ctx.send(i18n.t(lang, "an_not_yours", mention=ctx.author.mention))
            parents.append(a)
        if not await database.inv_take(ctx.author.id, "shard", "fuzon", 2):
            have = await database.inv_count(ctx.author.id, "shard", "fuzon")
            return await ctx.send(i18n.t(lang, "an_breed_need_shards", icon=SHARD_ICON,
                                         have=have, mention=ctx.author.mention))
        new_id = await database.animal_breed(parents[0], parents[1])
        await database.delete_animal(ids[0])
        await database.delete_animal(ids[1])
        baby = await database.get_animal(new_id)
        sp = baby["species"]
        meta = RARITY_META.get(sp["rarity"], RARITY_META["common"])
        await ctx.send(i18n.t(lang, "an_breed_done", icon=SHARD_ICON,
                              emoji=sp["emoji"], name=sp["name"], ref=f"a{new_id}",
                              r_emoji=meta["emoji"], rarity=sp["rarity"].title(),
                              hp=stat_of(baby, "hp"), atk=stat_of(baby, "atk"),
                              dfn=stat_of(baby, "def"),
                              p1=animal_name(parents[0]), p2=animal_name(parents[1]),
                              mention=ctx.author.mention))

    @commands.command(name="ability")
    async def ability(self, ctx: commands.Context, animal_ref: str = None, ability_id: str = None):
        """Inventory se ability animal par lagao: wability a1 lightning"""
        lang = await database.get_lang(ctx.author.id)
        if not animal_ref or not animal_ref.lower().startswith("a") or not animal_ref[1:].isdigit():
            list_lines = [f"{a['emoji']} **{a['name']}** — {a['desc']} ({a['price']} {COIN})"
                          for a in ABILITIES.values()]
            return await ctx.send(embed=discord.Embed(
                title=i18n.t(lang, "an_abil_list"), description="\n".join(list_lines),
                color=discord.Color.blurple()))
        aid = int(animal_ref[1:])
        ability_id = (ability_id or "").lower()
        a = await database.get_animal(aid)
        if not a or a["owner_id"] != ctx.author.id:
            return await ctx.send(i18n.t(lang, "an_not_yours", mention=ctx.author.mention))
        if ability_id not in ABILITIES:
            return await ctx.send(i18n.t(lang, "an_abil_unknown",
                                         foods="/".join(ABILITIES), mention=ctx.author.mention))
        if not await database.inv_take(ctx.author.id, "ability", ability_id, 1):
            ab = ABILITIES[ability_id]
            return await ctx.send(i18n.t(lang, "an_abil_not_owned", emoji=ab["emoji"],
                                         name=ab["name"], prefix=ctx.clean_prefix,
                                         mention=ctx.author.mention))
        ok = await database.animal_add_ability(aid, ability_id)
        if not ok:
            await database.inv_add(ctx.author.id, "ability", ability_id, 1)  # wapas
            return await ctx.send(i18n.t(lang, "an_abil_limit",
                                         emoji=a["species"]["emoji"], mention=ctx.author.mention))
        ab = ABILITIES[ability_id]
        await ctx.send(i18n.t(lang, "an_abil_applied", ab_emoji=ab["emoji"],
                              ab_name=ab["name"], emoji=a["species"]["emoji"],
                              name=animal_name(a), mention=ctx.author.mention))

    @commands.command(name="release")
    async def release(self, ctx: commands.Context, animal_ref: str = None):
        """Animal chhod do (coins milte hain, active/fight me nahi)."""
        lang = await database.get_lang(ctx.author.id)
        if not animal_ref or not animal_ref.lower().startswith("a") or not animal_ref[1:].isdigit():
            return await ctx.send(i18n.t(lang, "an_release_usage", prefix=ctx.clean_prefix,
                                         mention=ctx.author.mention))
        aid = int(animal_ref[1:])
        a = await database.get_animal(aid)
        if not a or a["owner_id"] != ctx.author.id:
            return await ctx.send(i18n.t(lang, "an_not_yours", mention=ctx.author.mention))
        active = await database.get_active_animal(ctx.author.id)
        if active and active["id"] == aid:
            return await ctx.send(i18n.t(lang, "an_release_active",
                                         emoji=a["species"]["emoji"], mention=ctx.author.mention))
        if aid in self.FIGHT_ACTIVE:
            return await ctx.send(i18n.t(lang, "an_release_fighting",
                                         emoji=a["species"]["emoji"], mention=ctx.author.mention))
        reward = RARITY_META.get(a["species"]["rarity"], RARITY_META["common"])["hp"] * 5
        await database.delete_animal(aid)
        await database.update_coins(ctx.author.id, reward)
        await ctx.send(i18n.t(lang, "an_released", emoji=a["species"]["emoji"],
                              name=animal_name(a), amount=reward, coin=COIN,
                              mention=ctx.author.mention))

    @commands.command(name="anick")
    async def anick(self, ctx: commands.Context, animal_ref: str = None, *, nickname: str = None):
        """Animal ka nickname: wanick a1 Sheru"""
        lang = await database.get_lang(ctx.author.id)
        if not animal_ref or not animal_ref.lower().startswith("a") or not animal_ref[1:].isdigit() or not nickname:
            return await ctx.send(i18n.t(lang, "an_nick_usage", prefix=ctx.clean_prefix,
                                         mention=ctx.author.mention))
        aid = int(animal_ref[1:])
        a = await database.get_animal(aid)
        if not a or a["owner_id"] != ctx.author.id:
            return await ctx.send(i18n.t(lang, "an_not_yours", mention=ctx.author.mention))
        await database.set_nickname(aid, nickname.strip()[:30])
        await ctx.send(i18n.t(lang, "an_nick_done", emoji=a["species"]["emoji"],
                              name=nickname.strip()[:30], mention=ctx.author.mention))

    # ---------------- fight ----------------

    @commands.command(name="fight", aliases=["battle", "duel"])
    async def fight(self, ctx: commands.Context, target: discord.Member = None, *, wager: str = None):
        """Player challenge karo: wfight @user 500 (coins) ya wfight @user a3 (animal)"""
        lang = await database.get_lang(ctx.author.id)
        if target is None or wager is None:
            return await ctx.send(i18n.t(lang, "an_fight_usage", prefix=ctx.clean_prefix,
                                         mention=ctx.author.mention))
        if target.bot or target.id == ctx.author.id:
            return await ctx.send(i18n.t(lang, "an_fight_bad_target",
                                         mention=ctx.author.mention))

        wager = wager.strip().lower()
        if wager.startswith("a") and wager[1:].isdigit():
            aid = int(wager[1:])
            a = await database.get_animal(aid)
            if not a or a["owner_id"] != ctx.author.id:
                return await ctx.send(i18n.t(lang, "an_not_yours", mention=ctx.author.mention))
            if aid in self.FIGHT_ACTIVE:
                return await ctx.send(i18n.t(lang, "an_fight_busy_animal",
                                             emoji=a["species"]["emoji"], mention=ctx.author.mention))
            my_animal, wager_obj = a, {"type": "animal", "value": aid}
        elif wager.isdigit():
            bet = int(wager)
            user = await database.get_user(ctx.author.id)
            if not user or user["coins"] < bet or bet <= 0:
                return await ctx.send(i18n.t(lang, "an_fight_poor",
                                             coin=COIN, balance=user["coins"] if user else 0,
                                             mention=ctx.author.mention))
            # escrow: challenger ke coins abhi se kat lo (decline/timeout par refund)
            await database.update_coins(ctx.author.id, -bet)
            my_animal, wager_obj = await database.get_active_animal(ctx.author.id), {"type": "coins", "value": bet}
        else:
            return await ctx.send(i18n.t(lang, "an_fight_usage", prefix=ctx.clean_prefix,
                                         mention=ctx.author.mention))
        if my_animal is None:
            return await ctx.send(i18n.t(lang, "an_no_active", prefix=ctx.clean_prefix,
                                         mention=ctx.author.mention))

        view = FightView(ctx.author, target, wager_obj)
        view.message = await ctx.send(i18n.t(lang, "an_fight_challenge",
                                             user=target.mention,
                                             challenger=ctx.author.display_name,
                                             emoji=my_animal["species"]["emoji"],
                                             aname=animal_name(my_animal),
                                             wager=await FightView.wager_line(lang, wager_obj)), view=view)
        await view.wait()
        if view.result != "accepted":
            if wager_obj["type"] == "coins":
                await database.update_coins(ctx.author.id, wager_obj["value"])  # refund
            return await ctx.send(i18n.t(lang, "an_fight_declined"
                                         if view.result == "declined" else "an_fight_timeout",
                                         mention=ctx.author.mention))

        await self._run_fight(ctx, lang, ctx.author, target, my_animal, wager_obj)

    async def _run_fight(self, ctx, lang, p1, p2, a1, wager):
        """Asli combat: 5 rounds, HP bars, escrow, wager settle."""
        # dono ke animals
        a2 = await database.get_active_animal(p2.id)
        if a2 is None:
            if wager["type"] == "coins":
                await database.update_coins(p1.id, wager["value"])  # refund
            return await ctx.send(i18n.t(lang, "an_fight_target_no_animal", user=p2.mention,
                                         prefix=ctx.clean_prefix))
        if a2["id"] in self.FIGHT_ACTIVE:
            return await ctx.send(i18n.t(lang, "an_fight_busy_animal",
                                         emoji=a2["species"]["emoji"], mention=p2.mention))

        # escrow: challenger ke coins pehle se kat chuke; target ke coins ab kato (refund-safe)
        if wager["type"] == "coins":
            u2 = await database.get_user(p2.id)
            if not u2 or u2["coins"] < wager["value"]:
                await database.update_coins(p1.id, wager["value"])  # challenger refund
                return await ctx.send(i18n.t(lang, "an_fight_target_poor",
                                             user=p2.mention, mention=p1.mention))
            await database.update_coins(p2.id, -wager["value"])
        else:
            self.FIGHT_ACTIVE.add(wager["value"])
        self.FIGHT_ACTIVE.add(a1["id"])
        self.FIGHT_ACTIVE.add(a2["id"])

        try:
            winner_p, loser_p, winner_a, loser_a = await self._simulate(ctx, p1, p2, a1, a2)
        finally:
            self.FIGHT_ACTIVE.discard(a1["id"])
            self.FIGHT_ACTIVE.discard(a2["id"])
            if wager["type"] == "animal":
                self.FIGHT_ACTIVE.discard(wager["value"])

        await database.record_game(p1.id)
        await database.record_game(p2.id)

        # thakan: har fight par hunger -1
        await database.animal_set_hunger(winner_a["id"], winner_a["hunger"] - 1)
        await database.animal_set_hunger(loser_a["id"], loser_a["hunger"] - 1)
        await database.animal_record_result(winner_a["id"], True)
        await database.animal_record_result(loser_a["id"], False)
        old_lvl, new_lvl = await database.animal_gain_xp(winner_a["id"], 25)
        await database.animal_gain_xp(loser_a["id"], 5)

        # wager settle
        wager_line = await FightView.wager_line(lang, wager)
        if wager["type"] == "coins":
            await database.update_coins(winner_p.id, wager["value"] * 2)
        else:
            # stake wala animal winner ke paas jata hai (owner change)
            async with __import__("aiosqlite").connect(database.DB_PATH) as db:
                await db.execute("UPDATE animals SET owner_id = ? WHERE id = ?",
                                 (winner_p.id, wager["value"]))
                await db.commit()

        winner_lvl_line = ""
        if new_lvl > old_lvl:
            winner_lvl_line = i18n.t(lang, "an_level_up", emoji=winner_a["species"]["emoji"],
                                     name=animal_name(winner_a), level=new_lvl)

        embed = discord.Embed(
            title=i18n.t(lang, "an_fight_result_title"),
            description=i18n.t(lang, "an_fight_winner",
                               emoji=winner_a["species"]["emoji"],
                               name=animal_name(winner_a), user=winner_p.mention,
                               wager=wager_line),
            color=discord.Color.gold(),
        )
        if winner_lvl_line:
            embed.add_field(name="🎉", value=winner_lvl_line, inline=False)
        embed.set_footer(text=i18n.t(lang, "an_fight_tired",
                                     w_emoji=winner_a["species"]["emoji"],
                                     l_emoji=loser_a["species"]["emoji"]))
        await ctx.send(embed=embed)

    async def _simulate(self, ctx, p1, p2, a1, a2):
        """5-round combat; har round ek attacker (speed roll), damage formula
        ATK * power * ability; HP khatam = haar. Status embed update hota hai."""
        lang = await database.get_lang(ctx.author.id)

        def eff(animal):
            hp = stat_of(animal, "hp")
            if "ironbody" in animal["abilities"]:
                hp = round(hp * 1.25)
            return hp

        hp1, hp2 = eff(a1), eff(a2)
        max1, max2 = hp1, hp2
        embed = discord.Embed(title=i18n.t(lang, "an_fight_live_title"),
                              color=discord.Color.dark_orange())
        msg = await ctx.send(embed=embed)

        def bar(cur, mx):
            filled = max(0, round(cur / max(1, mx) * 10))
            return "🟩" * filled + "⬛" * (10 - filled)

        async def upd(round_no, note):
            e = discord.Embed(
                title=i18n.t(lang, "an_fight_live_title"),
                description=f"**{a1['species']['emoji']} {animal_name(a1)}** ({p1.display_name}) vs "
                            f"**{a2['species']['emoji']} {animal_name(a2)}** ({p2.display_name})\n\n{note}",
                color=discord.Color.dark_orange())
            e.add_field(name=f"{a1['species']['emoji']} {animal_name(a1)}",
                        value=f"{bar(hp1, max1)} {max(0, hp1)}/{max1}", inline=False)
            e.add_field(name=f"{a2['species']['emoji']} {animal_name(a2)}",
                        value=f"{bar(hp2, max2)} {max(0, hp2)}/{max2}", inline=False)
            e.set_footer(text=i18n.t(lang, "an_fight_round", n=round_no))
            try:
                await msg.edit(embed=e)
            except discord.HTTPException:
                pass

        await upd(0, i18n.t(lang, "an_fight_begin"))

        def can_dodge(animal):
            return "fastrun" in animal["abilities"] and secrets.randbelow(100) < 15

        def calc_dmg(attacker, defender):
            dmg = stat_of(attacker, "atk") * power_mult(attacker)
            dmg *= 1 + secrets.randbelow(30) / 100  # ±15% variance
            dmg *= 100 / (100 + stat_of(defender, "def"))
            if "fireball" in attacker["abilities"] and secrets.randbelow(100) < 20:
                dmg *= 1.5
            return dmg

        rnd = 0
        while hp1 > 0 and hp2 > 0 and rnd < 12:
            rnd += 1
            # kaun attack karega - slightly random
            if secrets.randbelow(100) < 50:
                atk_a, def_a, hp_def = a1, a2, "hp2"
            else:
                atk_a, def_a, hp_def = a2, a1, "hp1"
            if can_dodge(def_a):
                note = i18n.t(lang, "an_fight_dodge", emoji=def_a["species"]["emoji"],
                              name=animal_name(def_a))
            else:
                dmg = round(calc_dmg(atk_a, def_a))
                if hp_def == "hp2":
                    hp2 -= dmg
                    note = i18n.t(lang, "an_fight_hit", ae=atk_a["species"]["emoji"],
                                  an=animal_name(atk_a), de=def_a["species"]["emoji"],
                                  dn=animal_name(def_a), dmg=dmg)
                else:
                    hp1 -= dmg
                    note = i18n.t(lang, "an_fight_hit", ae=atk_a["species"]["emoji"],
                                  an=animal_name(atk_a), de=def_a["species"]["emoji"],
                                  dn=animal_name(def_a), dmg=dmg)
                if "lightning" in atk_a["abilities"] and secrets.randbelow(100) < 15:
                    dmg2 = round(dmg * 0.8)
                    if hp_def == "hp2":
                        hp2 -= dmg2
                    else:
                        hp1 -= dmg2
                    note += "\n⚡ " + i18n.t(lang, "an_fight_double",
                                             dmg=dmg2)
            await upd(rnd, note)
            await asyncio.sleep(1.2)

        if hp1 <= 0 and hp2 <= 0:
            hp1, hp2 = 1, 0  # last hit wins tie-break
        if hp2 <= 0:
            return p1, p2, a1, a2
        return p2, p1, a2, a1


async def handle_buy(ctx, lang: str, kind: str, ref):
    """wbuy animal/food/ability - profile.py se call hota hai."""
    user = await database.get_user(ctx.author.id)
    balance = user["coins"] if user else 0

    if kind == "animal":
        if ref is None or not str(ref).isdigit():
            return await ctx.send(i18n.t(lang, "an_buy_usage", prefix=ctx.clean_prefix,
                                         mention=ctx.author.mention))
        num = int(ref)
        sp = await species_by_code(num)
        if sp is None:
            # fallback: purana position-index (shop listing ka #number)
            species = [s for s in await database.get_all_species() if s["in_store"]]
            if 1 <= num <= len(species):
                sp = species[num - 1]
        if sp is None or not sp.get("in_store"):
            return await ctx.send(i18n.t(lang, "an_buy_bad_id", mention=ctx.author.mention))
        if balance < sp["price"]:
            return await ctx.send(i18n.t(lang, "m_poor", coin=COIN, balance=balance,
                                         mention=ctx.author.mention))
        await database.update_coins(ctx.author.id, -sp["price"])
        aid = await database.add_animal(ctx.author.id, sp["id"], obtained="store")
        return await ctx.send(i18n.t(lang, "an_buy_done", emoji=sp["emoji"], name=sp["name"],
                                     price=sp["price"], coin=COIN, ref=f"a{aid}",
                                     prefix=ctx.clean_prefix, mention=ctx.author.mention))

    if kind == "food":
        food = (str(ref) or "").lower() if ref else ""
        if food not in FOODS:
            return await ctx.send(i18n.t(lang, "an_feed_food", foods="/".join(FOODS),
                                         mention=ctx.author.mention))
        f = FOODS[food]
        if balance < f["price"]:
            return await ctx.send(i18n.t(lang, "m_poor", coin=COIN, balance=balance,
                                         mention=ctx.author.mention))
        await database.update_coins(ctx.author.id, -f["price"])
        await database.inv_add(ctx.author.id, "food", food, 1)
        return await ctx.send(i18n.t(lang, "an_buy_food_done", emoji=f["emoji"], name=f["name"],
                                     price=f["price"], coin=COIN, prefix=ctx.clean_prefix,
                                     mention=ctx.author.mention))

    if kind == "ability":
        ab_id = (str(ref) or "").lower() if ref else ""
        if ab_id not in ABILITIES:
            return await ctx.send(i18n.t(lang, "an_abil_unknown", foods="/".join(ABILITIES),
                                         mention=ctx.author.mention))
        ab = ABILITIES[ab_id]
        if balance < ab["price"]:
            return await ctx.send(i18n.t(lang, "m_poor", coin=COIN, balance=balance,
                                         mention=ctx.author.mention))
        await database.update_coins(ctx.author.id, -ab["price"])
        await database.inv_add(ctx.author.id, "ability", ab_id, 1)
        return await ctx.send(i18n.t(lang, "an_buy_ability_done", emoji=ab["emoji"],
                                     name=ab["name"], price=ab["price"], coin=COIN,
                                     prefix=ctx.clean_prefix, mention=ctx.author.mention))


async def setup(bot):
    await database.init_db()
    await seed_species()
    await bot.add_cog(Animals(bot))
