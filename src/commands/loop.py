from discord.ext import commands, tasks
import discord
from api.riot import riotAPI
from config import Settings
from commands.utility.team_image import imageCreator
from redis.exceptions import ConnectionError
import aiohttp
import asyncio
from databases.betting import BettingDB
from databases.main import MainDB
from databases.stalker import StalkingDB
from commands.utility.end_image import EndImage
from commands.utility.decorators import fix_highlighted_player
import tracemalloc
from api.ddragon import get_latest_ddragon
# Start tracing memory allocations

class loops(commands.Cog):
    def __init__(self, bot: commands.Bot, main_db: MainDB, betting_db: BettingDB, 
                 stalking_db: StalkingDB, riot_api: riotAPI, channel_id: int, ping_role_id: int, ddrag_version: str) -> None:
        self.bot = bot
        self.main_db = main_db
        self.betting_db = betting_db
        self.stalking_db = stalking_db
        self.riot_api = riot_api
        self.channel_id = channel_id
        self.ping_role_id = ping_role_id
        self.active_message_id = 0
        self.ddrag_version = ddrag_version 
        # Fix the db if there is a highlighted player
        fix_highlighted_player(self.main_db, self.betting_db, self.stalking_db)



    @tasks.loop(hours=24)
    async def refresh_ddrag(self):
        self.ddrag_version = await get_latest_ddragon()

    @commands.Cog.listener()
    async def on_ready(self):
        self.tracemalloc_started = False
        
        # Start tracing memory usage
        tracemalloc.start()
        self.tracemalloc_started = True
        print("Tracemalloc started in cog initialization.")
        self.activate_stalking.start()
        self.end_stalking.start()
        # await asyncio.sleep(900)
        # self.leaderboard.start()
        # await asyncio.sleep(1800)  # 1800
        # self.send_message.start()

    @tasks.loop(hours=24)
    async def send_message(self):
        print("Setting up exposing session...")
        channel_id: int = self.channel_id
        channel = self.bot.get_channel(channel_id)
        try:
            discord_ids: list[bytes] = self.main_db.get_all_users()
        except ConnectionError as e:
            print(e)
            await channel.send("No connection to DB")

        if len(discord_ids) > 0:
            discord_ids = [id.decode('utf-8') for id in discord_ids]
        else:
            await channel.send("No users registered")
            return
        embed = discord.Embed(title="⏰ ITS EXPOSING TIME ⏰\n\n",
                                description="BOTTOM G's WILL BE REPRIMANDED",
                                color=0xFF0000)
        inters = 0
        for index, discord_id in enumerate(discord_ids):
            riot_id = self.main_db.get_user_field(discord_id, "puuid")
            try:
                flame_text = await self.riot_api.get_bad_kda_by_puuid(riot_id.decode('utf-8'), 5, sleep_time=30)
            except aiohttp.ClientResponseError as e:
                print(e.message)
                await channel.send(f"Exposing command errored with: {e}")
                return

            if flame_text:
                inters += 1
                embed.add_field(name=f"SUSPECT #{inters}", value=f"<@{discord_id}>\n {flame_text}\n")
            else:
                print("no inters found for our exposing session")
                return

        if channel is not None:
            """
            query redis db for all users, check recents kdas and retrieve the cumulative worst.
            
            """
            try:
                await channel.send(embed=embed)
                print("Message sent successfully.")
            except discord.Forbidden:
                print("I don't have permission to send messages to that channel.")
            except discord.HTTPException:
                print("Failed to send the message.")

    @tasks.loop(hours=24)
    # # FIXME: Remove the concurrency here, its redundant
    async def leaderboard(self):
        """
            Keeps track of top 5 in each role of the leaderboard
        """
        channel_id: int = self.channel_id
        channel = self.bot.get_channel(channel_id)
        print("Retrieving Leaderboard...")
        try:
            discord_ids: list[bytes] = self.main_db.get_all_users()
        except ConnectionError as e:
            await channel.send("Could not connect to database.")
            return
        leaderboard_text = ''
        if len(discord_ids) > 0:
            discord_ids = [id.decode('utf-8') for id in discord_ids]
        else:
            await channel.send("No users are registered.")
        tasks = []
        delay = 1
        for discord_id in discord_ids:
            puuid = self.main_db.get_user_field(discord_id, "puuid")
            tasks.append(self.riot_api.get_highest_damage_taken_by_puuid(puuid=puuid.decode('utf-8'), count=5,
                                                                            sleep_time=delay, discord_id=discord_id))
            delay += 20
        try:
            result = await asyncio.gather(*tasks)
        except aiohttp.ClientResponseError as e:
            print(e)
            # await channel.send(f"")
        top_5 = sorted(result, key=lambda x: x['taken'], reverse=True)[:5]
        for index, top_g in enumerate(top_5):
            leaderboard_text += f'\n{index + 1}. <@{top_g["disc_id"]}> | {top_g["taken"]} on **{top_g["champion"]}**'
        description = f"Type .register to be able to participate"
        embed = discord.Embed(title="💪🏽TOPPEST G's💪🏽\n\n", description=f"{description}", color=0xFF0000)
        embed.add_field(name="Top Damage Taken Past 5 Games", value=leaderboard_text)
        await channel.send(embed=embed)

    @tasks.loop(minutes=2.0)
    async def activate_stalking(self):
        channel_id: int = self.channel_id
        channel = self.bot.get_channel(channel_id)
        try:
            # Check if a user is currently getting stalked
            if self.stalking_db.get_active_user() is not None:      
                return
            victims = self.stalking_db.get_all_users()
            print(f"Stalking victims of length: {len(victims)}")
            found = False
            active = False
            data = None
            victim = ""
            for pos_victim in victims:
                try:
                    # Small 1 second delay to not spam the requests
                    print(f"Checking if {pos_victim} is in game")
                    user, tag = pos_victim.split('#')
                    await asyncio.sleep(1)
                    active, data, game_length, game_type = await self.riot_api.get_active_game_status(user, tag, self.ddrag_version)
                    if active:
                        print(f"{pos_victim} is in game! Processing..")
                except aiohttp.ClientResponseError as e:
                    continue
                # If game was already highlighted, dont show it again and look for another active game
                # or if game is too far gone or isnt ranked dont track
                if game_length > 600 or game_type != 420:
                    print(f"Continuing, gametype {game_type} or gamelength {game_length} incorrect")
                    continue
                if active and self.stalking_db.current_game != data[0]:
                    victim = pos_victim
                    found = True
                    break
            if not found:
                print("No active user was found")
                return
            message = None
            embed = None
            async with channel.typing():
                ## TODO: man really use a better datas structure here
                embed = discord.Embed(title=f":eyes::eyes:  {victim.upper()} IS IN GAME :eyes::eyes:\n"
                                            "YOU HAVE 10 MINUTES TO PREDICT!!!\n\n",
                                      description="HE WILL SURELY WIN, RIGHT?",
                                      color=0xFF0000)
                champions = [[player[1] for player in team] for team in data[1]]
                players = [[player[0] for player in team] for team in data[1]]
                try:
                    image_creator: imageCreator = imageCreator(champions, players, data[2])
                    img = await image_creator.get_team_image()
                except aiohttp.ClientResponseError as e:
                    print("Failed to get images for image creator with exception: ", e)
                    return
                picture = discord.File(fp=img, filename="team.png")
                embed.set_image(url="attachment://team.png")

                if channel is not None:
                    try:
                        if data[2] != "Custom":
                            self.stalking_db.custom = False
                            message = await channel.send(f"<@&{self.ping_role_id}>", file=picture, embed=embed)
                            self.betting_db.enable_betting()
                        else:
                            self.stalking_db.custom = True
                            message = await channel.send(file=picture, embed=embed)
                        print("Message sent successfully.")
                    except Exception as e:
                        print(e)
                        return
            self.stalking_db.current_game = data[0]
            if data[2] == "Custom":
                return
            # Only when there is no custom game we lock the highlighted player
            # Otherwise, we just show the game screen and continue with our lives
            self.stalking_db.change_status(victim, True)
            self.active_message_id = message.id
            await asyncio.sleep(self.betting_db.betting_time)
            # Send betting is no longer available
            try:
                embed_bet = discord.Embed(title="Betting is no longer enabled",
                                      color=0xFF0000)
                await channel.send(embed=embed_bet)
            except Exception as e:
                print(f"Betting no longer enabled message failed: {e}")
            async with channel.typing():
                all_bets = self.betting_db.get_all_bets()
                for decision in all_bets.keys():
                    text = ""
                    for user in all_bets[decision]:
                        text += f"{user['name']} **{user['amount']}**\n"
                    embed.add_field(name=f"**{decision.upper()}**", value=text, inline=True)
                    if decision == "believers":
                        embed.add_field(name='\u200b', value='\u200b')
                try:
                    # embed.set_footer(text="Made by Matthijs (Aftershock)")
                    await message.edit(embed=embed)
                    print("Starting message updated.")
                except Exception as e:
                    print(f"Failed to update message: {e}")
        # Send the error in Discord
        except Exception as e:
            try:
                await channel.send(f"Activate stalking error: {e}")
                print(f"Activate stalking error: {e}")
            except Exception as e:
                print(f"Activate stalking error: {e}")
        finally:
            # Take a memory snapshot
            pass
            # snapshot = tracemalloc.take_snapshot()
            # top_stats = snapshot.statistics("lineno")
            # print("[Top 10 Memory Stats]")
            # for stat in top_stats[:10]:
            #     print(stat)
                
                
    @tasks.loop(minutes=2.0)
    async def end_stalking(self):
        print("End stalking")
        channel_id: int = self.channel_id
        channel = self.bot.get_channel(channel_id)
        try:
            victim = self.stalking_db.get_active_user()
            ##
            # victim = "1738#EUW" ##TODO:
            print(f"Active victim: {victim}")
            if victim is None:
  
                return
            
            match_id = f'EUW1_{self.stalking_db.current_game}'
            # match_id = "EUW1_7223658854" ##TODO:
            try:
                match_data = await self.riot_api.get_full_match_details_by_matchID(match_id)
            except aiohttp.ClientResponseError:
                print("Game is still in progress")
                return
            try:
                endIm = EndImage(match_data, victim)
                end_image = await endIm.get_team_image()
                end_result = endIm.get_game_result()
                picture = discord.File(fp=end_image, filename="team.png")
            except Exception as e:
                print(f"error in image: {e}")  
                return
            self.stalking_db.change_status(victim, False)
            self.betting_db.disable_betting()
            if end_result:
                description = "**WINNER WINNER CHICKEN DINNER 👑**\n"
                winners = "believers"
            else:
                description = "**BRO HAD NO IMPACT 🔥🔥**\n"
                winners = "doubters"

            message: discord.Message = await channel.fetch_message(self.active_message_id) #TODO
            embed = discord.Embed(title=f"{victim.upper()}'S GAME RESULT IS IN :eyes::eyes:\n\n",
                                  description=description,
                                  color=0xFF0000)
            embed.set_image(url="attachment://team.png")
            all_bets = self.betting_db.get_all_bets()
            for decision in all_bets.keys():
                text = ""
                decide = "won" if decision == winners else "lost"
                for user in all_bets[decision]:
                    if decision == winners:
                        self.main_db.increment_field(user['discord_id'], "points", 2*int(user['amount']))
                    if decide == "won":
                        text += f"{user['name']} has {decide} {2*int(user['amount'])} points\n"
                    else:
                        text += f"{user['name']} has {decide} {user['amount']} points\n"
                embed.add_field(name=f"**{decision.upper()}**", value=text, inline=True)
                if decision == "believers":
                    embed.add_field(name='\u200b', value='\u200b')
            if channel is not None:
                try:
                    self.betting_db.remove_all_bets()
                    await channel.send(embed=embed, reference=message, file=picture) 
                    print("Message sent successfully.")
                except discord.Forbidden:
                    print("I don't have permission to send messages to that channel.")
                except discord.HTTPException:
                    print("Failed to send the message.")
        # Send the error in Discord
        except Exception as e:
            try:
                await channel.send(f"End stalking error: {e}")
                print(f"End stalking error: {e}")
            except Exception as e:
                print(f"End stalking error: {e}")
        finally:
            # Take a memory snapshot
            pass
            # snapshot = tracemalloc.take_snapshot()
            # top_stats = snapshot.statistics("lineno")
            # print("[Top 10 Memory Stats]")
            # for stat in top_stats[:10]:
            #     print(stat)

async def setup(bot: commands.Bot):
    settings = Settings()
    main_db = MainDB(settings.REDISURL)
    betting_db = BettingDB(settings.REDISURL)
    stalking_db = StalkingDB(settings.REDISURL)
    riot: riotAPI = riotAPI(settings.RIOTTOKEN)
    ddrag_version = await get_latest_ddragon()
    print("adding loops..")
    await bot.add_cog(loops(bot, main_db, betting_db, stalking_db, riot, settings.LIVEGAMECHANNELID, settings.PINGROLE, ddrag_version=ddrag_version))
