import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
from discord import ui
from bot.logs_to_channel import log_to_channel
from cogs.ticket_cog.create_ticket_modal import TicketModal
from bot import message_store

load_dotenv()

TICKET_CHANNEL_NAME = os.getenv("TICKET_CHANNEL_NAME") or "ticket"
TICKET_CATEGORY_NAME = os.getenv("TICKET_CATEGORY_NAME") or "Tickets"


class Ticket(commands.Cog):
    """Sorgt dafür, dass genau eine Start-Nachricht im Ticket-Channel existiert."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.channel_name = TICKET_CHANNEL_NAME
        self.category_name = TICKET_CATEGORY_NAME

    @commands.Cog.listener()
    async def on_ready(self):
        # Optional: nur einmal ausführen
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            await self.ensure_ticket_setup(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self.ensure_ticket_setup(guild)

    async def ensure_ticket_setup(self, guild: discord.Guild):
        # 1. Kategorie sicherstellen
        category = discord.utils.get(guild.categories, name=self.category_name)
        if not category:
            if guild.me.guild_permissions.manage_channels:
                try:
                    category = await guild.create_category(
                        self.category_name, reason="Ticket System Setup"
                    )
                    print(
                        f"[Ticket] Kategorie '{self.category_name}' erstellt in {guild.name}"
                    )
                except discord.Forbidden:
                    await log_to_channel(
                        guild,
                        f"[ERROR] Keine Rechte um Kategorie '{self.category_name}' zu erstellen.",
                    )
                    return
                except discord.HTTPException as e:
                    await log_to_channel(
                        guild, f"[ERROR] Fehler beim Erstellen der Kategorie: {e}"
                    )
                    return
            else:
                await log_to_channel(
                    guild,
                    f"[ERROR] Fehlende Rechte für Kategorie '{self.category_name}'.",
                )
                return

        # 2. Channel sicherstellen (erst in Kategorie suchen, dann global – falls verschoben)
        ch = discord.utils.get(category.text_channels, name=self.channel_name)
        print(f"[Ticket DEBUG] Channel gesucht: {self.channel_name} in {category.name}")
        print(f"[Ticket DEBUG] Gefundener Channel: {ch}")
        # if not ch:
        #     ch = discord.utils.get(guild.text_channels, name=self.channel_name)

        if not ch:
            if guild.me.guild_permissions.manage_channels:
                try:
                    print(
                        f"[Ticket DEBUG] Guild={guild.name} "
                        f"manage_channels={guild.me.guild_permissions.manage_channels} "
                        f"raw_env='{os.getenv('TICKET_CHANNEL_NAME')}' "
                        f"channel_name_repr={repr(self.channel_name)}"
                    )
                    ch = await guild.create_text_channel(
                        self.channel_name,
                        category=category,
                        reason="Ticket System Setup",
                    )
                    print(
                        f"[Ticket DEBUG] create_text_channel returned: {ch} (id={ch.id if ch else 'None'})"
                    )
                    print(
                        f"[Ticket] Channel '{self.channel_name}' erstellt in {guild.name}"
                    )
                except discord.Forbidden:
                    await log_to_channel(
                        guild,
                        f"Keine Rechte um Channel '{self.channel_name}' zu erstellen.",
                    )
                    return
                except discord.HTTPException as e:
                    await log_to_channel(
                        guild, f"Fehler beim Erstellen des Channels: {e}"
                    )
                    return
            else:
                await log_to_channel(
                    guild, f"Fehlende Rechte für Channel '{self.channel_name}'."
                )
                return

        # 3. Start-Nachricht sicherstellen
        saved_ids = message_store.get_all(guild.id)
        saved_msg_id = saved_ids[0] if saved_ids else None
        print(
            f"[Ticket DEBUG] raw saved_msg_id={saved_msg_id} type={type(saved_msg_id)}"
        )
        if saved_msg_id:
            try:
                await ch.fetch_message(saved_msg_id)
                return  # Nachricht existiert -> fertig
            except discord.NotFound:
                message_store.remove_bug(guild.id, saved_msg_id)

        embed = discord.Embed(
            title="🎫 Projekt Gamma",
            description=(
                "@everyone\nWillkommen im Ticket-Kanal!\n"
                "Klicke unten auf **„Ticket öffnen“**, "
                "um dein Anliegen einzureichen."
            ),
            color=discord.Color.blurple(),
        )
        embed.set_image(url="https://i.imgur.com/yQeP0Lb.jpeg")
        embed.set_footer(text="LG. Das Admin Team 😇")

        try:
            msg = await ch.send(embed=embed, view=TicketView())
        except discord.Forbidden:
            await log_to_channel(
                guild, f"Kann nicht in #{ch.name} posten (Berechtigungen)."
            )
            return
        except discord.HTTPException as e:
            await log_to_channel(guild, f"Fehler beim Senden der Ticket-Nachricht: {e}")
            return

        message_store.add(guild.id, msg.id)
        print(f"[Ticket] Ticket-Nachricht erstellt ({msg.id}) in {guild.name}")


class TicketView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Ticket öffnen",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="ticket_open_button",
    )
    async def ticket_button(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(TicketModal())


async def setup(bot: commands.Bot):
    await bot.add_cog(Ticket(bot))
    # Persistente View registrieren (nur einmal nötig)
    bot.add_view(TicketView())
