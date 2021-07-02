from src.utils import Log, ErrorHandler
from src.loadingmessage import get_loading_message
from bs4 import BeautifulSoup
from iso639 import languages as Languages
from translate import Translator
from discord import Embed
from base64 import standard_b64encode
from requests import get
from asyncio import TimeoutError, gather
from string import ascii_uppercase, ascii_lowercase, digits
from re import findall, sub, search
from langid import classify as detect
class GoogleSearch:
   def __init__(self, bot, ctx, serverSettings, userSettings, message, searchQuery):
      self.bot = bot
      self.ctx = ctx
      self.serverSettings = serverSettings
      self.userSettings = userSettings
      self.message = message
      self.searchQuery = searchQuery
      return

   async def search(self):      
      #region utility functions

      #translates unicode codes in links
      def linkUnicodeParse(link: str): 
         return sub(r"%(.{2})",lambda m: chr(int(m.group(1),16)),link)

      #formats uule strings for use in locales
      #found this on a random stackoverflow
      def uule(city: str) -> str: 
         secret_list = list(ascii_uppercase) + \
            list(ascii_lowercase) + list(digits) + ["-", "_"]

         secret = secret_list[len(city) % len(secret_list)]
         hashed = standard_b64encode(city.encode()).decode().strip("=")
         return f"w+CAIQICI{secret}{hashed}"
      
      #parses image url from html
      def imageURLParser(image):
         try:
            #searches html for image urls
            imgurl = linkUnicodeParse(findall("(?<=imgurl=).*(?=&imgrefurl)", image.parent.parent["href"])[0])
            if "encrypted" in imgurl:
                  imgurl = findall("(?<=imgurl=).*(?=&imgrefurl)", image.findAll("img")[1].parent.parent["href"])[0]
            # imgurl = findall("(?<=\=).*(?=&imgrefurl)", image["href"])[0]
            return imgurl
         except: raise
      #endregion
      
      #region embed creation functions
      #embed creation for image embeds
      def imageEmbed(image):
         try:
            #creates and formats the embed 
            resultEmbed = Embed(
               title=f'Search results for: {self.searchQuery[:233]}{"..." if len(self.searchQuery) > 233 else ""}'
            )

            #sets the discord embed to the image
            resultEmbed.set_image(url=imageURLParser(image))
            resultEmbed.url = url
         except: 
            resultEmbed.description = 'Image failed to load'
         finally: return resultEmbed

      #embed creation for text embeds
      def textEmbed(result):
         #creates and formats the embed
         resultEmbed = Embed(title=f'Search results for: {self.searchQuery[:233]}{"..." if len(self.searchQuery) > 233 else ""}') 

         #google results are separated by divs
         #extracts all meaningful text in the search result by div
         resultFind = result.findAll('div')
         divs = tuple(d for d in resultFind if not d.find('div'))
         lines = tuple(
            ' '.join(
               [string if string != 'View all' else '' for string in div.stripped_strings]
            ) for div in divs
         )
         printstring = '\n'.join(lines)

         #discord prevents embeds longer than 2048 chars
         #truncates adds ellipses to strings longer than 2048 chars
         if len(printstring) > 2048:
            printstring = printstring[:2045] + '...'

         #sets embed description to string
         resultEmbed.description = sub("\n\n+", "\n\n", printstring)

         #searches for link in div
         findLink = result.findAll("a", href_="")
         link_list = tuple(a for a in findLink if not a.find("img")) 
         if len(link_list) != 0: 
            try:
               #parses link from html
               link = linkUnicodeParse(findall("(?<=url\?q=).*(?=&sa)", link_list[0]["href"])[0])
               
               #adds link to embed
               resultEmbed.add_field(name="Relevant Link", value=link)
               print(" link: " + link)
            except:
               print("adding link failed")

         # tries to add an image to the embed
         image = result.find("img")
         try:
            resultEmbed.set_image(url=imageURLParser(image))
         except: 
            pass
         resultEmbed.url = url
         return resultEmbed
      #endregion 
      
      try:
         #checks if image is in search query     
         if bool(search('image', self.searchQuery.lower())):
            hasFoundImage = True
         else: hasFoundImage = False 

         #gets uule string based on user settings
         if self.userSettings[self.ctx.author.id]['locale'] is not None: 
            uuleParse = uule(self.userSettings[self.ctx.author.id]['locale'])
         else: 
            #default uule is Google HQ
            uuleParse = 'w+CAIQICI5TW91bnRhaW4gVmlldyxTYW50YSBDbGFyYSBDb3VudHksQ2FsaWZvcm5pYSxVbml0ZWQgU3RhdGVz' 
         
         #creates google search url
         #format: https://google.com/search?pws=0&q=[query]&uule=[uule string]&num=[number of results]&safe=[safesearch status]
         url = (''.join([
               "https://google.com/search?pws=0&q=", 
               self.searchQuery.replace(" ", "+"), f'{"+-stock+-pinterest" if hasFoundImage else ""}',
               f"&uule={uuleParse}&num=5{'&safe=active' if self.serverSettings[hex(self.ctx.guild.id)]['safesearch']and not self.ctx.channel.nsfw else ''}"
            ])
         )

         #gets the webscraped html of the google search
         response = get(url)
         soup, index = BeautifulSoup(response.text, features="lxml"), 3

         #Debug HTML output
         # with open('test.html', 'w', encoding='utf-8-sig') as file:
         #    file.write(soup.prettify())

         #if the search returns results
         if soup.find("div", {"id": "main"}) is not None:
            Log.appendToLog(self.ctx, f"{self.ctx.command} results", url)
            googleSnippetResults = soup.find("div", {"id": "main"}).contents

            #region html processing
            #html div cleanup
            googleSnippetResults = [googleSnippetResults[resultNumber] for resultNumber in range(3, len(googleSnippetResults)-2)]
            
            #bad divs to discard
            wrongFirstResults = {"Did you mean: ", "Showing results for ", "Tip: ", "See results about", "Including results for ", "Related searches", "Top stories", 'People also ask', 'Next >'}
            #bad div filtering
            googleSnippetResults = {result for result in googleSnippetResults if not any(badResult in result.strings for badResult in wrongFirstResults) or result.strings==''}
            #endregion
            
            #checks if user searched specifically for images
            images, embeds = None, None
            if hasFoundImage:
               #searches for the "images for" search result div
               for results in googleSnippetResults:
                  if 'Images' in results.strings: 
                     images = results.findAll("img", recursive=True)
                     embeds = list(map(imageEmbed, images))
                     if len(embeds) > 0:
                        del embeds[-1]
                     break
            
            if embeds == None:
               embeds = list(map(textEmbed, googleSnippetResults))
            
            print(self.ctx.author.name + " searched for: "+self.searchQuery[:233]) 

            #adds the page numbering footer to the embeds
            for index, item in enumerate(embeds):
               item.set_footer(text=f'Page {index+1}/{len(embeds)}\nRequested by: {str(self.ctx.author)}') 
            
            #sets the reactions for the search result
            if len(embeds) > 1:
               await gather(
                  self.message.add_reaction('🗑️'), 
                  self.message.add_reaction('◀️'), 
                  self.message.add_reaction('▶️')
               )
            else: 
               await self.message.add_reaction('🗑️')

            #multipage result display 
            doExit, curPage = False, 0
            while doExit == False:
               try:
                  await self.message.edit(content=None, embed=embeds[curPage%len(embeds)])
                     
                  reaction, user = await self.bot.wait_for(
                     "reaction_add", 
                     check=lambda reaction, user: 
                        all([
                           user == self.ctx.author, 
                           str(reaction.emoji) in ["◀️", "▶️", "🗑️"], 
                           reaction.message == self.message
                        ]), 
                     timeout=60
                  )
                  await self.message.remove_reaction(reaction, user)
                  
                  if str(reaction.emoji) == '🗑️':
                     await self.message.delete()
                     doExit = True
                  elif str(reaction.emoji) == '◀️':
                     curPage-=1
                  elif str(reaction.emoji) == '▶️':
                     curPage+=1
         
               except TimeoutError:
                  await self.message.clear_reactions() 
                  raise

         else:
            embed = Embed(title=f'Search results for: {self.searchQuery[:233]}{"..." if len(self.searchQuery) > 233 else ""}',
               description = 'No results found. Maybe try another search term.')
         
            embed.set_footer(text=f"Requested by {self.ctx.author}")
            await self.message.edit(content=None, embed=embed)
            try:
               await self.message.add_reaction('🗑️')
               reaction, user = await self.bot.wait_for("reaction_add", check=lambda reaction, user: user == self.ctx.author and reaction.message == self.message and str(reaction.emoji) == "🗑️", timeout=60)
               if str(reaction.emoji) == '🗑️':
                  await self.message.delete()
                  
            except TimeoutError: 
               raise
      
      except TimeoutError: 
         raise

      except Exception as e:
         await self.message.delete()
         await ErrorHandler(self.bot, self.ctx, e, self.searchQuery)
      finally: return

   async def translate(self):
      try:
         #translate string processing
         query = self.searchQuery.lower().split(' ')
         
         if len(query) > 1:
            #processes keywords in query for language options
            del query[0]
            if "to" in query:
               destLanguage = Languages.get(name=query[query.index('to')+1].lower().capitalize()).alpha2
               del query[query.index('to')+1]
               del query[query.index('to')]
            else: destLanguage = 'en'

            if "from" in query:
               srcLanguage = Languages.get(name=query[query.index('from')+1].lower().capitalize()).alpha2
               del query[query.index('from')+1]
               del query[query.index('from')]
            else: srcLanguage = None

            #creates query
            query = ' '.join(query)

            #queries Google Translate for translations
            translator = Translator(to_lang=destLanguage, from_lang=f'{srcLanguage if srcLanguage != None else detect(query)[0]}')
            result = translator.translate(query)
            
            #creates and sends embed
            if isinstance(result, list): result = '\n'.join(result)
            embed = Embed(title=f"{Languages.get(alpha2=translator.from_lang).name}" +
               f" to {Languages.get(alpha2=translator.to_lang).name} Translation", 
               description = result + '\n\nReact with 🔍 to search Google')
            embed.set_footer(text=f"Requested by {self.ctx.author}")
            await self.message.edit(content=None, embed=embed)
            
            #waits for user reaction options
            await self.message.add_reaction('🗑️')
            await self.message.add_reaction('🔍')
            reaction, user = await self.bot.wait_for("reaction_add", check=lambda reaction, user: user == self.ctx.author and str(reaction.emoji) in ["🔍", "🗑️"], timeout=60)
            
            if str(reaction.emoji) == '🗑️':
               await self.message.delete()
               return
            
            #deletes translation and gives the user the Google results
            elif str(reaction.emoji) == '🔍':
               await self.message.clear_reactions()
               await self.message.edit(content=f'{get_loading_message()} <a:loading:829119343580545074>', embed=None)
               await self.search()
               pass
         
         else:
            await self.message.edit(content=f'{get_loading_message()} <a:loading:829119343580545074>', embed=None)
            await self.search()

      except KeyError:
         await self.message.clear_reactions()
         await self.message.edit(content=f'{get_loading_message()} <a:loading:829119343580545074>', embed=None)
         await self.search()

      except TimeoutError: 
         raise

      except Exception as e:
         await self.message.delete()
         await ErrorHandler(self.bot, self.ctx, e, self.searchQuery)
         await self.message.edit(content=f'{get_loading_message()} <a:loading:829119343580545074>', embed=None)
         await self.search()
      
      finally: return

   async def define(self):
      try:
         #creates the embed for each definition result
         def definitionEmbed(word, response):
               embed = []
               for definition in word['definitions']:      
                  embed.append(Embed( 
                     title=f'Definition of: {response["word"]}',
                     description='\n'.join([
                        f'{response["word"]}',
                        f'`{response["phonetics"][0]["text"]}`',
                        '\n',
                        f'{word["partOfSpeech"]}', 
                        f'{definition["definition"]}', '\n'])
                  ))
                  embed[-1].add_field(name='Synonyms', value=", ".join(definition["synonyms"]) if "synonyms" in definition.keys() else "None")
                  embed[-1].add_field(name='Example', value = definition["example"] if "example" in definition.keys() else "None")
                  embed[-1].add_field(name='Pronounciation Guide', value=response["phonetics"][0]["audio"], inline=False)
                  embed[-1].url = f'https://www.merriam-webster.com/dictionary/{response["word"]}'
               return embed

         #definition string processing  
         query = self.searchQuery.lower().split(' ')
         
         if len(query) > 1:
            #queries dictionary API
            response = get(f'https://api.dictionaryapi.dev/api/v2/entries/en_US/{" ".join(query[1:])}')
            response = response.json()[0]
            
            #creates embed
            embeds = [item for sublist in [definitionEmbed(word, response) for word in response['meanings']] for item in sublist]
            for index, item in enumerate(embeds): 
               item.set_footer(text=f'Page {index+1}/{len(embeds)}\nReact with 🔍 to search Google\nRequested by: {str(self.ctx.author)}')

            #user react option system
            doExit, curPage = False, 0
            await self.message.add_reaction('🗑️')
            await self.message.add_reaction('🔍')
            if len(embeds) > 1:
               await self.message.add_reaction('◀️')
               await self.message.add_reaction('▶️')
            
            #multipage definition display
            while 1:
               await self.message.edit(content=None, embed=embeds[curPage%len(embeds)])
               reaction, user = await self.bot.wait_for("reaction_add", check=lambda reaction, user: all([user == self.ctx.author, str(reaction.emoji) in ["◀️", "▶️", "🗑️",'🔍'], reaction.message == self.message]), timeout=60)
               await self.message.remove_reaction(reaction, user)

               if str(reaction.emoji) == '🗑️':
                  await self.message.delete()
                  return
               elif str(reaction.emoji) == '◀️':
                  curPage-=1
               elif str(reaction.emoji) == '▶️':
                  curPage+=1
               
               #gives the user Google results
               elif str(reaction.emoji) == '🔍':
                  await self.message.clear_reactions()
                  await self.message.edit(content=f'{get_loading_message()} <a:loading:829119343580545074>', embed=None)
                  await self.search()
                  break

         else: 
            await self.message.edit(content=f'{get_loading_message()} <a:loading:829119343580545074>', embed=None)
            await self.search()
         

      except TimeoutError: 
         raise

      except Exception as e:
         await self.message.delete()
         await ErrorHandler(self.bot, self.ctx, e, self.searchQuery)
         await self.message.edit(content=f'{get_loading_message()} <a:loading:829119343580545074>', embed=None)
         await self.search()
      
      finally: return
