import discord
import os
import asyncio

from discord import ui
from bot.logs_to_channel import log_to_channel
from zoneinfo import ZoneInfo
from datetime import datetime, timezone


TICKET_ARCHIVE_CATEGORY_NAME = "archiv"
TRANSCRIPT_FOLDER = "transcripts"


# Close and claim view
class CloseView(ui.View):
    def __init__(self, requester: discord.Member):
        super().__init__(timeout=None)
        self.requester = requester

    @ui.button(label="Claim", style=discord.ButtonStyle.primary)
    async def claim_button(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        channel = interaction.channel
        claimer = interaction.user

        # 1. Nur Admins dürfen claimen
        if not any(role.permissions.administrator for role in claimer.roles):
            await interaction.response.send_message(
                "❌ Nur Admins können Tickets claimen.", ephemeral=True
            )
            await log_to_channel(
                guild,
                f"❌ {claimer.mention} versucht ein Ticket zu claimen.",
            )
            return

        # 2. Alle Admins (Members!) blockieren, außer Claimer
        for member in guild.members:
            if member != claimer and any(
                r.permissions.administrator for r in member.roles
            ):
                await channel.set_permissions(member, send_messages=False)

        # 3. Claimer explizit erlauben
        await channel.set_permissions(
            claimer, send_messages=True, read_message_history=True
        )

        # 4. Button deaktivieren
        button.disabled = True
        await interaction.message.edit(view=self)

        # 5. Hinweis senden
        await interaction.response.send_message(
            f"🤺 {claimer.mention} hat dieses Ticket übernommen.",
            ephemeral=False,
        )

        # log start

        log_embed = discord.Embed(
            title="📥 Ticket zugeteilt",
            color=discord.Color.blue(),
            timestamp=interaction.created_at,
        )
        log_embed.add_field(name="👤 Admin", value=claimer.mention, inline=True)
        log_embed.add_field(name="Ticket", value=channel.name, inline=True)

        await log_to_channel(guild, log_embed)

        # log end

    @ui.button(label="Ticket schließen & löschen", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: ui.Button):
        channel = interaction.channel
        guild = interaction.guild
        closer = interaction.user

        # 1. Schreibrechte entziehen
        await channel.set_permissions(self.requester, send_messages=False)

        # 2. Channel umbenennen
        if not channel.name.startswith("closed-"):
            await channel.edit(name=f"closed-{channel.name}")

        # 3. Transkript speichern
        transcript_path = await self.save_transcript(channel)

        # 5. Archiv-Embed erstellen
        embed = discord.Embed(
            title="📁 Archiviertes Ticket",
            color=discord.Color.dark_grey(),
            timestamp=datetime.now(timezone.utc),
        )

        # format created_at
        formatted_date = interaction.created_at.strftime("%B %d, %Y")

        embed.add_field(name="👤 User", value=self.requester.mention, inline=True)
        embed.add_field(name="🎟️ Ticket", value=channel.name, inline=True)
        embed.add_field(name="📅 Created on", value=formatted_date, inline=True)
        embed.add_field(name="🔒 Closed by", value=closer.name, inline=True)
        embed.set_footer(text="Transkript im Anhang")

        transcript_file = discord.File(
            transcript_path, filename=os.path.basename(transcript_path)
        )

        # 5. Archiv-Channel suchen und senden
        archiv_channel = discord.utils.get(
            guild.text_channels, name=TICKET_ARCHIVE_CATEGORY_NAME
        )
        if archiv_channel:
            await archiv_channel.send(embed=embed, file=transcript_file)
        else:
            await interaction.response.send_message(
                "⚠️ Channel `#archiv` nicht gefunden. Archivierung fehlgeschlagen.",
                ephemeral=True,
            )
            return

        # 6. Button deaktivieren
        button.disabled = True
        await interaction.message.edit(view=self)

        # 7. Bestätigung
        await interaction.response.send_message(
            "✅ Ticket geschlossen & im Archiv geloggt.(Channel wird in 1 Minute gelöscht)",
            ephemeral=True,
        )
        await log_to_channel(
            guild, f"📁 Ticket {channel.name} wurde von {closer.mention} geschlossen."
        )

        # 8. Channel löschen
        await asyncio.sleep(60)
        await channel.delete()

    async def save_transcript(self, channel: discord.TextChannel) -> str:
        """Speichert den Nachrichtenverlauf des Channels in eine .txt Datei."""
        if not os.path.exists(TRANSCRIPT_FOLDER):
            os.makedirs(TRANSCRIPT_FOLDER)

        filename = f"{TRANSCRIPT_FOLDER}/{channel.name}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            async for msg in channel.history(limit=None, oldest_first=True):
                timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
                author = f"{msg.author.name}#{msg.author.discriminator}"
                content = msg.content or "[EMBED / DATEI / NICHT-LESBAR]"
                f.write(f"[{timestamp}] {author}: {content}\n")
        return filename
