import os
import discord
import asyncio
from dotenv import load_dotenv
from discord.ext import commands
from cogs.ticket import TicketView

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    bot.add_view(TicketView())


# @bot.event  # ← fehlte zuvor
# async def on_message(message):
#     if message.author == bot.user:
#         return
#     if message.content == "!ping":
#         await message.channel.send("Pong!")


async def main():
    async with bot:
        await bot.load_extension("cogs.ticket")
        await bot.start(TOKEN)


asyncio.run(main())
