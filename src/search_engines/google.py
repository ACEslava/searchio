#External Dependencies
import aiofiles
import io

from asyncio import TimeoutError, gather, sleep
from base64 import standard_b64encode
from bs4 import BeautifulSoup, SoupStrainer
from datetime import datetime, timezone
from dotenv import load_dotenv
from iso639 import languages
from langid import classify as detect
from os import getenv
from os import path as os_path
from PIL import Image, ImageFont, ImageDraw
from re import findall, sub
from re import search as re_search
from selenium.webdriver.support.ui import WebDriverWait
from string import ascii_uppercase, ascii_lowercase, digits
from translate import Translator
from typing import List

#Discord Modules
from discord import Embed
from discord import Message, File, Embed
from discord_components import Button, ButtonStyle
from discord.ext import commands

#Utility Modules
from src.utils import Log, error_handler, Sudo
from src.loadingmessage import get_loading_message
class GoogleSearch:
    def __init__(
        self,
        bot: commands.Bot,
        ctx: commands.Context,
        server_settings: dict,
        user_settings: dict,
        message: Message,
        args: list,
        query: str
    ):
        # formats uule strings for use in locales
        # found this on a random stackoverflow
        def uule(city: str) -> str:
            secret_list = (
                list(ascii_uppercase)
                + list(ascii_lowercase)
                + list(digits)
                + ["-", "_"]
            )

            secret = secret_list[len(city) % len(secret_list)]
            hashed = standard_b64encode(city.encode()).decode().strip("=")
            return f"w+CAIQICI{secret}{hashed}"

        self.bot = bot
        self.ctx = ctx
        self.serverSettings = server_settings
        self.userSettings = user_settings
        self.message = message
        self.args = args if args is not None else []
        self.query = query
                
        # gets uule string based on user settings
        if self.userSettings[self.ctx.author.id]["locale"] is not None:
            uule_parse = uule(self.userSettings[self.ctx.author.id]["locale"])
        else:
            # default uule is Google HQ
            uule_parse = "w+CAIQICI5TW91bnRhaW4gVmlldyxTYW50YSBDbGFyYSBDb3VudHksQ2FsaWZvcm5pYSxVbml0ZWQgU3RhdGVz"

        # creates google search url
        # format: https://google.com/search?pws=0&q=[query]&uule=[uule string]&num=[number of results]&safe=[safesearch status]
        self.url = "".join(
            [
            "https://google.com/search?pws=0&q=",
            self.query.replace(" ", "+"),
            f'{"+-stock+-pinterest" if bool(re_search("image", self.query.lower())) else ""}',
            f"&uule={uule_parse}&num=6"
            f"{'&safe=active' if self.serverSettings[hex(self.ctx.guild.id)]['safesearch'] and not self.ctx.channel.nsfw else ''}"
            ]
        )
        return

    async def __call__(self) -> None:
        if any([
            bool(re_search('translate', self.query.lower())),
            'translate' in self.args
        ]):
            await self.translate()

        elif any([
            bool(re_search('define', self.query.lower())), 
            bool(re_search('meaning', self.query.lower())),
            'define' in self.args
        ]):
            await self.define()

        elif any([
            bool(re_search('weather', self.query.lower())),
            'weather' in self.args
        ]):
            await self.weather()
        
        else: 
            await self.google()
        return
    
    async def google(self) -> None:
        # region utility functions

        # translates unicode codes in links
        def link_unicode_parse(link: str) -> str:
            return sub(r"%(.{2})", lambda m: chr(int(m.group(1), 16)), link)

        # parses image url from html
        def image_url_parser(image) -> str:
            try:
                # searches html for image urls
                imgurl = link_unicode_parse(
                    findall(
                        "(?<=imgurl=).*(?=&imgrefurl)", image.parent.parent["href"]
                    )[0]
                )
                if "encrypted" in imgurl:
                    imgurl = findall(
                        "(?<=imgurl=).*(?=&imgrefurl)",
                        image.findAll("img")[1].parent.parent["href"],
                    )[0]

                return imgurl
            except Exception:
                raise

        # endregion

        # region embed creation functions
        # embed creation for image embeds
        def image_embed(image) -> Embed:
            try:
                # creates and formats the embed
                result_embed = Embed(
                    title=f"Search results for: {self.query[:233]}"
                    f'{"..." if len(self.query) > 233 else ""}'
                )

                # sets the discord embed to the image
                result_embed.set_image(url=image_url_parser(image))
                result_embed.url = self.url
            except:
                result_embed.set_image(url="https://external-preview.redd.it/9HZBYcvaOEnh4tOp5EqgcCr_vKH7cjFJwkvw-45Dfjs.png?auto=webp&s=ade9b43592942905a45d04dbc5065badb5aa3483")
            finally:
                return result_embed

        # embed creation for text embeds
        def text_embed(result) -> Embed:
            # creates and formats the embed
            result_embed = Embed(
                title=f'Search results for: {self.query[:233]}{"..." if len(self.query) > 233 else ""}'
            )

            # google results are separated by divs
            # searches for link in div
            find_link = result.find_all("a", href_="")
            link_list = tuple(a for a in find_link if not a.find("img"))
            link = None
            if len(link_list) != 0:
                try:
                    # parses link from html
                    link = link_unicode_parse(
                        findall(r"(?<=url\?q=).*(?=&sa)", link_list[0]["href"])[0]
                    )
                except:
                    pass
            
            # extracts all meaningful text in the search result by div
            result_find = result.findAll("div")
            divs = tuple(d for d in result_find if not d.find("div"))
            
            titleinfo = [
                " ".join(
                    [
                        string if string != "View all" else ""
                        for string in div.stripped_strings
                    ]
                )
                for div in divs[:2]
            ]
            titleinfo = [f"**{ti}**" for ti in titleinfo if ti != ""]
            if link is not None:
                titleinfo[-1] = link
            
            lines = [
                " ".join(
                    [
                        string if string != "View all" else ""
                        for string in div.stripped_strings
                    ]
                )
                for div in divs[2:]
            ]
            
            printstring = "\n".join(titleinfo+lines)

            # discord prevents embeds longer than 2048 chars
            # truncates adds ellipses to strings longer than 2048 chars
            if len(printstring) > 1024:
                printstring = printstring[:1020] + "..."

            # sets embed description to string
            result_embed.description = sub("\n\n+", "\n\n", printstring)

            # tries to add an image to the embed
            image = result.find("img")
            try:
                result_embed.set_image(url=image_url_parser(image))
            except:
                pass
            result_embed.url = self.url
            return result_embed

        # endregion

        try:
            # checks if image is in search query
            if bool(re_search("image", self.query.lower())):
                has_found_image = True
            else:
                has_found_image = False

            # gets the webscraped html of the google search
            async with self.bot.session.get(
                self.url, 
                headers={'User-Agent':'python-requests/2.25.1'}
            ) as data:
                html = await data.text()
                soup, index = BeautifulSoup(
                    html, 
                    features="lxml",
                    parse_only=SoupStrainer('div',{'id': 'main'})
                ), 3
            
            #Debug HTML output
            # with open('test.html', 'w', encoding='utf-8-sig') as file:
            #     file.write(soup.prettify())

            # if the search returns results
            if soup.find("div", {"id": "main"}) is not None:
                Log.append_to_log(self.ctx, f"{self.ctx.command} results", self.url)
                google_snippet_results = soup.find("div", {"id": "main"}).contents

                # region html processing
                # html div cleanup
                google_snippet_results = [
                    google_snippet_results[resultNumber]
                    for resultNumber in range(3, len(google_snippet_results) - 2)
                ]

                # bad divs to discard
                wrong_first_results = {
                    "Did you mean: ",
                    "Showing results for ",
                    "Tip: ",
                    "See results about",
                    "Related searches",
                    "Including results for ",
                    "Top stories",
                    "People also ask",
                    "Next >",
                }
                # bad div filtering
                google_snippet_results = {
                    result
                    for result in google_snippet_results
                    if not any(
                        badResult in result.strings for badResult in wrong_first_results
                    )
                    or result.strings == ""
                }
                # endregion

                # checks if user searched specifically for images
                embeds = None
                if has_found_image:
                    # searches for the "images for" search result div
                    for results in google_snippet_results:
                        if "Images" in results.strings:
                            images = results.findAll("img", recursive=True)
                            
                            #checks if image wont embed properly
                            bad_urls = [] 
                            async def http_req(index, url):
                                try:
                                    url = image_url_parser(url)
                                except: return
                                
                                async with self.bot.session.get(url, allow_redirects=False) as resp:
                                    if resp.status == 301 or resp.status == 302:
                                        bad_urls.append(index)

                            await gather(
                                *[
                                    http_req(index, url) 
                                    for index, url in enumerate(images)
                                ]
                            )
                            if len(bad_urls) > 0:
                                images = [img for idx, img in enumerate(images) if idx not in bad_urls]
                            
                            #creates embed list
                            embeds = [
                                embed 
                                for embed in list(map(image_embed, images))
                                if embed.description is not (None or '')
                            ]
                            
                            if len(embeds) > 0:
                                del embeds[-1]
                            break

                if embeds is None or len(embeds) == 0:
                    embeds = [
                        embed 
                        for embed in list(map(text_embed, google_snippet_results))
                        if embed.description is not (None or '')
                    ]
                    
                    #Creates search groupings
                    new_embed_list = []
                    i = 0
                    combinedDesc = ''
                    for j in range(len(embeds)):
                        embed_desc = '\n'.join(list(filter(None, embeds[j].description.split('\n'))))
                        if 'image' in embeds[j].to_dict().keys():
                            combinedDesc = ''
                            new_embed_list.append([embeds[j]])
                            i=j
                            continue
                        else:
                            if len(combinedDesc + embed_desc) < 1048:
                                combinedDesc += '\n'+ '\n'+embed_desc
                                continue
                            
                            combinedDesc = ''
                            new_embed_list.append(embeds[i:j+1])
                            i=j
                    new_embed_list.append(embeds[i:j+1])
                    
                    for idx, group in enumerate(new_embed_list):
                        if len(group) == 1: continue
                        combinedDesc = ''
                        for embed in group:
                            combinedDesc += '\n'+'\n'+'\n'.join(list(filter(None, embed.description.split('\n'))))
                        
                        new_embed_list[idx] = [
                            Embed(
                                title=f'Search results for: {self.query[:233]}{"..." if len(self.query) > 233 else ""}',
                                description=combinedDesc,
                                url = self.url
                            )
                        ]    

                    embeds = [i[0] for i in new_embed_list]

                # adds the page numbering footer to the embeds
                for index, item in enumerate(embeds):
                    item.set_footer(
                        text=f"Page {index+1}/{len(embeds)}\nRequested by: {str(self.ctx.author)}"
                    )

                print(
                    self.ctx.author.name + " searched for: " + self.query[:233]
                )

                #finds the first https link
                first_link = None
                for idx, e in enumerate(embeds):
                    try:
                        first_link = next(filter(
                            lambda x: 'https://' in x, e.description.split('\n')
                        ))
                        break
                    except Exception:
                        continue

                # sets the buttons for the search result
                if len(embeds) > 1:
                    buttons = [
                        [{
                            Button(style=ButtonStyle.blue, label="Screenshot", custom_id="scr"): 
                            self.webpage_screenshot
                        },
                        {
                            Button(style=ButtonStyle.blue, label="Screenshot First Result", custom_id="scrfr"): 
                            (self.webpage_screenshot, first_link)
                        }],
                        [
                        {Button(style=ButtonStyle.grey, label="◀️", custom_id="◀️"): None},
                        {Button(style=ButtonStyle.red, label="🗑️", custom_id="🗑️"): None},
                        {Button(style=ButtonStyle.grey, label="▶️", custom_id="▶️"): None}
                        ]
                    ]
                else:
                    buttons = [
                        [{
                            Button(style=ButtonStyle.blue, label="Screenshot", custom_id="scr"): 
                            self.webpage_screenshot
                        },
                        {
                            Button(style=ButtonStyle.blue, label="Screenshot First Result", custom_id="scrfr"): 
                            (self.webpage_screenshot, first_link)
                        }],
                        [{Button(style=ButtonStyle.red, label="🗑️", custom_id="🗑️"): None}]
                    ]

                #search for images button
                if "images" not in self.query.lower():
                    buttons[0].append({
                        Button(style=ButtonStyle.blue, label="Images", custom_id="img", emoji=self.bot.get_emoji(928889019838894090)): 
                        (self.search_google_handler, f'{self.query} images')
                    })

                await Sudo.multi_page_system(self.bot, self.ctx, self.message, tuple(embeds), buttons)
                return

            else:
                embed = Embed(
                    title=f'Search results for: {self.query[:233]}{"..." if len(self.query) > 233 else ""}',
                    description="No results found. Maybe try another search term.",
                )

                embed.set_footer(text=f"Requested by {self.ctx.author}")
                
                buttons = [[
                    Button(style=ButtonStyle.red, label="🗑️", custom_id="🗑️")
                ]]
                
                await Sudo.multi_page_system(self.bot, self.ctx, self.message, (embed,), buttons)
                return

        except TimeoutError:
            raise

        except Exception as e:
            await self.message.delete()
            await error_handler(self.bot, self.ctx, e, self.query)
        finally:
            return

    async def translate(self) -> None:
        try:
            # translate string processing
            query = self.query \
                .lower() \
                .replace('translate','') \
                .strip() \
                .split(" ")


            if len(query) > 1:
                # processes keywords in query for language options
                del query[0]
                if "to" in query:
                    dest_language = languages.get(
                        name=query[query.index("to") + 1].lower().capitalize()
                    ).alpha2
                    del query[query.index("to") + 1]
                    del query[query.index("to")]
                else:
                    dest_language = "en"

                if "from" in query:
                    src_language = languages.get(
                        name=query[query.index("from") + 1].lower().capitalize()
                    ).alpha2
                    del query[query.index("from") + 1]
                    del query[query.index("from")]
                else:
                    src_language = None

                # creates query
                query = " ".join(query)

                # queries Google Translate for translations
                translator = Translator(
                    to_lang=dest_language,
                    from_lang=f"{src_language if src_language is not None else detect(query)[0]}",
                )
                result = translator.translate(query)

                # creates and sends embed
                if isinstance(result, list):
                    result = "\n".join(result)
                embed = Embed(
                    title=f"{languages.get(alpha2=translator.from_lang).name}"
                    + f" to {languages.get(alpha2=translator.to_lang).name} Translation"
                )
                embed.add_field(name=languages.get(alpha2=translator.from_lang).name, value=query)
                embed.add_field(name=languages.get(alpha2=translator.to_lang).name, value=result)
                embed.set_footer(text=f"Requested by {self.ctx.author}")
                # sets the reactions for the search result
                
                buttons = [[
                    {Button(style=ButtonStyle.blue, 
                            label="Google Results", custom_id="google", 
                            emoji=self.bot.get_emoji(928889019838894090)
                    ): self.search_google_handler},
                    {Button(style=ButtonStyle.red, label="🗑️", custom_id="🗑️"): None},
                ]]
                await Sudo.multi_page_system(self.bot, self.ctx, self.message, (embed,), buttons)

            else:
                await self.message.edit(
                    content=f"{get_loading_message()}",
                    embed=None,
                )
                await self.google()

        except KeyError:
            await self.message.clear_reactions()
            await self.message.edit(
                content=f"{get_loading_message()}",
                embed=None,
            )
            await self.google()

        except TimeoutError:
            raise

        except Exception as e:
            await self.message.delete()
            await error_handler(self.bot, self.ctx, e, self.query)
            await self.message.edit(
                content=f"{get_loading_message()}",
                embed=None,
            )
            await self.google()

        finally:
            return

    async def define(self) -> None:
        try:
            # creates the embed for each definition result
            def definition_embed(word, response) -> List[Embed]:
                embeds = []
                for definition in word["definitions"]:
                    embeds.append(
                        Embed(
                            title=f'Definition of: {response["word"]}',
                            description="\n".join(
                                [
                                    f'{response["word"]}',
                                    f'`{response["phonetics"][0]["text"]}`',
                                    "\n",
                                    f'{word["partOfSpeech"]}',
                                    f'{definition["definition"]}',
                                    "\n",
                                ]
                            ),
                        )
                    )

                    embeds[-1].add_field(
                        name="Synonyms",
                        value=
                            ", ".join(definition["synonyms"])
                            if "synonyms" in definition.keys() and len(definition["synonyms"]) > 0
                            else "None"
                    )
                    embeds[-1].add_field(
                        name="Example",
                        value=definition["example"]
                        if "example" in definition.keys() and len(definition["example"]) > 0
                        else "None",
                    )
                    embeds[-1].add_field(
                        name="Pronounciation Guide",
                        value=response["phonetics"][0]["audio"],
                        inline=False,
                    )
                    embeds[
                        -1
                    ].url = f'https://www.merriam-webster.com/dictionary/{response["word"]}'
                return embeds

            # definition string processing
            query = self.query \
                .lower() \
                .replace('define','') \
                .strip() \
                .split(" ")

            # queries dictionary API
            async with self.bot.session.get(
                f'https://api.dictionaryapi.dev/api/v2/entries/en_US/{" ".join(query)}'
            ) as data:
                
                response = await data.json()
            response = response[0]
            # creates embed
            embeds = [
                item
                for sublist in [
                    definition_embed(word, response)
                    for word in response["meanings"]
                ]
                for item in sublist
            ]

            for index, item in enumerate(embeds):
                item.set_footer(
                    text=f"Page {index+1}/{len(embeds)}\n"
                    f"Requested by: {str(self.ctx.author)}"
                )

            if len(embeds) > 1:
                buttons = [
                    [{Button(style=ButtonStyle.blue, 
                            label="Google Results", custom_id="google", 
                            emoji=self.bot.get_emoji(928889019838894090)
                    ): self.search_google_handler}],
                    [
                    {Button(style=ButtonStyle.grey, label="◀️", custom_id="◀️"): None},
                    {Button(style=ButtonStyle.red, label="🗑️", custom_id="🗑️"): None},
                    {Button(style=ButtonStyle.grey, label="▶️", custom_id="▶️"): None}
                    ]
                ]
            else:
                buttons = [[
                    {Button(style=ButtonStyle.blue, 
                            label="Google Results", custom_id="google", 
                            emoji=self.bot.get_emoji(928889019838894090)
                    ): self.search_google_handler},
                    {Button(style=ButtonStyle.red, label="🗑️", custom_id="🗑️"): None},
                ]]

            await Sudo.multi_page_system(self.bot, self.ctx, self.message, tuple(embeds), buttons)

        except TimeoutError:
            raise

        except KeyError:
            await self.message.edit(
                content=f"{get_loading_message()}",
                embed=None,
            )
            await self.google()

        except Exception as e:
            await self.message.delete()
            await error_handler(self.bot, self.ctx, e, self.query)
            await self.message.edit(
                content=f"{get_loading_message()}",
                embed=None,
            )
            await self.google()

        finally:
            return

    async def weather(self) -> None:
        #get necessary images
        async def getImages(imageList:'list[str]'):
            async def http_req(url):
                async with self.bot.session.get(url) as resp:
                    if resp.status == 200:
                        file = await aiofiles.open(
                            file=f'./src/cache/{url.split("/")[-1]}',
                            mode='wb'
                            )
                        await file.write(await resp.read())
                        await file.close()

            await gather(
                *[
                    http_req(url) 
                    for url in imageList
                ]
            )

        try:
            load_dotenv()
            query = self.query \
                .lower() \
                .replace('weather','') \
                .strip()

            OPENWEATHERMAP_TOKEN = getenv("OPENWEATHERMAP_TOKEN")

            #get font from cdn
            if not os_path.exists('./src/cache/NotoSans-Bold.ttf'):
                async with self.bot.session.get(
                    'https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf'
                ) as resp:
                    if resp.status == 200:
                        file = await aiofiles.open(
                            file=f'./src/cache/NotoSans-Bold.ttf',
                            mode='wb'
                            )
                        await file.write(await resp.read())
                        await file.close()

            async with self.bot.session.get(
                f'https://nominatim.openstreetmap.org/search.php?city={query.replace(" ", "+")}&format=jsonv2&limit=10',
                headers={
                    'Accept-Language':'en-US'
                }
            ) as data:

                geocode = await data.json()
                geocode = [
                    g for g in geocode 
                    if g["type"] =='administrative'
                ]
                if len(geocode) == 0:
                    #no results found
                    await self.google()
                    return

            coords = (round(float(geocode[0]['lat']), 4), round(float(geocode[0]['lon']), 4))
            async with self.bot.session.get(
                ''.join([
                    f'https://api.openweathermap.org/data/2.5/onecall?',
                    f'lat={coords[0]}&lon={coords[1]}',
                    f'&exclude=minutely&units=metric&appid={OPENWEATHERMAP_TOKEN}'
                ])
            ) as data:
                json = await data.json()

            #weekdays as integers
            weekDayCodes = {
                0:'Monday',
                1:'Tuesday',
                2:'Wednesday',
                3:'Thursday',
                4:'Friday',
                5:'Saturday',
                6:'Sunday'
            }

            #creating dict with weekday forecast
            forecast = {
                weekDayCodes[datetime.fromtimestamp(i['dt']+json['timezone_offset'], timezone.utc).weekday()]:i 
                for i in json['daily'][1:6]
            }

            im = Image.new(
                mode="RGB", 
                size=(1920,1080),
                color = (47,47,47)
            )
            
            iconCodes = [json["current"]["weather"][0]["icon"]]+[w["weather"][0]["icon"] for w in forecast.values()]
            imageList = set([
                f'https://openweathermap.org/img/wn/{i}@4x.png' 
                for i in iconCodes
                if not os_path.exists(f'./src/cache/{i}@4x.png')
            ])
            
            await getImages(imageList)
            
            #current data
            todayImage = Image.open(f'./src/cache/{json["current"]["weather"][0]["icon"]}@4x.png')
            todayImage = todayImage.resize(
                (int(todayImage.width * 2), int(todayImage.height * 2)),
                resample=Image.ANTIALIAS
            )
            
            im.paste(
                todayImage, 
                (740,200), 
                todayImage
            )
            font = ImageFont.truetype("./src/cache/NotoSans-Bold.ttf", 200)
            
            draw = ImageDraw.Draw(im)
            #region text formatting
            draw.text(
                (450, 470),
                f'{round(json["current"]["temp"])}°C',
                (255,255,255),
                font=font,
                anchor="ms"
            )

            font = ImageFont.truetype("./src/cache/NotoSans-Bold.ttf", 48)

            draw.text(
                (1200, 265),
                weekDayCodes[datetime.fromtimestamp(json["current"]['dt']+json['timezone_offset'], timezone.utc).weekday()],
                (255,255,255),
                font=font
            )

            draw.text(
                (1200, 315),
                f'Precipitation: {json["hourly"][0]["pop"]*100}%',
                (255,255,255),
                font=font
            )

            draw.text(
                (1200, 365),
                f'Humidity: {json["current"]["humidity"]}%',
                (255,255,255),
                font=font
            )

            draw.text(
                (1200, 415),
                f'Wind: {json["current"]["wind_speed"]}m/s @ {json["current"]["wind_deg"]}°',
                (255,255,255),
                font=font
            )

            draw.text(
                (1200, 465),
                json["current"]["weather"][0]["main"],
                (255,255,255),
                font=font
            )

            font = ImageFont.truetype("./src/cache/NotoSans-Bold.ttf", 100)
            city_name = geocode[0]['display_name'].split(', ')
            draw.text(
                (960, 150),
                ', '.join(city_name[::len(city_name)-1]),
                (255,255,255),
                font=font,
                anchor='ms'
            )
            #endregion

            #5 day forecast
            five_day_forcast = []
            for icon in iconCodes[1:]:
                five_day_forcast.append(
                    Image.open(f'./src/cache/{icon}@4x.png')
                )

            x = 200
            for idx, image in enumerate(five_day_forcast):
                im.paste(
                    image, 
                    (x-50,720), 
                    image
                )

                font = ImageFont.truetype("./src/cache/NotoSans-Bold.ttf", 48)

                draw.text(
                    (x+50, 720),
                    list(forecast.keys())[idx],
                    (255,255,255),
                    font=font,
                    anchor="ms"
                )

                temp = list(forecast.values())[idx]['temp']
                draw.text(
                    (x+50, 980),
                    f"{round(temp['min'])}/{round(temp['max'])}",
                    (255,255,255),
                    font=font,
                    anchor="ms"
                )

                x += 344
            
            with io.BytesIO() as image_binary:
                im.save(image_binary, 'PNG')
                image_binary.seek(0)

                file = File(fp=image_binary, filename='image.png')
            embed = Embed()
            embed.set_image(url="attachment://image.png")
            embed.set_footer(text=f"Requested by: {str(self.ctx.author)}")
            
            await self.message.delete()
            self.message = await self.ctx.send(
                embed=embed,
                file=file
            )

            buttons = [[
                {Button(style=ButtonStyle.blue, 
                        label="Google Results", custom_id="google", 
                        emoji=self.bot.get_emoji(928889019838894090)
                ): self.search_google_handler},
                {Button(style=ButtonStyle.red, label="🗑️", custom_id="🗑️"): None},
            ]]
            
            await Sudo.multi_page_system(self.bot, self.ctx, self.message, (embed,), buttons)

        except TimeoutError:
            raise

        except KeyError:
            await self.message.edit(
                content=f"{get_loading_message()}",
                embed=None,
            )
            await self.google()

        except Exception as e:
            await self.message.delete()
            await error_handler(self.bot, self.ctx, e, self.query)
            await self.message.edit(
                content=f"{get_loading_message()}",
                embed=None,
            )
            await self.google()

        finally:
            return
    
    async def search_google_handler(self, new_search:str=None) -> None:
        if new_search is not None:
            self.query = new_search
        await self.message.delete()
        self.message = await self.ctx.send(f"{get_loading_message()}")
        await self.google()
        return

    async def webpage_screenshot(self, url:str=None):
        if url is None: url = self.url
        async with self.ctx.typing():
            self.bot.webdriver.get(url)
            await sleep(1.5)
            
            img = self.bot.webdriver.get_screenshot_as_png()
            embed = Embed()
            embed.set_image(url=f'attachment://{self.query.replace(" ", "_")}.png')
            embed.set_footer(text=f"Requested by: {str(self.ctx.author)}")

            await self.ctx.send(
                embed=embed,
                file=File(fp=io.BytesIO(img), filename=f'{self.query.replace(" ", "_")}.png')
            )
        return