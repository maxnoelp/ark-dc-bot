# Create, update and delete Tickets

import discord

from discord.ext import commands
from discord import ui
from bot.logs_to_channel import log_to_channel
from cogs.ticket_cog.create_ticket_modal import TicketModal


TICKET_CATEGORY_NAME = "tickets"
TICKET_ARCHIVE_CATEGORY_NAME = "archiv"
TRANSCRIPT_FOLDER = "transcripts"


# ------------------------------------------------------------------------------------------------------------------
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


# ------------------------------------------------------------------------------------------------------------------
# open Modal by button
class TicketView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Ticket öffnen", style=discord.ButtonStyle.primary, emoji="🎫")
    async def ticket_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(TicketModal())


# ------------------------------------------------------------------------------------------------------------------


async def setup(bot):
    await bot.add_cog(Ticket(bot))
