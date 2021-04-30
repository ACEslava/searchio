from src.utils import Log, ErrorHandler
from src.loadingmessage import LoadingMessage
from bs4 import BeautifulSoup
from google_trans_new import google_translator
from iso639 import languages as Languages
from discord import Embed
import asyncio, re, wikipedia, string, base64, requests

class GoogleSearch:
   @staticmethod
   async def search(http, bot, ctx, serverSettings, userSettings, message, searchQuery=None):
      #region embed creation functions
      def imageEmbed(image): #embed creation for image embeds
         try:
            resultEmbed = Embed(title=f'Search results for: {searchQuery[:233]}{"..." if len(searchQuery) > 233 else ""}')
            imgurl = linkUnicodeParse(re.findall("(?<=imgurl=).*(?=&imgrefurl)", image.parent.parent["href"])[0])
            if "encrypted" in imgurl:
                  imgurl = re.findall("(?<=imgurl=).*(?=&imgrefurl)", image.findAll("img")[1].parent.parent["href"])[0]
            # imgurl = re.findall("(?<=\=).*(?=&imgrefurl)", image["href"])[0]
            print(" image: " + imgurl)
            resultEmbed.set_image(url=imgurl)
         except: 
            resultEmbed.description = 'Image failed to load'
         finally: return resultEmbed
            
      def textEmbed(result): #embed creation for text embeds
         resultEmbed = Embed(title=f'Search results for: {searchQuery[:233]}{"..." if len(searchQuery) > 233 else ""}') 
         
         divs = [d for d in result.findAll('div') if not d.find('div')]
         lines = [' '.join([string if string != 'View all' else '' for string in div.stripped_strings]) for div in divs]
         printstring = '\n'.join(lines)
         
         resultEmbed.description = re.sub("\n\n+", "\n\n", printstring)
      
         # tries to add a link to the embed
         link_list = [a for a in result.findAll("a", href_="") if not a.find("img")] 
         if len(link_list) != 0: 
            try:
               link = linkUnicodeParse(re.findall("(?<=url\?q=).*(?=&sa)", link_list[0]["href"])[0])
               
               if 'wikipedia' in link:
                  page = wikipedia.WikipediaPage(title=link.split('/')[-1])
                  summary = page.summary
                  summary = summary[:233] + f'{"..." if len(summary) > 233 else ""}'
                  resultEmbed.description = f'Wikipedia: {link.split("/")[-1]}\n {summary}' #outputs wikipedia article

               resultEmbed.add_field(name="Relevant Link", value=link)
               print(" link: " + link)
            except:
               print("adding link failed")

         # tries to add an image to the embed
         image = result.find("img")
         try:
            imgurl = linkUnicodeParse(re.findall("(?<=imgurl=).*(?=&imgrefurl)", image.parent.parent["href"])[0])
            if "encrypted" in imgurl:
                  imgurl = re.findall("(?<=imgurl=).*(?=&imgrefurl)", image.findAll("img")[1].parent.parent["href"])[0]
            # imgurl = re.findall("(?<=\=).*(?=&imgrefurl)", image["href"])[0]
            print(" image: " + imgurl)
            resultEmbed.set_image(url=imgurl)
         except: 
            pass
         
         return resultEmbed
      #endregion          
      
      #region utility functions
      def linkUnicodeParse(link: str): #translates unicode codes in links
         return re.sub(r"%(.{2})",lambda m: chr(int(m.group(1),16)),link)
      
      def uule_secret(length: int) -> str: #creates a uule secret for use in locales
         #Creates UULE secret
         secret_list = list(string.ascii_uppercase) + \
            list(string.ascii_lowercase) + list(string.digits) + ["-", "_"]
         return secret_list[length % len(secret_list)]

      def uule(city: str) -> str: #formats uule strings for use in locales
         #Creates UULE code
         secret = uule_secret(len(city))
         hashed = base64.standard_b64encode(city.encode()).decode().strip("=")
         return f"w+CAIQICI{secret}{hashed}"
      #endregion
      
      try:
         #region sub-commands
         if bool(re.search('translate', searchQuery.lower())):
            query = searchQuery.lower().split(' ')
            if len(query) > 1:
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
               
               query = ' '.join(query)
               translator = google_translator()
               result = translator.translate(query, lang_src=f'{srcLanguage if srcLanguage != None else "auto"}' , lang_tgt=destLanguage)
               
               if isinstance(result, list): result = '\n'.join(result)
               embed = Embed(title=f"{Languages.get(alpha2=srcLanguage).name if srcLanguage != None else translator.detect(query)[1].capitalize()} " +
                  f"to {Languages.get(part1=destLanguage).name} Translation", 
                  description = result + '\n\nReact with 🔍 to search Google')
               embed.set_footer(text=f"Requested by {ctx.author}")
               await message.edit(content=None, embed=embed)
               await message.add_reaction('🗑️')
               await message.add_reaction('🔍')
               reaction, user = await bot.wait_for("reaction_add", check=lambda reaction, user: user == ctx.author and str(reaction.emoji) in ["🔍", "🗑️"], timeout=60)
               
               if str(reaction.emoji) == '🗑️':
                  await message.delete()
                  return
               
               elif str(reaction.emoji) == '🔍':
                  await message.clear_reactions()
                  await message.edit(content=f'{LoadingMessage()} <a:loading:829119343580545074>', embed=None)
                  pass
            
            else: pass
            hasFoundImage = False 
         
         elif bool(re.search('image', searchQuery.lower())):
            hasFoundImage = True
         
         elif bool(re.search('define', searchQuery.lower())):
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
            query = searchQuery.lower().split(' ')
            if len(query) > 1:
               response = requests.get(f'https://api.dictionaryapi.dev/api/v2/entries/en_US/{" ".join(query[1:])}')
               response = response.json()[0]
               
               embeds = [item for sublist in [definitionEmbed(word, response) for word in response['meanings']] for item in sublist]
               for index, item in enumerate(embeds): 
                  item.set_footer(text=f'Page {index+1}/{len(embeds)}\nReact with 🔍 to search Google\nRequested by: {str(ctx.author)}')
               
               doExit, curPage = False, 0
               await message.add_reaction('🗑️')
               await message.add_reaction('🔍')
               if len(embeds) > 1:
                  await message.add_reaction('◀️')
                  await message.add_reaction('▶️')
               while 1:
                  try:
                     await message.edit(content=None, embed=embeds[curPage])
                     reaction, user = await bot.wait_for("reaction_add", check=lambda reaction, user: all([user == ctx.author, str(reaction.emoji) in ["◀️", "▶️", "🗑️",'🔍'], reaction.message == message]), timeout=60)
                     if str(reaction.emoji) == '🗑️':
                        await message.delete()
                        return
                     elif str(reaction.emoji) == '◀️':
                        curPage-=1
                     elif str(reaction.emoji) == '▶️':
                        curPage+=1
                     elif str(reaction.emoji) == '🔍':
                        await message.clear_reactions()
                        await message.edit(content=f'{LoadingMessage()} <a:loading:829119343580545074>', embed=None)
                        break

                     await message.remove_reaction(reaction, user)
                     if curPage < 0:
                        curPage = len(embeds)-1
                     elif curPage > len(embeds)-1:
                        curPage = 0
                  
                  except asyncio.TimeoutError: 
                     raise  
            else: pass
            
            hasFoundImage = False
         
         else: hasFoundImage = False        
         #endregion
         
         uuleParse = uule(userSettings[ctx.author.id]['locale']) if userSettings[ctx.author.id]['locale'] is not None else 'w+CAIQICI5TW91bnRhaW4gVmlldyxTYW50YSBDbGFyYSBDb3VudHksQ2FsaWZvcm5pYSxVbml0ZWQgU3RhdGVz' 
         url = (''.join(["https://google.com/search?pws=0&q=", 
            searchQuery.replace(" ", "+"), f'{"+-stock+-pinterest" if hasFoundImage else ""}',
            f"&uule={uuleParse}&num=5{'&safe=active' if serverSettings[ctx.guild.id]['safesearch'] == True and ctx.channel.nsfw == False else ''}"]))
         response = requests.get(url)
         soup = BeautifulSoup(response.content, features="lxml")
         index = 3
         google_snippet_result = soup.find("div", {"id": "main"})
   
         if google_snippet_result is not None:
            #region html processing
            google_snippet_result = google_snippet_result.contents[index]
            wrongFirstResults = ["Did you mean: ", "Showing results for ", "Tip: ", "See results about", "Including results for ", "Related searches", "Top stories", 'People also ask', 'Next >']

            Log.appendToLog(ctx, f"{ctx.command} results", url)
            googleSnippetResults = soup.find("div", {"id": "main"}).contents

            #Debug HTML
            # with open('test.html', 'w', encoding='utf-8-sig') as file:
            #    file.write(soup.prettify())

            #end div filtering
            googleSnippetResults = [googleSnippetResults[resultNumber] for resultNumber in range(3, len(googleSnippetResults)-2)]
            
            #bad result filtering
            googleSnippetResults = [result for result in googleSnippetResults if not any(badResult in result.strings for badResult in wrongFirstResults) or result.strings=='']
            #endregion

            #checks if user searched specifically for images
            embeds = list(map(textEmbed, googleSnippetResults))
            if hasFoundImage:
               for results in googleSnippetResults:
                  if 'Images' in results.strings: 
                     images = results.findAll("img", recursive=True)
                     embeds = list(map(imageEmbed, images))
                     del embeds[-1]
                     break
               
            print(ctx.author.name + " searched for: "+searchQuery[:233])

            for index, item in enumerate(embeds): 
               item.url = url
               item.set_footer(text=f'Page {index+1}/{len(embeds)}\nRequested by: {str(ctx.author)}')
            
            doExit, curPage = False, 0
            await message.add_reaction('🗑️')
            if len(embeds) > 1:
               await message.add_reaction('◀️')
               await message.add_reaction('▶️')
            
            while doExit == False:
               try:
                  await message.edit(content=None, embed=embeds[curPage])
                  reaction, user = await bot.wait_for("reaction_add", check=lambda reaction, user: all([user == ctx.author, str(reaction.emoji) in ["◀️", "▶️", "🗑️"], reaction.message == message]), timeout=60)
                  if str(reaction.emoji) == '🗑️':
                     await message.delete()
                     doExit = True
                  elif str(reaction.emoji) == '◀️':
                     curPage-=1
                  elif str(reaction.emoji) == '▶️':
                     curPage+=1

                  await message.remove_reaction(reaction, user)
                  if curPage < 0:
                     curPage = len(embeds)-1
                  elif curPage > len(embeds)-1:
                     curPage = 0
               
               except asyncio.TimeoutError:
                  await message.clear_reactions() 
                  raise

         else:
            embed = Embed(title=f'Search results for: {searchQuery[:233]}{"..." if len(searchQuery) > 233 else ""}',
               description = 'No results found')
         
            embed.set_footer(text=f"Requested by {ctx.author}")
            await message.edit(content=None, embed=embed)
            try:
               await message.add_reaction('🗑️')
               reaction, user = await bot.wait_for("reaction_add", check=lambda reaction, user: user == ctx.author and reaction.message == message and str(reaction.emoji) == "🗑️", timeout=60)
               if str(reaction.emoji) == '🗑️':
                  await message.delete()
                  
            except asyncio.TimeoutError: 
               raise
      
      except asyncio.TimeoutError: 
         raise

      except Exception as e:
         await message.delete()
         await ErrorHandler(bot, ctx, e, searchQuery)
      finally: return

class UserCancel(Exception):
   pass