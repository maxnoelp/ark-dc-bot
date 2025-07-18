import discord
from discord import ui
import requests
from bot.logs_to_channel import log_to_channel
from cogs.bug_report.create_delete_btn import ConfirmBugView


class BugView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(
        label="🐞 Bug melden",
        style=discord.ButtonStyle.blurple,
        custom_id="bug_modal_open",
    )
    async def open_modal(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        print("[DEBUG] Button wurde gedrückt. Modal wird geöffnet.")
        await interaction.response.send_modal(BugModal(self.bot))


class BugModal(ui.Modal):
    def __init__(self, bot):
        super().__init__(title="Bug melden")
        self.bot = bot
        self.add_item(
            ui.TextInput(
                label="Beschreibe den Bug",
                style=discord.TextStyle.long,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bug_text = self.children[0].value
            user = interaction.user

            embed = discord.Embed(
                title="🐞 Neuer Bug-Report",
                description=bug_text,
                color=discord.Color.orange(),
            )
            embed.set_footer(
                text=f"Gemeldet von {user}", icon_url=user.display_avatar.url
            )

            target_channel = discord.utils.get(
                interaction.guild.text_channels, name="bug-tickets"
            )
            if not target_channel:
                await interaction.response.send_message(
                    "Channel `#bug-tickets` nicht gefunden.", ephemeral=True
                )
                return

            view = ConfirmBugView()
            await target_channel.send(embed=embed, view=view)

            log_embed = discord.Embed(
                title="🐞 Bug-Modal übermittelt",
                description=f"{user.mention} hat einen Bug eingereicht.",
                color=discord.Color.red(),
            )
            await log_to_channel(interaction.guild, log_embed)

            await interaction.response.send_message(
                "Bug wurde gemeldet!", ephemeral=True
            )

        except Exception as e:
            print("[ERROR] Fehler im Modal:", e)
            try:
                await interaction.response.send_message(
                    f"Fehler beim Verarbeiten.({e})", ephemeral=True
                )
            except discord.InteractionResponded:
                pass
