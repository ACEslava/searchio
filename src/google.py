from src.utils import Log, ErrorHandler
from bs4 import BeautifulSoup
from google_trans_new import google_translator
from iso639 import languages as Languages
import asyncio, discord, urllib3, re, random, wikipedia

class GoogleSearch:
   @staticmethod
   async def search(bot, ctx, serverSettings, message, searchQuery=None):
      try:
         def linkUnicodeParse(link: str):
            return re.sub(r"%(.{2})",lambda m: chr(int(m.group(1),16)),link)
         
         Log.appendToLog(ctx, "googlesearch", searchQuery)

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
               if type(result) == list:
                  result = '\n'.join(result)
               try:
                  embed = discord.Embed(title=f"{Languages.get(alpha2=srcLanguage).name if srcLanguage != None else translator.detect(query)[1].capitalize()} " +
                     f"to {Languages.get(part1=destLanguage).name} Translation", 
                     description = result + '\n\nReact with 🔍 to search Google')
                  embed.set_footer(text=f"Requested by {ctx.author}")
                  await message.edit(content=None, embed=embed)
                  await message.add_reaction('🗑️')
                  await message.add_reaction('🔍')
                  reaction, user = await bot.wait_for("reaction_add", check=lambda reaction, user: user == ctx.author and str(reaction.emoji) in ["🔍", "🗑️"], timeout=60)
                  if str(reaction.emoji) == '🗑️':
                     await message.delete()
                  
                  elif str(reaction.emoji) == '🔍':
                     await message.delete()
                     pass
               
               except asyncio.TimeoutError: 
                  pass
               except Exception as e:
                  await message.delete()
                  await ErrorHandler(bot, ctx, e, 'google', searchQuery)
               finally: return
                  
         await asyncio.sleep(random.uniform(0,2))
         http = urllib3.PoolManager()
         url = ("https://google.com/search?pws=0&q=" + 
            searchQuery.replace(" ", "+") + "+-stock+-pinterest&uule=w+CAIQICI5TW91bnRhaW4gVmlldyxTYW50YSBDbGFyYSBDb3VudHksQ2FsaWZvcm5pYSxVbml0ZWQgU3RhdGVz"
            f"&num=5{'&safe=active' if serverSettings[ctx.guild.id]['safesearch'] == True and ctx.channel.nsfw == False else ''}")
         response = http.request('GET', url)
         soup = BeautifulSoup(response.data, features="lxml")
         index = 3
         foundImage = False
         google_snippet_result = soup.find("div", {"id": "main"})
   
         if google_snippet_result is not None:
            google_snippet_result = google_snippet_result.contents[index]
            breaklines = ["People also search for", "Episodes"]
            wrongFirstResults = ["Did you mean: ", "Showing results for ", "Tip: ", "See results about", "Including results for ", "Related searches", "Top stories", 'People also ask', 'Next >']

            Log.appendToLog(ctx, "googlesearch results", url)
            googleSnippetResults = soup.find("div", {"id": "main"}).contents
            googleSnippetResults = [googleSnippetResults[resultNumber] for resultNumber in range(3, len(googleSnippetResults)-2)]
            
            #bad result filtering
            for index, result in enumerate(googleSnippetResults):
               for badResult in wrongFirstResults:
                  if badResult in result.strings or result.strings == '':
                     del googleSnippetResults[index]
           
            #checks if user searched specifically for images
            if bool(re.search('image', searchQuery.lower())):
               index = 0
               for results in googleSnippetResults:
                  if index == len(soup.find("div", {"id": "main"}).contents):
                        break
                  elif 'Images' in results.strings: 
                     images = results.findAll("img", recursive=True)
                     foundImage = True
                     break
                  else: index += 1
               
            embeds = []
            print(ctx.author.name + " searched for: "+searchQuery[:233])
            for result in googleSnippetResults:  
               
               #if the search term is images, all results will only be images
               if foundImage == True: 
                  for image in images:
                     try:
                        resultEmbed = discord.Embed(title=f'Search results for: {searchQuery[:233]}{"..." if len(searchQuery) > 233 else ""}')
                        imgurl = linkUnicodeParse(re.findall("(?<=imgurl=).*(?=&imgrefurl)", image.parent.parent["href"])[0])
                        if "encrypted" in imgurl:
                              imgurl = re.findall("(?<=imgurl=).*(?=&imgrefurl)", result.findAll("img")[1].parent.parent["href"])[0]
                        # imgurl = re.findall("(?<=\=).*(?=&imgrefurl)", image["href"])[0]
                        print(" image: " + imgurl)
                        resultEmbed.set_image(url=imgurl)
                        embeds.append(resultEmbed)
                     except: pass 
                  del embeds[-1]
                     
               else:  
                  resultEmbed = discord.Embed(title=f'Search results for: {searchQuery[:233]}{"..." if len(searchQuery) > 233 else ""}') 
                  printstring = ""
                  for div in [d for d in result.findAll('div') if not d.find('div')]:  # makes the text portion of the message by finding all strings in the snippet + formatting
                     linestring = ""
                     for string in div.stripped_strings:
                        linestring += string + " "
                     if linestring == "View all ":  # clean this part up
                        linestring = ""

                     if len(printstring+linestring+"\n") < 2000 and not any(map(lambda breakline: breakline in linestring, breaklines)):
                        printstring += linestring + "\n"
                     else:
                        break
                  
                  resultEmbed.description = re.sub("\n\n+", "\n\n", printstring)
                  image = result.find("img")  # can also be done for full html (soup) with about same result.
               
                  # tries to add an image to the embed
                  if image is not None: 
                     try:
                        imgurl = linkUnicodeParse(re.findall("(?<=imgurl=).*(?=&imgrefurl)", image.parent.parent["href"])[0])
                        if "encrypted" in imgurl:
                              imgurl = re.findall("(?<=imgurl=).*(?=&imgrefurl)", result.findAll("img")[1].parent.parent["href"])[0]
                        # imgurl = re.findall("(?<=\=).*(?=&imgrefurl)", image["href"])[0]
                        print(" image: " + imgurl)
                        if "Images" in result.strings:
                              resultEmbed.set_image(url=imgurl)
                        else:
                              resultEmbed.set_thumbnail(url=imgurl)
                     except: pass

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
                           resultEmbed.url = page.url

                        resultEmbed.add_field(name="Relevant Link", value=link)
                        print(" link: " + link)
                     except:
                        print("adding link failed")
                  resultEmbed.url = url
                  embeds.append(resultEmbed)
            
            doExit = False
            curPage = 0

            await message.add_reaction('◀️')
            await message.add_reaction('▶️')
            await message.add_reaction('🗑️')
            
            while doExit == False:
               try:
                  await message.edit(content=None, embed=embeds[curPage])
                  reaction, user = await bot.wait_for("reaction_add", check=lambda reaction, user: user == ctx.author and str(reaction.emoji) in ["◀️", "▶️", "🗑️"], timeout=60)
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
                  raise

         
         
         else:
            embed = discord.Embed(title=f'Search results for: {searchQuery[:233]}{"..." if len(searchQuery) > 233 else ""}',
               description = 'No results found')
         
            embed.set_footer(text=f"Requested by {ctx.author}")
            await message.edit(content=None, embed=embed)
            try:
               await message.add_reaction('🗑️')
               reaction, user = await bot.wait_for("reaction_add", check=lambda reaction, user: user == ctx.author and str(reaction.emoji) == "🗑️", timeout=60)
               if str(reaction.emoji) == '🗑️':
                  await message.delete()
                  
            except asyncio.TimeoutError: 
               raise
      
      except asyncio.TimeoutError: 
         raise

      except Exception as e:
         await message.delete()
         await ErrorHandler(bot, ctx, e, 'google', searchQuery)
      finally: return

class UserCancel(Exception):
   pass