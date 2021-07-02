import asyncio

import discord
import scholarly as scholarly_exceptions
from discord.ext import commands
from fp.fp import FreeProxy
from scholarly import scholarly, ProxyGenerator

from src.utils import Log, error_handler


class ScholarSearch:
    @staticmethod
    async def search(
        bot: commands.Bot,
        ctx: commands.Context,
        message: discord.Message,
        args: tuple,
        search_query: str,
    ):
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

            embed.set_footer(text=f"Requested by {ctx.author}")
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
            embed.set_footer(text=f"Requested by {ctx.author}")
            return embed

        def citation_embeds(result) -> discord.Embed:
            embed = discord.Embed(
                title=result["bib"]["title"],
                description=f"```{scholarly.bibtex(result)}```",
                url=result["eprint_url"]
                if "eprint_url" in result.keys()
                else result["pub_url"],
            )
            embed.set_footer(text=f"Requested by {ctx.author}")
            return embed

        # endregion

        try:
            # region user flags processing

            pg = ProxyGenerator()
            proxy = FreeProxy(rand=True, timeout=1, country_id=["BR"]).get()
            pg.SingleProxy(http=proxy, https=proxy)
            scholarly.use_proxy(pg)

            # args processing
            if args is None:
                results = [next(scholarly.search_pubs(search_query)) for _ in range(5)]
                embeds = list(map(publication_embeds, results))
            elif "author" in args:
                results = [
                    next(scholarly.search_author(search_query)) for _ in range(5)
                ]
                embeds = list(map(author_embeds, results))
            elif "cite" in args:
                results = scholarly.search_pubs(search_query)
                results = [results for _ in range(5)]
                embeds = list(map(citation_embeds, results))
            else:
                await message.edit(content="Invalid flag")
                return
            # endregion

            do_exit, cur_page = False, 0
            await message.add_reaction("🗑️")
            if len(embeds) > 1:
                await message.add_reaction("◀️")
                await message.add_reaction("▶️")

            while not do_exit:
                await message.edit(content=None, embed=embeds[cur_page % len(embeds)])
                reaction, user = await bot.wait_for(
                    "reaction_add",
                    check=lambda reaction_, user_: all(
                        [
                            user_ == ctx.author,
                            str(reaction_.emoji) in ["◀️", "▶️", "🗑️"],
                            reaction_.message == message,
                        ]
                    ),
                    timeout=60,
                )
                await message.remove_reaction(reaction, user)

                if str(reaction.emoji) == "🗑️":
                    await message.delete()
                    do_exit = True
                elif str(reaction.emoji) == "◀️":
                    cur_page -= 1
                elif str(reaction.emoji) == "▶️":
                    cur_page += 1

        except asyncio.TimeoutError:
            raise
        except asyncio.CancelledError:
            pass
        except scholarly_exceptions._navigator.MaxTriesExceededException:
            await message.edit(
                content="Google Scholar is currently blocking our requests. Please try again later"
            )
            Log.append_to_log(ctx, f"{ctx.command} error", "MaxTriesExceededException")
            return

        except Exception as e:
            await error_handler(bot, ctx, e, search_query)
        finally:
            return
