from discord.ext import commands
from config import Settings
import discord
import random
import datetime
from commands.utility.decorators import role_check, super_user_check
from databases.betting import BettingDB
from databases.main import MainDB
import pytz
import asyncio
from api.fandom import get_loldle_data

class PointCommands(commands.Cog):
    def __init__(self, main_db, betting_db, g_role, bot) -> None:
        self.main_db: MainDB = main_db
        self.betting_db = betting_db
        self.g_role = g_role
        self.bot : commands.bot.Bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        pass

    @commands.command()
    @super_user_check
    async def give(self, ctx, _, amount):
        async with ctx.typing():
            try:
                mentions = ctx.message.mentions
                if len(mentions) == 0 or len(mentions) > 1:
                    await ctx.send("Mention 1 person to grant points")
                    return
                self.main_db.increment_field(mentions[0].id, "points", int(amount))
                points_bytes = self.main_db.get_user_field(mentions[0].id, "points")
            except Exception as e:
                await ctx.send(e)
                return
            points = points_bytes.decode('utf-8')
            message = f'Total points: {points}'
            embed = discord.Embed(title=f"{'You have been given some points'}\n\n",
                                  description=f"{message}",
                                  color=0xFF0000)
            await ctx.send(embed=embed)

    @commands.command()
    @role_check
    async def daily(self, ctx):
        """ Get daily points (500)"""
        async with ctx.typing():
            try:
                amsterdam_tz = pytz.timezone('Europe/Amsterdam')
                today = datetime.datetime.now(amsterdam_tz).date()
                userid = str(ctx.author.id)
                last_claim = self.main_db.get_user_field(discord_id=userid, field="last_claim")
                if last_claim is None or last_claim.decode('utf-8') != str(today.strftime('%Y-%m-%d')):
                    status = "You claim some points"
                    self.main_db.set_user_field(userid, "last_claim", today.strftime('%Y-%m-%d'))
                    self.main_db.increment_field(userid, "points", 500)
                else:
                    status = "You already claimed your points for today"
                points_bytes = self.main_db.get_user_field(userid, "points")
            except Exception as e:
                await ctx.send(e)
                return
            points = points_bytes.decode('utf-8')
            message = f'Total points: {points}'
            embed = discord.Embed(title=f"{status}\n\n",
                                  description=f"{message}",
                                  color=0xFF0000)
            await ctx.send(embed=embed)

    def compare_dicts_and_create_embed(self, dict1, dict2):
        # Define the emojis
        cross_emoji = "❌"
        check_emoji = "✅"

        # Create a Discord embed
        embed = discord.Embed(title="Comparison Result", color=0x00ff00)

        # Compare the dictionaries
        for key in dict1:
            if key in dict2:
                if isinstance(dict1[key], list) and isinstance(dict2[key], list):
                    # Both values are lists, compare items
                    matching_items = [f"{check_emoji} {item}" for item in dict1[key] if item in dict2[key]]
                    non_matching_items = [f"{cross_emoji} {item}" for item in dict1[key] if item not in dict2[key]]
                    items_str = ', '.join(matching_items + non_matching_items)
                    embed.add_field(name=key, value=items_str, inline=False)
                elif dict1[key] == dict2[key]:
                    # Values match
                    embed.add_field(name=key, value=f"{check_emoji} {dict1[key]}", inline=False)
                else:
                    # Values don't match
                    embed.add_field(name=key, value=f"{cross_emoji} {dict1[key]} -> {dict2[key]}", inline=False)
            else:
                # Key doesn't exist in the second dictionary
                embed.add_field(name=key, value=f"{cross_emoji} {dict1[key]} -> Key not found", inline=False)

        # Check for any extra keys in the second dictionary
        for key in dict2:
            if key not in dict1:
                # Key doesn't exist in the first dictionary
                embed.add_field(name=key, value=f"{cross_emoji} Key not found -> {dict2[key]}", inline=False)

        return embed

    @commands.command()
    @role_check
    async def loldle(self, ctx, option="classic"):
        if option.lower() not in ["classic", "ability", "quote"]:
            await ctx.send("Invalid option, use .loldle <classic/ability/quote>")
            return
        async with ctx.typing():
            try:
                amsterdam_tz = pytz.timezone('Europe/Amsterdam')
                today = datetime.datetime.now(amsterdam_tz).date()
                userid = str(ctx.author.id)
                #TODO: REMOVE!!!!
                self.main_db.set_user_field(userid, "last_loldle", "2017-03-21")
                last_claim = self.main_db.get_user_field(discord_id=userid, field="last_loldle")
                await ctx.send(last_claim.decode('utf-8'))
                ##
                if last_claim is None or last_claim.decode('utf-8') != str(today.strftime('%Y-%m-%d')):
                    status = "Guess a champion and win 1000 points!"
                    winning_guess_info = await get_loldle_data()  
                    await ctx.send(winning_guess_info)
                    await ctx.send(status)
                    # start LODLE api call and wait for response
                    def check(m):
                        return m.author == ctx.author and m.channel == ctx.channel
                    try:
                        msg = await self.bot.wait_for('message', check=check, timeout=60.0)
                        champion_guess = (msg.content.replace(" ", "")).capitalize()
                        await ctx.send('Your guess: {}'.format(champion_guess))
                        try:
                            champion_guess_info = await get_loldle_data(champion_guess)
                            await ctx.send(champion_guess_info)
                            embed = self.compare_dicts_and_create_embed(champion_guess_info, winning_guess_info)
                            print(embed)
                            await ctx.send(embed)
                        except Exception as e:
                            await ctx.send(e)
                    except asyncio.TimeoutError:
                        await ctx.send('Sorry, you took too long to respond.')
                        return
                    # self.main_db.increment_field(userid, "points", 500)
                else:
                    status = "You already played a LOLDLE today"
                points_bytes = self.main_db.get_user_field(userid, "points")
            except Exception as e:
                await ctx.send(e)
                return
            # points = points_bytes.decode('utf-8')
            # self.main_db.set_user_field(userid, "last_loldle", today.strftime('%Y-%m-%d'))
            # message = f'Total points: {points}'
            # embed = discord.Embed(title=f"{status}\n\n",
            #                       description=f"{message}",
            #                       color=0xFF0000)
            await ctx.send(embed=embed)

    @commands.command()
    @role_check
    async def roll(self, ctx, *args):
        async with ctx.typing():
            userid = str(ctx.author.id)
            points_bytes = self.main_db.get_user_field(userid, "points")
            if points_bytes is None:
                await ctx.send("You have no points,  type .daily to get your points")
                return
            if len(args) == 0:
                await ctx.send("Amount has to be specified .roll <amount>")
                return
            number = args[0]
            points = points_bytes.decode('utf-8')
            try:
                number = int(number)
            except ValueError:
                await ctx.send("Specify a valid amount larger than 0")
                return
            if number <= 0:
                await ctx.send("Specify a valid amount larger than 0")
                return
            if number > int(points):
                await ctx.send(f"You do not have enough points for this, total points: {points}")
                return
            roll = random.choice(['Heads', 'Tails'])
            if roll != 'Heads':
                try:
                    self.main_db.decrement_field(userid, "points", number)
                except Exception as e:
                    print(e)
                new_points = self.main_db.get_user_field(userid, "points")
                status = "LOLOLOLOLO-LOSER"
            else:
                self.main_db.increment_field(userid, "points", number)
                new_points = self.main_db.get_user_field(userid, "points")
                status = "You won!"
            embed = discord.Embed(title=f"{status}\n\n",
                                  description=f"Original points: {points}\nNew points: {new_points.decode('utf-8')}",
                                  color=0xFF0000)
            await ctx.send(embed=embed)

    @commands.command()
    @role_check
    async def bet(self, ctx, *args):
        """
            Bet points with .bet <win/lose> <amount>
        """
        print("Bet command")
        if not self.betting_db.get_betting_state():
            await ctx.send("Betting not enabled")
            return
        if len(args) != 2 or args[0].lower() not in ["win", "lose"]:
            await ctx.send("Use .bet <win/lose> <amount>")
            return
        decision = "believers" if args[0] == "win" else "doubters"
        try:
            amount = int(args[1])
        except ValueError:
            await ctx.send("Specify a whole number larger than 0")
            return
        if amount <= 0:
            await ctx.send("Specify a whole number larger than 0")
            return
        try:
            state = self.betting_db.store_bet(str(ctx.author.id), str(ctx.author.display_name), decision, amount)
            if state:
                embed = discord.Embed(title=f"{str(ctx.author.display_name)} has bet {amount} points on {decision}",
                                      color=0xFF0000)
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"Bet amount > point")
        except Exception as e:
            print(e)

    @commands.command()
    @role_check
    async def points(self, ctx):
        """
            Returns amount of points of the current user
        """
        print("Points command")
        points = self.main_db.get_user_field(str(ctx.author.id), "points")
        if points is None:
            points = 0
        else:
            points = points.decode('utf8')
        embed = discord.Embed(title=f"You have {points} points", color=0xFF0000)
        try:
            await ctx.send(embed=embed)
            print("Message sent successfully.")
        except discord.Forbidden:
            print("I don't have permission to send messages to that channel.")
        except discord.HTTPException:
            print("Failed to send the message.")

    @commands.command()
    @role_check
    async def leaderboard(self, ctx, *args):
        """
            Returns point leaderboard with pagination support
        """
        try:
            print("Leaderboard command")
            leaderboard = None
            page_number = 1
            page_size = 10
            if len(args) == 0:
                leaderboard = self.main_db.get_all_users_sorted_by_field("points", True, 0, page_size)
            else:
                try:
                    page_number = int(args[0])
                    if page_number <= 0:
                        await ctx.send("Specify a whole number larger than 0")
                        return
                    start = (page_number - 1) * page_size
                    leaderboard = self.main_db.get_all_users_sorted_by_field("points", True, start, page_size)
                except ValueError:
                    await ctx.send("Specify a whole number larger than 0")
                    return
            leaderboard_text = ''
            for index, user in enumerate(leaderboard):
                leaderboard_text += f'\n{index + 1 + ((page_number * 10) - 10)}. <@{user[0]}> | {user[1]} points'
            description = f"99 percent of gamblers quit right before they hit it big! \n This is page {page_number}, to look at the next page use '.leaderboard {page_number+1}'"
            embed = discord.Embed(title="Biggest gambling addicts 🃏\n\n", description=f"{description}", color=0xFF0000)
            embed.add_field(name="Top 10 point havers on the server", value=leaderboard_text)
            await ctx.send(embed=embed)
        except Exception as ex:
            print(ex)
            await ctx.send(ex)

    @commands.command()
    @role_check
    async def transfer(self, ctx, *args):
        """
            Transfer your points to another player .transfer <@player> <points>
        """
        try:
            print(f"Transfer command: {args}")
            if len(args) != 2 or len(args[0]) < 3:
                await ctx.send("Use .transfer <@player> <points>")
                return
            discord_id = bytes(args[0][2:-1], 'utf-8')
            try:
                points = int(args[1])
            except ValueError:
                await ctx.send("Use .transfer <@player> <points>")
                return
            all_players = self.main_db.get_all_users()
            if discord_id not in all_players:
                await ctx.send("User is not registered")
                return
            if points <= 0:
                await ctx.send("Points must be larger than 0")
                return
            player_points = int(self.main_db.get_user_field(ctx.author.id, "points"))
            if player_points < points:
                await ctx.send("You do not have enough points")
                return
            self.main_db.decrement_field(ctx.author.id, "points", points)
            self.main_db.increment_field(discord_id, "points", points)
            embed = discord.Embed(title=f"Transferred {points} points", color=0xFF0000)
            await ctx.send(embed=embed)
        except Exception as e:
            print(e)
            await ctx.send(e)


async def setup(bot):
    settings = Settings()
    main_db = MainDB(settings.REDISURL)
    betting_db = BettingDB(settings.REDISURL)
    print("adding commands...")
    await bot.add_cog(PointCommands(main_db, betting_db, settings.GROLE, bot))
