import discord
import requests
import re
import logging
from discord import ui
from dotenv import load_dotenv  # pip install python-dotenv
import os
from cogs.bug_report.finish_bug import FinishBugView

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}


class ConfirmBugView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="✅ Ja, übernehmen",
        style=discord.ButtonStyle.green,
        custom_id="bug_confirm_accept",
    )
    async def accept_bug(self, interaction: discord.Interaction, _):
        ticket_msg = interaction.message  # Merken, um gleich zu löschen
        ticket_embed = ticket_msg.embeds[0]
        bug_text = ticket_embed.description

        # 1. Branch-Namen erzeugen und anlegen
        branch_name = self._sanitize_branch(bug_text)
        ok, url = await self.create_github_branch(branch_name)

        # 2. Nachricht in #progress
        progress_ch = discord.utils.get(
            interaction.guild.text_channels, name="progress"
        )
        if not progress_ch:
            return await interaction.response.send_message(
                "Channel `#progress` nicht gefunden.", ephemeral=True
            )

        embed = discord.Embed(
            title="🚧 Bug in Bearbeitung",
            description=f"{bug_text}\n\n**Branch:** {url or '– Fehler beim Erstellen –'}",
            color=discord.Color.yellow(),
        )
        embed.set_footer(
            text=f"In Arbeit von {interaction.user}",
            icon_url=interaction.user.display_avatar.url,
        )

        await progress_ch.send(embed=embed, view=FinishBugView())  # ➋ "Fertig"-Button

        # 3. altes Ticket entfernen
        await ticket_msg.delete()

        # 4. Ephemeral-Antwort
        await interaction.response.send_message(
            "Bug verschoben ➡ **#progress** und Branch angelegt.", ephemeral=True
        )

    @ui.button(
        label="❌ Nein", style=discord.ButtonStyle.red, custom_id="bug_confirm_reject"
    )  # ➌  feste ID
    async def reject_bug(self, interaction: discord.Interaction, _):
        await interaction.message.delete()
        await interaction.response.send_message("Bug abgelehnt.", ephemeral=True)

    def _sanitize_branch(self, bug_text):
        # Kürzen & formatieren
        return "bug/" + "-".join(bug_text.strip().lower().split())[:30]

    async def create_github_branch(  # ①  self als 1. Parameter hinzufügen
        self, branch_name: str
    ) -> tuple[bool, str | None]:
        print(f"[INFO] Create Branch called with {branch_name}")
        owner_repo = GITHUB_REPO
        repo_url = f"https://api.github.com/repos/{owner_repo}"

        # Default-Branch ermitteln
        repo_info = requests.get(repo_url, headers=HEADERS)
        if repo_info.status_code != 200:
            logging.error(
                "Repo nicht gefunden oder Token ohne Rechte: %s", repo_info.text
            )
            return False, None

        default_branch = repo_info.json()["default_branch"]

        # SHA des Default-Heads holen
        sha_url = f"{repo_url}/git/ref/heads/{default_branch}"  # Singular ref
        sha_resp = requests.get(sha_url, headers=HEADERS)
        if sha_resp.status_code != 200:
            logging.error(
                "Default-Branch '%s' nicht gefunden: %s", default_branch, sha_resp.text
            )
            return False, None

        sha = sha_resp.json()["object"]["sha"]

        # Neuen Branch anlegen
        payload = {"ref": f"refs/heads/{branch_name}", "sha": sha}
        resp = requests.post(f"{repo_url}/git/refs", json=payload, headers=HEADERS)

        if resp.status_code == 201:
            return True, f"https://github.com/{owner_repo}/tree/{branch_name}"
        if resp.status_code == 422 and "Reference already exists" in resp.text:
            return True, f"https://github.com/{owner_repo}/tree/{branch_name}"
        logging.error("Branch-Erstellung fehlgeschlagen: %s", resp.text)
        return False, None
