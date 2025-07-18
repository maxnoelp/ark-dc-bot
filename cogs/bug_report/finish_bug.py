import discord
from discord import ui


class FinishBugView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="🏁 Fertig", style=discord.ButtonStyle.green, custom_id="bug_finish_done"
    )  # ➊  feste ID
    async def finish_bug(self, interaction: discord.Interaction, _):
        # Nachricht als erledigt markieren
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.title = "✅ Bug erledigt"

        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message(
            "Bug als **fertig** markiert.", ephemeral=True
        )
