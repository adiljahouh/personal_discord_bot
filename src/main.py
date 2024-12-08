from discord_handler import discBot, add_cog
import asyncio
from config import Settings
import resource
from databases.loldle import loldleDB
def set_memory_limit(max_memory_mb):
    max_memory = max_memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (max_memory, max_memory))

async def main():
    settings = Settings()
    loldle_db = loldleDB(settings.REDISURL)
    await loldle_db.populate_if_needed()
    my_bot = discBot(token=settings.DISCORDTOKEN, channel_id=settings.CHANNELID, loldle_db=loldle_db)
    my_cogs = ["commands.league", "commands.animals", "commands.points", "commands.discord_moderation", "commands.loop"]
    for cog in my_cogs:
        await add_cog(my_bot, cog)
    await my_bot.start_bot()


if __name__ == "__main__":
    """Run the bot"""
    set_memory_limit(512)  # Limit to 512 MB
    asyncio.run(main())
