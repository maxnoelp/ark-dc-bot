import discord
import asyncio
import os
from dotenv import load_dotenv
from discord import ui
from cogs.ticket_cog.close_claim_ticket import CloseView
from bot import message_store

load_dotenv()
TICKET_CATEGORY_NAME = os.getenv("TICKET_CATEGORY_NAME")


class TicketModal(ui.Modal, title="🎫 Ticket erstellen"):
    anliegen = ui.TextInput(
        label="Was ist dein Anliegen?", style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild

        # Kategorie
        category = discord.utils.get(
            guild.categories, name=TICKET_CATEGORY_NAME
        ) or await guild.create_category(TICKET_CATEGORY_NAME)

        # Channel-Name
        channel_name = f"ticket-{interaction.user.name}-{interaction.user.id}"

        # Rechte
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

        # Channel anlegen
        ticket_ch = await category.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            topic=f"Ticket von {interaction.user} | Anliegen-ID: {interaction.id}",
        )

        # Erste Nachricht + Buttons
        embed = discord.Embed(
            title="🎫 Neues Ticket",
            description=f"**Ticket von {interaction.user.mention}**\n\n"
            f"**Anliegen:**\n{self.anliegen.value}",
            color=discord.Color.green(),
        )
        view = CloseView(requester=interaction.user)
        first_msg = await ticket_ch.send(embed=embed, view=view)

        # im JSON speichern
        message_store.add_ticket(guild.id, ticket_ch.id, first_msg.id)

        # Bestätigung
        ok_msg = await ticket_ch.send(
            f"{interaction.user.mention} ✅ Dein Ticket wurde erstellt. "
            "Ein Teammitglied meldet sich bald!"
        )
        await interaction.response.send_message(
            f"✅ Dein Ticket wurde erstellt: {ticket_ch.mention}", ephemeral=True
        )

        await asyncio.sleep(90)
        await ok_msg.delete()
