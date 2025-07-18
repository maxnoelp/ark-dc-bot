import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
from discord import ui
from bot.logs_to_channel import log_to_channel
from cogs.ticket_cog.create_ticket_modal import TicketModal
from bot import message_store

load_dotenv()

TICKET_CHANNEL_NAME = os.getenv("TICKET_CHANNEL_NAME")


class Ticket(commands.Cog):
    """Postet genau eine Start-Nachricht in #ticket und speichert deren ID."""

    def __init__(self, bot):
        self.bot, self.channel_name = bot, TICKET_CHANNEL_NAME

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            ch = discord.utils.get(guild.text_channels, name=self.channel_name)
            if not ch:
                await log_to_channel(
                    guild, f"Channel '{self.channel_name}' nicht gefunden."
                )
                continue

            saved = message_store.get_bug(guild.id)
            if saved:
                try:
                    await ch.fetch_message(saved[0])
                    continue  # Nachricht existiert → fertig
                except discord.NotFound:
                    message_store.remove_bug(guild.id, saved[0])

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

            msg = await ch.send(embed=embed, view=TicketView())
            message_store.add_bug(guild.id, msg.id)


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


async def setup(bot):  # py-cord reloadable
    await bot.add_cog(Ticket(bot))
