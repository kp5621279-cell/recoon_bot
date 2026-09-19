import discord
from discord.ext import commands
import yt_dlp
import asyncio

import database

# Banner image URL (Discord CDN for emoji 473)
BANNER_URL = "https://cdn.discordapp.com/emojis/1550526211388612608.png?size=512"

# yt-dlp options for streaming
ytdl_format_options = {
    'format': 'best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
}

# Add cookies if the file exists
import os
if os.path.exists('cookies.txt'):
    ytdl_format_options['cookiefile'] = 'cookies.txt'

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_query(cls, query, loop=None):
        loop = loop or asyncio.get_event_loop()
        # If it's a link, we process it. If it's text, we search.
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
        
        if 'entries' in data:
            # take first item from a playlist or search results
            data = data['entries'][0]

        filename = data['url']
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class MusicControlView(discord.ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="Pause/Resume", style=discord.ButtonStyle.primary, emoji=discord.PartialEmoji(name='pause', id=1550534116208935063))
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = interaction.guild.voice_client
        if not voice_client:
            return await interaction.response.send_message("Bot is not in a VC.", ephemeral=True)
        
        if voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("⏸️ Paused the music.", ephemeral=True)
        elif voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("▶️ Resumed the music.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, emoji=discord.PartialEmoji(name='next', id=1550534071757570069))
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_playing():
            return await interaction.response.send_message("Nothing is playing.", ephemeral=True)
        
        voice_client.stop() # Stopping triggers the after callback which plays next
        await interaction.response.send_message("⏭️ Skipped the song.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji=discord.PartialEmoji(name='music', id=1550534050715009065))
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = interaction.guild.voice_client
        if not voice_client:
            return await interaction.response.send_message("Bot is not in a VC.", ephemeral=True)
        
        self.cog.queues[self.guild_id] = []
        await self.cog._forget_voice_channel(self.guild_id)
        voice_client.stop()
        await self.cog._set_voice_status(interaction.guild, None)
        await voice_client.disconnect()
        await interaction.response.send_message("⏹️ Stopped music and cleared queue.", ephemeral=True)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {} # guild_id: [queries]
        self._startup_done = False

    async def _set_voice_status(self, guild, status):
        """Set the text shown under the voice channel's name ("Playing - ...").

        Pass ``status=None`` to clear it. Discord needs the 'Set Voice Channel
        Status' permission for this, so failures are logged instead of raised.
        """
        voice_client = guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return

        # Discord caps the voice channel status at 500 characters.
        status = status[:500] if status else None
        try:
            await voice_client.channel.edit(status=status, reason="Now playing")
        except discord.Forbidden:
            print("Cannot update voice channel status: missing 'Set Voice Channel Status' permission.")
        except Exception as e:
            print(f"Error updating voice channel status: {e}")

    # ------------------- 24/7 helpers -------------------

    async def _remember_voice_channel(self, guild_id, channel_id):
        """Persist the channel the bot stays in, so it can rejoin after a restart."""
        await database.set_voice_channel(guild_id, channel_id)

    async def _forget_voice_channel(self, guild_id):
        await database.clear_voice_channel(guild_id)

    async def _was_kicked(self, guild):
        """Tell a manual kick apart from a network drop using the audit log.

        Returns ``True`` only when an admin disconnected the bot, which is the
        one case where it should stay out of voice instead of rejoining.
        """
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.member_disconnect):
                if (discord.utils.utcnow() - entry.created_at).total_seconds() > 10:
                    break  # entries are newest first
                # Discord frequently leaves target_id empty for this action, so
                # an entry we cannot attribute is treated as a kick. Staying out
                # is the safer guess: rejoining after a kick is the obvious bug.
                if entry.target is None or entry.target.id == self.bot.user.id:
                    print(f"Disconnect logged by {entry.user} in guild {guild.id}.")
                    return True
        except discord.Forbidden:
            print("Cannot read the audit log (missing 'View Audit Log'): will rejoin after every disconnect.")
        except Exception as e:
            print(f"Audit log check failed: {e}")
        return False

    async def _reconnect(self, guild, channel_id):
        """Rejoin a voice channel after an unexpected drop."""
        for attempt in range(1, 4):
            channel = guild.get_channel(channel_id)
            if not isinstance(channel, discord.VoiceChannel):
                print(f"Voice channel {channel_id} is no longer available; dropping 24/7 mode for guild {guild.id}.")
                await self._forget_voice_channel(guild.id)
                return
            try:
                await channel.connect()
                print(f"Rejoined '{channel}' in guild {guild.id} (attempt {attempt}).")
                return
            except Exception as e:
                print(f"Rejoin attempt {attempt} failed: {e}")
                await asyncio.sleep(2)

    @commands.Cog.listener()
    async def on_ready(self):
        if self._startup_done:
            return
        self._startup_done = True
        # Safe to call again: init_db only uses CREATE TABLE IF NOT EXISTS.
        await database.init_db()
        for guild_id, channel_id in await database.get_all_voice_channels():
            guild = self.bot.get_guild(guild_id)
            channel = guild.get_channel(channel_id) if guild else None
            if isinstance(channel, discord.VoiceChannel):
                try:
                    await channel.connect()
                    print(f"Rejoined saved voice channel '{channel}' in guild {guild_id}.")
                except Exception as e:
                    print(f"Could not rejoin saved voice channel in guild {guild_id}: {e}")
            else:
                await self._forget_voice_channel(guild_id)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Stay in voice 24/7: rejoin on drops, leave only when kicked."""
        if self.bot.user is None or member.id != self.bot.user.id or before.channel == after.channel:
            return

        guild = member.guild
        if after.channel is not None:
            # Followed a move to another channel.
            await self._remember_voice_channel(guild.id, after.channel.id)
            return

        # The bot is out of voice now. Give Discord a moment to write the audit
        # log entry before deciding whether this was a kick.
        await asyncio.sleep(1)
        if await self._was_kicked(guild):
            await self._forget_voice_channel(guild.id)
            return

        # Only rejoin when this channel is the one we are supposed to be in,
        # so an intentional !leave/!stop is not undone.
        if before.channel is not None and await database.get_voice_channel(guild.id) == before.channel.id:
            await self._reconnect(guild, before.channel.id)

    def play_next(self, ctx):
        try:
            if self.queues.get(ctx.guild.id):
                query = self.queues[ctx.guild.id].pop(0)
                self.bot.loop.create_task(self.play_song(ctx, query))
        except Exception as e:
            print(f"Error in play_next: {e}")

    async def play_song(self, ctx, query):
        voice_client = ctx.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return
        try:
            player = await YTDLSource.from_query(query, loop=self.bot.loop)
            
            def after_playing(error):
                if error:
                    print(f"Player error: {error}")
                # Clear activity if nothing left in queue
                if not self.queues.get(ctx.guild.id):
                    self.bot.loop.create_task(
                        self.bot.change_presence(status=discord.Status.dnd, activity=None)
                    )
                    self.bot.loop.create_task(self._set_voice_status(ctx.guild, None))
                self.play_next(ctx)
            
            voice_client.play(player, after=after_playing)
            
            # Set bot activity to the current song
            activity = discord.Game(name=f"🎶 {player.title}")
            await self.bot.change_presence(status=discord.Status.dnd, activity=activity)
            # Show the song under the voice channel name too
            await self._set_voice_status(ctx.guild, f"🎶 Playing - {player.title}")
            print(f"Status set to: {player.title}")
            
            embed = discord.Embed(title="<:music:1550534050715009065> Now Playing", description=f"**{player.title}**", color=discord.Color.green())
            embed.set_thumbnail(url=BANNER_URL)
            view = MusicControlView(self, ctx.guild.id)
            await ctx.send(embed=embed, view=view)
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"Error playing song: `{str(e)}`",
                color=discord.Color.red()
            )
            error_embed.set_thumbnail(url=BANNER_URL)
            await ctx.send(embed=error_embed)
            await self.bot.change_presence(status=discord.Status.dnd, activity=None)
            await self._set_voice_status(ctx.guild, None)
            self.play_next(ctx)

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        """Plays a song from YouTube/Spotify/etc or adds it to queue."""
        if not ctx.author.voice:
            return await ctx.send("❌ You need to join a Voice Channel first!")

        voice_channel = ctx.author.voice.channel
        voice_client = ctx.guild.voice_client

        if not voice_client:
            await voice_channel.connect()
            voice_client = ctx.guild.voice_client
        elif voice_client.channel != voice_channel:
            return await ctx.send("❌ Bot is already in another voice channel.")

        # Stay in this channel until kicked, even when the queue runs out.
        await self._remember_voice_channel(ctx.guild.id, voice_channel.id)

        if ctx.guild.id not in self.queues:
            self.queues[ctx.guild.id] = []

        if voice_client.is_playing() or voice_client.is_paused():
            self.queues[ctx.guild.id].append(query)
            queue_embed = discord.Embed(
                title="📜 Added to Queue",
                description=f"✅ **{query}** has been added to the queue.",
                color=discord.Color.blurple()
            )
            queue_embed.set_thumbnail(url=BANNER_URL)
            await ctx.send(embed=queue_embed)
        else:
            search_embed = discord.Embed(
                title="🔍 Searching",
                description=f"Searching for `{query}`...",
                color=discord.Color.orange()
            )
            search_embed.set_thumbnail(url=BANNER_URL)
            await ctx.send(embed=search_embed)
            await self.play_song(ctx, query)

    @commands.command(name="join", aliases=["summon"])
    async def join(self, ctx: commands.Context):
        """Joins your voice channel and stays there 24/7."""
        if not ctx.author.voice:
            return await ctx.send("❌ You need to join a Voice Channel first!")

        channel = ctx.author.voice.channel
        voice_client = ctx.guild.voice_client

        if voice_client:
            if voice_client.channel != channel:
                await voice_client.move_to(channel)
        else:
            await channel.connect()

        await self._remember_voice_channel(ctx.guild.id, channel.id)
        await ctx.send(f"✅ Joined **{channel.name}**. I'll stay here until I'm kicked out.")

    @commands.command(name="leave", aliases=["disconnect", "dc"])
    async def leave(self, ctx: commands.Context):
        """Leaves the voice channel and stops staying 24/7."""
        await self._forget_voice_channel(ctx.guild.id)
        voice_client = ctx.guild.voice_client
        if voice_client:
            self.queues[ctx.guild.id] = []
            voice_client.stop()
            await self._set_voice_status(ctx.guild, None)
            await voice_client.disconnect()
            await self.bot.change_presence(status=discord.Status.dnd, activity=None)
            await ctx.send("👋 Left the voice channel.")
        else:
            await ctx.send("Bot is not connected to a voice channel.")

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        """Stops the music and disconnects the bot."""
        voice_client = ctx.guild.voice_client
        if voice_client:
            self.queues[ctx.guild.id] = []
            await self._forget_voice_channel(ctx.guild.id)
            voice_client.stop()
            await self._set_voice_status(ctx.guild, None)
            await voice_client.disconnect()
            await self.bot.change_presence(status=discord.Status.dnd, activity=None)
            await ctx.send("⏹️ Disconnected and cleared queue.")
        else:
            await ctx.send("Bot is not connected to a voice channel.")

    @commands.command(name="skip")
    async def skip(self, ctx: commands.Context):
        """Skips the current song."""
        voice_client = ctx.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await ctx.send("⏭️ Skipped.")
        else:
            await ctx.send("Nothing is playing to skip.")

async def setup(bot):
    await bot.add_cog(Music(bot))
