import discord
import os
import asyncio
from discord import ui
from bot.logs_to_channel import log_to_channel
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

TICKET_ARCHIVE_CATEGORY_NAME = os.getenv("TICKET_ARCHIVE_CATEGORY_NAME")
TRANSCRIPT_FOLDER = os.getenv("TRANSCRIPT_FOLDER")


class CloseView(ui.View):
    """Claim / Close-Buttons für jede Ticket-Nachricht."""

    def __init__(self, requester: discord.Member | None = None):
        super().__init__(timeout=None)
        self.requester = requester

    # ------------ Claim --------------------------------------------------
    @ui.button(
        label="Claim",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_claim_button",
    )
    async def claim_button(self, interaction: discord.Interaction, button: ui.Button):
        guild, channel, claimer = (
            interaction.guild,
            interaction.channel,
            interaction.user,
        )

        if not any(r.permissions.administrator for r in claimer.roles):
            await interaction.response.send_message(
                "❌ Nur Admins können Tickets claimen.", ephemeral=True
            )
            await log_to_channel(
                guild, f"{claimer.mention} wollte claimen, fehlende Rechte."
            )
            return

        for m in guild.members:  # Admins stummschalten
            if m != claimer and any(r.permissions.administrator for r in m.roles):
                await channel.set_permissions(m, send_messages=False)
        await channel.set_permissions(
            claimer, send_messages=True, read_message_history=True
        )

        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(
            f"🤺 {claimer.mention} hat das Ticket übernommen."
        )
        await log_to_channel(guild, f"{claimer.mention} hat {channel.name} geclaimt.")

    # ------------ Close --------------------------------------------------
    @ui.button(
        label="Ticket schließen & löschen",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close_button",
    )
    async def close_button(self, interaction: discord.Interaction, button: ui.Button):
        channel, guild, closer = (
            interaction.channel,
            interaction.guild,
            interaction.user,
        )

        requester = self.requester or self._guess_requester(channel)
        if requester:
            await channel.set_permissions(requester, send_messages=False)

        if not channel.name.startswith("closed-"):
            await channel.edit(name=f"closed-{channel.name}")

        transcript = await self._save_transcript(channel)

        embed = discord.Embed(
            title="📁 Archiviertes Ticket",
            color=discord.Color.dark_grey(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(
            name="👤 User",
            value=requester.mention if requester else "unbekannt",
            inline=True,
        )
        embed.add_field(name="🎟️ Ticket", value=channel.name, inline=True)
        embed.add_field(name="🔒 Closed by", value=closer.mention, inline=True)
        embed.set_footer(text="Transkript im Anhang")

        archiv_ch = discord.utils.get(
            guild.text_channels, name=TICKET_ARCHIVE_CATEGORY_NAME
        )
        if archiv_ch:
            await archiv_ch.send(
                embed=embed,
                file=discord.File(transcript, filename=os.path.basename(transcript)),
            )
        else:
            await interaction.response.send_message(
                "⚠️ Kein #archiv-Channel gefunden.", ephemeral=True
            )
            return

        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(
            "✅ Ticket archiviert. Channel wird in 60 s gelöscht.", ephemeral=True
        )

        from bot import message_store

        message_store.remove_ticket(guild.id, channel.id)  # Austragen
        await asyncio.sleep(60)
        await channel.delete()

    # ---------- Helpers --------------------------------------------------
    def _guess_requester(self, ch: discord.TextChannel) -> discord.Member | None:
        # ticket-max-123456789012345678  →  User-ID am Ende
        try:
            uid = int(ch.name.split("-")[-1])
            return ch.guild.get_member(uid)
        except Exception:
            return None

    async def _save_transcript(self, ch: discord.TextChannel) -> str:
        os.makedirs(TRANSCRIPT_FOLDER, exist_ok=True)
        path = f"{TRANSCRIPT_FOLDER}/{ch.name}.txt"
        with open(path, "w", encoding="utf-8") as f:
            async for m in ch.history(limit=None, oldest_first=True):
                ts = m.created_at.strftime("%Y-%m-%d %H:%M")
                author = f"{m.author.name}#{m.author.discriminator}"
                f.write(f"[{ts}] {author}: {m.content or '[EMBED / FILE]'}\n")
        return path
