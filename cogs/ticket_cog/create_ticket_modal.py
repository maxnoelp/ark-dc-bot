import discord
import asyncio

from discord import ui
from bot.logs_to_channel import log_to_channel
from cogs.ticket_cog.close_claim_ticket import CloseView

TICKET_CATEGORY_NAME = "tickets"


# Modal
class TicketModal(ui.Modal, title="🎫 Ticket erstellen"):
    anliegen = ui.TextInput(
        label="Was ist dein Anliegen?", style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):
        """
        This function is called when the user submits the ticket form.
        It creates a new ticket channel and sends a confirmation message to the user.
        The ticket channel is configured to only allow the user and the bot to view and post messages.
        The confirmation message is deleted after 5 minutes.
        """

        guild = interaction.guild

        # 1) search for category
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        # 2) generate channel name
        channel_name = f"ticket-{interaction.user.name}-{interaction.user.id}"

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

        # 4) create channel
        ticket_channel = await category.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            topic=f"Ticket von {interaction.user} | Anliegen-ID: {interaction.id}",
        )

        # 5) send embed
        embed = discord.Embed(
            title="🎫 Neues Ticket",
            description=f"**Ticket von {interaction.user.mention}**\n\n**Anliegen:**\n{self.anliegen.value}",
            color=discord.Color.green(),
        )
        view = CloseView(requester=interaction.user)
        await ticket_channel.send(embed=embed, view=view)

        # 6) send confirmation
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

        await interaction.response.send_message(
            f"✅ Dein Ticket wurde erstellt: {ticket_channel.mention}", ephemeral=True
        )

        await asyncio.sleep(90)
        await confirmation.delete()
