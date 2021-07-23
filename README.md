# Search.IO
A Discord bot search engine implemented in Python

## To use:

Install requirements with:
```
pip install -r requirements.txt
```

Obtain Discord bot credentials and place in a .env file in the same directory as main.py 

`DISCORD_TOKEN = [YOUR TOKEN]`

Run main.py


## To develop:

  The bot uses a modularised system were individual search modules are hooked up to main.py.
  Each module consists of a class named [Search Engine]Search, with a constructor:
  ```
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
  ```
  and an async `__call__` method.
  
  Modules are self sufficient, handling all search engine API calls and results displays.
  Before the module is called, a `discord.Message` instance is created, containing a loading animation. All attempts should be made to contain search results to that one message instance.
  After the search concludes and there is an associated single URL with the search (i.e. a Google search page or website URL), the result is logged as follows:
  ```
  from src.utils import Log
  Log.append_to_log(self.ctx, f"{self.ctx.command} result", [url variable])
  ```
  
  All modules display their results in a `discord.Embed`, with the title linking to the relevant url and the discription displaying a brief summary of the results.
  Any additional information is displayed in embed fields.
  The footer always contains "Requested by: [Discord User and Discriminator]"
  The embeds are immediately followed by a 🗑️ reaction to allow the user to delete their search results.
  
  If any `Exception`s occur outside of the normal ones (`asyncio.TimeoutError`, etc), they are sent to a handler as follows:
  ```
  from src.utils import error_handler
  except Exception as e:
    await error_handler(self.bot, self.ctx, e, self.query)
    return
  ```
  
  Single-option modules, such as youtube.py, immediately display the results to the user, and are limited to a maximum of 10 results. Each result is contained within a separate embed and all results are precached as a list before results are sent to the user. The user is allowed to navigate between results using ◀️ and ▶️ reactions.
  Multi-option modules, such as wikipedia.py, display a multipage listing of all the results to the user to choose from. This listing is organised into a newline-separated string of `[index number]: [result name]`. Users reply to the result with their chosen index number and the listing is replaced with further information on the result of their choice.
  
  Both servers and users have settings that must be saved in between bot run instances. These settings are in the form of `dict`s and are saved to `.yaml` files whenever their are changed and every hour.
  
  The server `dict` is structured as follows:
  ```
    serverSettings = {
      guildID=str: { #hex code of  the guildID
        adminrole: roleID=int OR null,
        blacklist: [userID=int],
        sudoer: [userID=int],
        safesearch: bool,
        commandprefix: char,
        searchEngines: {
          #search engine modules: bool
        }
      }
    }
  ```
  The user `dict` is structured as follows:
  ```
    userSettings = {
      userID=int: {
        downloadquota: {
            dailyDownload: float
            lifetimeDownload: float
            updateTime: ISO-8601 datetime str
          }
        level: {
          rank: int
          xp: int
        }
        locale: str OR null
        searchAlias: str OR null
      }
    }
  ```
