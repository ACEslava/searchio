from src.utils import Log, ErrorHandler
from bs4 import BeautifulSoup
from google_trans_new import google_translator
from iso639 import languages as Languages
import asyncio, discord, urllib3, re, random

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
         result_number = 3
         foundImage = True
         google_snippet_result = soup.find("div", {"id": "main"})
   
         if google_snippet_result is not None:
            google_snippet_result = google_snippet_result.contents[result_number]
            breaklines = ["People also search for", "Episodes"]
            wrong_first_results = ["Did you mean: ", "Showing results for ", "Tip: ", "See results about", "Including results for ", "Related searches", "Top stories", 'People also ask' ]

            Log.appendToLog(ctx, "googlesearch results", url)

            
            if bool(re.search('image', searchQuery.lower())):
               while 'Images' not in google_snippet_result.strings:
                  result_number +=1
                  google_snippet_result = soup.find("div", {"id": "main"}).contents[result_number]

                  if result_number == len(soup.find("div", {"id": "main"}).contents)-1:
                     result_number = 3
                     foundImage = False
                     break
            else:
               while any(map(lambda wrong_first_result: wrong_first_result in google_snippet_result.strings, wrong_first_results)):
                  result_number+=1
                  google_snippet_result = soup.find("div", {"id": "main"}).contents[result_number]

            printstring = ""
            for div in [d for d in google_snippet_result.findAll('div') if not d.find('div')]:  # makes the text portion of the message by finding all strings in the snippet + formatting
               linestring = ""
               for string in div.stripped_strings:
                  linestring += string + " "
               if linestring == "View all ":  # clean this part up
                  linestring = ""

               if len(printstring+linestring+"\n") < 2000 and not any(map(lambda breakline: breakline in linestring, breaklines)):
                  printstring += linestring + "\n"
               else:
                  break

            embed = discord.Embed(title=f'Search results for: {searchQuery[:233]}{"..." if len(searchQuery) > 233 else ""}', 
               description = "{}".format('' if foundImage else 'No image found. Defaulting to first result:\n\n') + re.sub("\n\n+", "\n\n", printstring))
            print(ctx.author.name + " searched for: "+searchQuery[:233])
            image = google_snippet_result.find("img")  # can also be done for full html (soup) with about same result.
            
            # tries to add an image to the embed
            if image is not None: 
               try:
                  imgurl = linkUnicodeParse(re.findall("(?<=imgurl=).*(?=&imgrefurl)", image.parent.parent["href"])[0])
                  if "encrypted" in imgurl:
                        imgurl = re.findall("(?<=imgurl=).*(?=&imgrefurl)", google_snippet_result.findAll("img")[1].parent.parent["href"])[0]
                  # imgurl = re.findall("(?<=\=).*(?=&imgrefurl)", image["href"])[0]
                  print(" image: " + imgurl)
                  if "Images" in google_snippet_result.strings:
                        embed.set_image(url=imgurl)
                  else:
                        embed.set_thumbnail(url=imgurl)
               except:
                  foundImage = False

            # tries to add a link to the embed
            link_list = [a for a in google_snippet_result.findAll("a", href_="") if not a.find("img")] 
            if len(link_list) != 0: 
               try:
                  link = linkUnicodeParse(re.findall("(?<=url\?q=).*(?=&sa)", link_list[0]["href"])[0])
                  embed.add_field(name="Relevant Link", value=link)
                  print(" link: " + link)
               except:
                  print("adding link failed")
            embed.url = url
         
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
                
         except asyncio.TimeoutError as e: 
            pass

      except asyncio.CancelledError:
         pass
      
      except Exception as e:
         await message.delete()
         await ErrorHandler(bot, ctx, e, 'google', searchQuery)
      finally: return

class UserCancel(Exception):
   pass