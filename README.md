# Search.IO
A Discord bot search engine implemented in Python

## To use:

Install requirements with:
```
pip install -r requirements.txt
```

Obtain Discord bot credentials and place in a .env file in the same directory as main.py 

`DISCORD_TOKEN = [copy paste token]`

Run main.py


## To develop:

  All search modules are imported from ./src
  
  The modules each have the ability to send messages using discord.py.
     
   Example:

   https://github.com/ACEslava/wikipediasearch/blob/b6f1e54c185c3191a1496c817c27f5b59868dca9/src/wikipedia.py#L1-L17

  * Each module is required to be hooked up to the logging system
    * This can be done via:
    ```
    Log.appendToLog(ctx=discord.ext.commands.Context, command=str, args=str OR list)
    ```
  * The required instance attributes are:
  ```
    bot=discord.ext.commands.Bot
    ctx=discord.ext.commands.Context
    searchQuery=str
  ```
  * Optional instance attributes are:
  ```
    searchSettings=dict
    userSettings=dict
  ```

  * The serverSettings.yaml (and by extension searchSettings dict) are structured as follows:
  ```
    guildID=int:
        adminrole: roleID=int OR null,
        blacklist: [userID=int],
        sudoer: [userID=int],
        safesearch: bool,
        commandprefix: char,
        searchEngines:
          google: bool,
          image: bool,
          mal: bool,
          pornhub: bool,
          s: bool,
          scholar: bool
          wiki: bool
          wikilang: bool
          xkcd: bool
          youtube: bool
  ```
  * The userSettings.yaml (and by extension userSettings dict) are structured as follows:
  ```
    userID=int:
      downloadquota:
        dailyDownload: float
        lifetimeDownload: float
        updateTime: ISO-8601 datetime str
      locale: str OR null
      searchAlias: str OR null
  ```
