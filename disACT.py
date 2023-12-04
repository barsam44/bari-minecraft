import discord
from discord.ext.commands import Bot
from discord.ext import commands
import asyncio

PREFIX = ("$")
bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())
@bot.event
async def on_ready():
    activity = discord.Game(name="hello world", type=1)
    await bot.change_presence(status=discord.Status.idle, activity=activity)
    print("Bot is ready!")

# Replace 'your_token_here' with your actual Discord bot token
bot.run('MTA1OTQ1MzkxNDUxODQwOTM2Nw.GAQ9fY.0QwLHt1PIW5nMyiC7Di8TLPs1bm5_kxvOb_HuU')