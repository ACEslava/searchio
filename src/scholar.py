import asyncio

import discord
import scholarly as scholarly_exceptions
from discord.ext import commands
from fp.fp import FreeProxy
from scholarly import scholarly, ProxyGenerator

from src.utils import Log, error_handler, Sudo


class ScholarSearch:
    def __init__(
        self,
        bot: commands.Bot,
        ctx: commands.Context,
        server_settings: dict,
        user_settings: dict,
        message: discord.Message,
        args: list,
        query: str
    ):
        self.bot = bot
        self.ctx = ctx
        self.serverSettings = server_settings
        self.userSettings = user_settings
        self.message = message
        self.args = args
        self.query = query
        return
    
    async def __call__(self):
        UserCancel = KeyboardInterrupt
        
        # region various embed types creation
        def publication_embeds(result) -> discord.Embed:
            embed = discord.Embed(
                title=result["bib"]["title"],
                description=result["bib"]["abstract"],
                url=result["eprint_url"]
                if "eprint_url" in result.keys()
                else result["pub_url"],
            )
            embed.add_field(
                name="Authors",
                value=", ".join(result["bib"]["author"]).strip(),
                inline=True,
            )

            embed.add_field(name="Publisher", value=result["bib"]["venue"], inline=True)
            embed.add_field(
                name="Publication Year", value=result["bib"]["pub_year"], inline=True
            )
            embed.add_field(
                name="Cited By",
                value=result["num_citations"]
                if "num_citations" in result.keys()
                else "0",
                inline=True,
            )

            embed.add_field(
                name="Related Articles",
                value=f'https://scholar.google.com{result["url_related_articles"]}',
                inline=True,
            )

            embed.set_footer(text=f"Requested by {self.ctx.author}")
            return embed

        def author_embeds(result) -> discord.Embed:
            embed = discord.Embed(title=result["name"])
            embed.add_field(
                name="Cited By", value=f"{result['citedby']} articles", inline=True
            )
            embed.add_field(name="Scholar ID", value=result["scholar_id"], inline=True)
            embed.add_field(
                name="Affiliation",
                value=result["affiliation"]
                if "affiliation" in result.keys()
                else "None",
                inline=True,
            )
            embed.add_field(
                name="Interests",
                value=f"{', '.join(result['interests']) if 'interests' in result.keys() else 'None'}",
                inline=True,
            )
            embed.set_image(url=result["url_picture"])
            embed.set_footer(text=f"Requested by {self.ctx.author}")
            return embed

        def citation_embeds(result) -> discord.Embed:
            embed = discord.Embed(
                title=result["bib"]["title"],
                description=f"```{scholarly.bibtex(result)}```",
                url=result["eprint_url"]
                if "eprint_url" in result.keys()
                else result["pub_url"],
            )
            embed.set_footer(text=f"Requested by {self.ctx.author}")
            return embed

        # endregion

        try:
            # region user flags processing

            pg = ProxyGenerator()
            proxy = FreeProxy(rand=True, timeout=1, country_id=["BR"]).get()
            pg.SingleProxy(http=proxy, https=proxy)
            scholarly.use_proxy(pg)

            # self.args processing
            if self.args is None:
                results = [next(scholarly.search_pubs(self.query)) for _ in range(5)]
                embeds = list(map(publication_embeds, results))
            elif "author" in self.args:
                results = [
                    next(scholarly.search_author(self.query)) for _ in range(5)
                ]
                embeds = list(map(author_embeds, results))
            elif "cite" in self.args:
                results = scholarly.search_pubs(self.query)
                results = [results for _ in range(5)]
                embeds = list(map(citation_embeds, results))
            else:
                await self.message.edit(content="Invalid flag")
                return
            # endregion

            # sets the reactions for the search result
            if len(embeds) > 1:
                emojis = {"🗑️":None,"◀️":None,"▶️":None}
            else:
                emojis = {"🗑️":None}

            await Sudo.multi_page_system(self.bot, self.ctx, self.message, tuple(embeds), emojis)
            return

        except asyncio.TimeoutError:
            raise
        except (asyncio.CancelledError, discord.errors.NotFound):
            pass
        except scholarly_exceptions._navigator.MaxTriesExceededException:
            await self.message.edit(
                content="Google Scholar is currently blocking our requests. Please try again later"
            )
            Log.append_to_log(self.ctx, f"{self.ctx.command} error", "MaxTriesExceededException")
            return

        except Exception as e:
            await error_handler(self.bot, self.ctx, e, self.query)
        finally:
            return
