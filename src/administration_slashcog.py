from discord_slash.client import SlashCommand
from src.utils import Sudo, Log, error_handler
from datetime import datetime
from yaml import load, FullLoader

import discord
from discord_slash import cog_ext, SlashContext
from discord.ext import commands

with open('serverSettings.yaml', 'r') as data:
    guild_ids = [int(x,0) for x in list(load(data, FullLoader).keys())]

class AdministrationSlash(commands.Cog, name="Administration Slash"):
    def __init__(self, bot):
        self.bot = bot
        return

    async def cog_before_invoke(self, ctx):
        self.bot.userSettings = Sudo.user_settings_check(self.bot.userSettings, ctx.author.id)
        Sudo.save_configs(self.bot)
        return

    @cog_ext.cog_slash(
        name='ping',
        description="Sends SearchIO's DiscordAPI connection latency")
    async def ping(self, ctx:SlashContext):
        try:
            beforeTime = datetime.now()
            message = await ctx.send(content='Testing')
            serverLatency = datetime.now() - beforeTime
            embed = discord.Embed(description='\n'.join(
                            [f'Message Send Time: `{round(serverLatency.total_seconds()*1000, 2)}ms`',
                            f'API Heartbeat: `{round(self.bot.latency, 2)*100}ms`']))
            embed.set_footer(text=f'Requested by {ctx.author}')
            await message.edit(content='', embed=embed)
        except Exception as e:
            await error_handler(self.bot, ctx, e)
        finally: return

def setup(bot):
    bot.add_cog(AdministrationSlash(bot))
    return