import discord


async def log_to_channel(
    guild: discord.Guild,
    message: str | discord.Embed,
    log_channel_name: str = "bot-logs",
    file: discord.File = None,
):
    """
    Sends a message or embed to a specified log channel within a Discord guild.

    Parameters:
    guild (discord.Guild): The Discord guild where the log channel is located.
    message (str | discord.Embed): The message or embed to send to the log channel.
    log_channel_name (str, optional): The name of the log channel. Defaults to "bot-logs".
    file (discord.File, optional): An optional file to send along with the message or embed.

    Returns:
    None
    """

    log_channel = discord.utils.get(guild.text_channels, name=log_channel_name)
    if not log_channel:
        return

    if isinstance(message, discord.Embed):
        await log_channel.send(embed=message, file=file)
    else:
        await log_channel.send(content=message, file=file)
