import discord, asyncio, os
from dotenv import load_dotenv
from discord.ext import commands
from bot import message_store
from cogs.ticket_cog.ticket import TicketView
from cogs.ticket_cog.close_claim_ticket import CloseView

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ticket_on = os.getenv("TICKET_ON")

intents = discord.Intents.default()
intents.guilds, intents.members = True, True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"{bot.user} connected.")

    # Persistente Views 1× registrieren
    bot.add_view(TicketView())
    bot.add_view(CloseView(requester=None))

    for guild in bot.guilds:
        # Ticket-Nachrichten reaktivieren
        for ch_id, msg_id in message_store.get_tickets(guild.id).items():
            ch = guild.get_channel(ch_id)
            if not ch:
                message_store.remove_ticket(guild.id, ch_id)
                continue
            try:
                msg = await ch.fetch_message(msg_id)
            except discord.NotFound:
                message_store.remove_ticket(guild.id, ch_id)
                continue

            # requester schätzen u. View neu anhängen
            await msg.edit(view=CloseView(requester=None))


async def main():
    async with bot:
        await bot.load_extension("cogs.bug_report.main_class")
        if ticket_on:
            await bot.load_extension("cogs.ticket_cog.ticket")
        await bot.start(TOKEN)


asyncio.run(main())
