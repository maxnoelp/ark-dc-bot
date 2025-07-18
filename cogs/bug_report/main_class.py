import discord
from discord.ext import commands
from cogs.bug_report.btn_modal import BugView
from bot.check_msg import load_sent_messages, save_sent_message
from cogs.bug_report.create_delete_btn import ConfirmBugView
from cogs.bug_report.finish_bug import FinishBugView


class BugReportCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_name = "bug-reports"

    @commands.Cog.listener()
    async def on_ready(self):
        print("[INFO] Bot ist bereit.")

        sent_messages = load_sent_messages()

        for guild in self.bot.guilds:
            if str(guild.id) in sent_messages:
                print(f"[INFO] Bug-Message existiert bereits für {guild.name}")
                continue

            bug_channel = discord.utils.get(guild.text_channels, name=self.channel_name)

            if bug_channel is None:
                print(
                    f"[WARN] Channel '{self.channel_name}' nicht gefunden in {guild.name}"
                )
                continue

            try:
                msg = await bug_channel.send(
                    embed=discord.Embed(
                        title="Report Bugs",
                        description="**Klicke auf den Button, um Bugs zu melden**",
                        color=discord.Color.red(),
                    ),
                    view=BugView(self.bot),
                )

                save_sent_message(guild.id, msg.id)
                print(f"[INFO] Bug-Message gesendet in {guild.name}")

            except discord.Forbidden:
                print(
                    f"[WARN] Keine Rechte zum Senden in {bug_channel.name} ({guild.name})"
                )
            except Exception as e:
                print(f"[ERROR] Fehler beim Senden in {guild.name}: {e}")


async def setup(bot):
    bot.add_view(ConfirmBugView())
    bot.add_view(FinishBugView())
    bot.add_view(BugView(bot))
    await bot.add_cog(BugReportCog(bot))
