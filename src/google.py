from src.utils import Log, ErrorHandler
from src.loadingmessage import LoadingMessage
from bs4 import BeautifulSoup
from google_trans_new import google_translator
from iso639 import languages as Languages
from discord import Embed
from base64 import standard_b64encode
from requests import get
from asyncio import TimeoutError, gather
from string import ascii_uppercase, ascii_lowercase, digits
from re import findall, sub, search

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
      def linkUnicodeParse(link: str): #translates unicode codes in links
         return sub(r"%(.{2})",lambda m: chr(int(m.group(1),16)),link)

      def uule(city: str) -> str: #formats uule strings for use in locales
         secret_list = list(ascii_uppercase) + \
            list(ascii_lowercase) + list(digits) + ["-", "_"]

         secret = secret_list[len(city) % len(secret_list)]
         hashed = standard_b64encode(city.encode()).decode().strip("=")
         return f"w+CAIQICI{secret}{hashed}"
      #endregion
      #region embed creation functions
      def imageEmbed(image): #embed creation for image embeds
         try:
            resultEmbed = Embed(title=f'Search results for: {self.searchQuery[:233]}{"..." if len(self.searchQuery) > 233 else ""}')
            imgurl = linkUnicodeParse(findall("(?<=imgurl=).*(?=&imgrefurl)", image.parent.parent["href"])[0])
            if "encrypted" in imgurl:
                  imgurl = findall("(?<=imgurl=).*(?=&imgrefurl)", image.findAll("img")[1].parent.parent["href"])[0]
            # imgurl = findall("(?<=\=).*(?=&imgrefurl)", image["href"])[0]
            print(" image: " + imgurl)
            resultEmbed.set_image(url=imgurl)
            resultEmbed.url = url
         except: 
            resultEmbed.description = 'Image failed to load'
         finally: return resultEmbed

      def textEmbed(result): #embed creation for text embeds
         resultEmbed = Embed(title=f'Search results for: {self.searchQuery[:233]}{"..." if len(self.searchQuery) > 233 else ""}') 

         resultFind = result.findAll('div')
         divs = tuple(d for d in resultFind if not d.find('div'))
         lines = tuple(' '.join([string if string != 'View all' else '' for string in div.stripped_strings]) for div in divs)
         printstring = '\n'.join(lines)

         resultEmbed.description = sub("\n\n+", "\n\n", printstring)

         # tries to add a link to the embed
         findLink = result.findAll("a", href_="")
         link_list = tuple(a for a in findLink if not a.find("img")) 
         if len(link_list) != 0: 
            try:
               link = linkUnicodeParse(findall("(?<=url\?q=).*(?=&sa)", link_list[0]["href"])[0])
               resultEmbed.add_field(name="Relevant Link", value=link)
               print(" link: " + link)
            except:
               print("adding link failed")

         # tries to add an image to the embed
         image = result.find("img")
         try:
            imgurl = linkUnicodeParse(findall("(?<=imgurl=).*(?=&imgrefurl)", image.parent.parent["href"])[0])
            if "encrypted" in imgurl:
                  imgurl = findall("(?<=imgurl=).*(?=&imgrefurl)", image.findAll("img")[1].parent.parent["href"])[0]
            # imgurl = findall("(?<=\=).*(?=&imgrefurl)", image["href"])[0]
            print(" image: " + imgurl)
            resultEmbed.set_image(url=imgurl)
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

         uuleParse = uule(self.userSettings[self.ctx.author.id]['locale']) if self.userSettings[self.ctx.author.id]['locale'] is not None else 'w+CAIQICI5TW91bnRhaW4gVmlldyxTYW50YSBDbGFyYSBDb3VudHksQ2FsaWZvcm5pYSxVbml0ZWQgU3RhdGVz' 
         url = (''.join([
               "https://google.com/search?pws=0&q=", 
               self.searchQuery.replace(" ", "+"), f'{"+-stock+-pinterest" if hasFoundImage else ""}',
               f"&uule={uuleParse}&num=5{'&safe=active' if self.serverSettings[hex(self.ctx.guild.id)]['safesearch']and not self.ctx.channel.nsfw else ''}"
            ])
         )
         response = get(url)
         soup, index = BeautifulSoup(response.text, features="lxml"), 3

         if soup.find("div", {"id": "main"}) is not None:
            #region html processing
            wrongFirstResults = {"Did you mean: ", "Showing results for ", "Tip: ", "See results about", "Including results for ", "Related searches", "Top stories", 'People also ask', 'Next >'}

            Log.appendToLog(self.ctx, f"{self.ctx.command} results", url)
            googleSnippetResults = soup.find("div", {"id": "main"}).contents
            
            #Debug HTML output
            # with open('test.html', 'w', encoding='utf-8-sig') as file:
            #    file.write(soup.prettify())

            #end div filtering
            googleSnippetResults = [googleSnippetResults[resultNumber] for resultNumber in range(3, len(googleSnippetResults)-2)]
            
            #bad result filtering
            googleSnippetResults = {result for result in googleSnippetResults if not any(badResult in result.strings for badResult in wrongFirstResults) or result.strings==''}
            #endregion
            
            #checks if user searched specifically for images
            images = None
            if hasFoundImage:
               for results in googleSnippetResults:
                  if 'Images' in results.strings: 
                     images = results.findAll("img", recursive=True)
                     embeds = list(map(imageEmbed, images))
                     del embeds[-1]
                     break
                 
            if images is not None:
               embeds = list(map(imageEmbed, images))
            else:
               embeds = list(map(textEmbed, googleSnippetResults))
            
            print(self.ctx.author.name + " searched for: "+self.searchQuery[:233]) 
            for index, item in enumerate(embeds):
               item.set_footer(text=f'Page {index+1}/{len(embeds)}\nRequested by: {str(self.ctx.author)}') 
            
            doExit, curPage = False, 0

            if len(embeds) > 1:
               await gather(
                  self.message.add_reaction('🗑️'), 
                  self.message.add_reaction('◀️'), 
                  self.message.add_reaction('▶️')
               )

            else: 
               await self.message.add_reaction('🗑️')

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
               description = 'No results found')
         
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
            
            #queries Google Translate for translations
            query = ' '.join(query)
            translator = google_translator()
            result = translator.translate(query, lang_src=f'{srcLanguage if srcLanguage != None else "auto"}' , lang_tgt=destLanguage)
            
            #creates and sends embed
            if isinstance(result, list): result = '\n'.join(result)
            embed = Embed(title=f"{Languages.get(alpha2=srcLanguage).name if srcLanguage != None else translator.detect(query)[1].capitalize()} " +
               f"to {Languages.get(part1=destLanguage).name} Translation", 
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
            
            elif str(reaction.emoji) == '🔍':
               await self.message.clear_reactions()
               await self.message.edit(content=f'{LoadingMessage()} <a:loading:829119343580545074>', embed=None)
               await self.search()
               pass
         
         else: pass

      except TimeoutError: 
         raise

      except Exception as e:
         await self.message.delete()
         await ErrorHandler(self.bot, self.ctx, e, self.searchQuery)
      
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

         query = self.searchQuery.lower().split(' ')
         if len(query) > 1:
            #queries dictionary
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
            
            #while loop b/c multipage 
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
               elif str(reaction.emoji) == '🔍':
                  await self.message.clear_reactions()
                  await self.message.edit(content=f'{LoadingMessage()} <a:loading:829119343580545074>', embed=None)
                  await self.search()
                  break

         else: pass
         

      except TimeoutError: 
         raise

      except Exception as e:
         await self.message.delete()
         await ErrorHandler(self.bot, self.ctx, e, self.searchQuery)
      
      finally: return
