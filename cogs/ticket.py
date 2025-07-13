import discord
from discord.ext import commands
from discord import ui
import datetime
import os
import asyncio

TICKET_CATEGORY_NAME = "tickets"
TICKET_ARCHIVE_CATEGORY_NAME = "archiv"
TRANSCRIPT_FOLDER = "transcripts"


# Modal
class TicketModal(ui.Modal, title="🎫 Ticket erstellen"):
    anliegen = ui.TextInput(
        label="Was ist dein Anliegen?", style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Wird ausgeführt, wenn der User das Modal abschickt."""
        guild = interaction.guild
        # admin_roles = [
        #     role
        #     for role in guild.roles
        #     if role.permissions.administrator and role != guild.default_role
        # ]

        # 1) Kategorie suchen oder anlegen
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        # 2) Channel-Name generieren
        channel_name = (
            f"ticket-{interaction.user.name}-{interaction.user.discriminator}"
        )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True
            ),
        }

        for role in guild.roles:
            if role.permissions.administrator and role != guild.default_role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True
                )

        # 4) Channel erstellen
        ticket_channel = await category.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            topic=f"Ticket von {interaction.user} | Anliegen-ID: {interaction.id}",
        )

        # 5) Begrüßungs-Embed + Close-Button senden
        embed = discord.Embed(
            title="🎫 Neues Ticket",
            description=f"**Ticket von {interaction.user.mention}**\n\n**Anliegen:**\n{self.anliegen.value}",
            color=discord.Color.green(),
        )
        view = CloseView(requester=interaction.user)
        await ticket_channel.send(embed=embed, view=view)

        # 6) User eine Bestätigung schicken
        confirmation = await ticket_channel.send(
            f"{interaction.user.mention} ✅ Dein Ticket wurde erstellt. Ein Teammitglied meldet sich bald!"
        )

        # log start

        log_embed = discord.Embed(
            title="📥 Ticket wurde erstellt",
            color=discord.Color.blue(),
            timestamp=interaction.created_at,
        )
        log_embed.add_field(
            name="👤 Benutzer", value=interaction.user.mention, inline=True
        )
        log_embed.add_field(
            name="📍 Ticket-Channel", value=ticket_channel.mention, inline=True
        )
        log_embed.add_field(
            name="📝 Anliegen", value=self.anliegen.value[:1024], inline=False
        )
        log_embed.set_footer(text=f"User ID: {interaction.user.id}")

        await log_to_channel(guild, log_embed)

        # log end

        await interaction.response.send_message(confirmation, ephemeral=True)

        await asyncio.sleep(300)
        await confirmation.delete()


# ---------- View + Button zum Schließen ----------
class CloseView(ui.View):
    def __init__(self, requester: discord.Member):
        super().__init__(timeout=None)
        self.requester = requester

    @ui.button(label="Claim", style=discord.ButtonStyle.primary, emoji="🤺")
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

    @ui.button(label="Ticket schließen", style=discord.ButtonStyle.danger, emoji="🛑")
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

        # 4. Nachrichtenverlauf speichern
        transcript_path = await self.save_transcript(channel)

        # 5. Archiv-Embed erstellen
        embed = discord.Embed(
            title="📁 Archiviertes Ticket",
            color=discord.Color.dark_grey(),
            timestamp=datetime.datetime.utcnow(),
        )
        embed.add_field(name="👤 User", value=self.requester.mention, inline=True)
        embed.add_field(name="🎟️ Ticket", value=channel.name, inline=True)
        embed.add_field(name="📅 Created by", value=self.requester.name, inline=True)
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
            "✅ Ticket geschlossen & im Archiv geloggt.", ephemeral=True
        )
        await log_to_channel(
            guild, f"📁 Ticket {channel.name} wurde von {closer.mention} geschlossen."
        )

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


# open Modal by button
class TicketView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Ticket öffnen", style=discord.ButtonStyle.primary, emoji="🎫")
    async def ticket_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(TicketModal())


# command for ui
class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_name = "ticket"  # Channel, in dem automatisch gepostet wird

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            ticket_channel = discord.utils.get(
                guild.text_channels, name=self.channel_name
            )
            if ticket_channel:
                # Optional: Lösche alte Bot-Messages zuerst
                async for msg in ticket_channel.history(limit=10):
                    if msg.author == self.bot.user:
                        await msg.delete()

                embed = discord.Embed(
                    title="🎫 Projekt Gamma",
                    description=(
                        "@everyone\n"
                        "Willkommen im Ticket-Kanal!\n"
                        "Klicke unten auf **„Ticket öffnen“**, um dein Anliegen einzureichen."
                    ),
                    color=discord.Color.blurple(),
                )
                embed.set_image(
                    url="https://i.imgur.com/yQeP0Lb.jpeg"
                )  # Bild optional anpassen
                embed.set_footer(text="LG. Das Admin Team 😇")

                await ticket_channel.send(embed=embed, view=TicketView())
            else:
                await log_to_channel(
                    guild,
                    f"Channel '{self.channel_name}' nicht gefunden in {guild.name}.",
                )


async def log_to_channel(
    guild: discord.Guild,
    message: str | discord.Embed,
    log_channel_name: str = "bot-logs",
    file: discord.File = None,
):
    """Sendet eine Nachricht oder ein Embed in den angegebenen Log-Channel."""
    log_channel = discord.utils.get(guild.text_channels, name=log_channel_name)
    if not log_channel:
        return

    if isinstance(message, discord.Embed):
        await log_channel.send(embed=message, file=file)
    else:
        await log_channel.send(content=message, file=file)


async def setup(bot):
    await bot.add_cog(Ticket(bot))
