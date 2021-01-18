from datetime import date, timedelta
from typing import Union, Tuple

import discord
from discord.ext import commands, tasks
from discord.ext.commands import Context

from bot.bot_utils import emoji_selection_detector, fetch_user, fetch_guild_member, generate_embed
from dependencies.database import Database, DatabaseDuplicateEntry
from . import bot_checks

NUMERIC_EMOTES = ['0⃣', '1⃣', '2⃣', '3⃣', '4⃣', '5⃣', '6⃣', '7⃣', '8⃣', '9⃣']


class Subscriptions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db: Database = bot.db
        self.membership_maintainer.add_exception_type(Exception)
        self.membership_maintainer.start()

    @commands.command()
    @bot_checks.is_whitelist()
    @bot_checks.check_permission_level(6)
    async def add_new_subscription(self, ctx: Context, sub_level: int, days: int, role: Union[discord.Role, int]):
        sub_level = int(sub_level)
        if not isinstance(role, discord.Role):
            try:
                role = await ctx.guild.fetch_role(int(role))
            except (discord.HTTPException, discord.Forbidden):
                await ctx.send("Invalid Role ID or Object!")
                return
        await self.db.add_subscription(ctx.guild.id, sub_level, role.name, role.id, days, ctx.author.id)
        await ctx.reply("Added a new subscription!")

    @commands.command()
    @bot_checks.is_whitelist()
    @bot_checks.check_permission_level(6)
    async def list_subscriptions(self, ctx: Context):
        subscriptions = await self.db.get_subscriptions(ctx.guild.id)
        embed = generate_embed('Subscriptions : ', ctx.author, description='', color=0)
        for _, sub_level, sub_name, role_id, duration, _ in subscriptions:
            name = f"{sub_name}"
            value = f"Duration : `{duration}` day(s) \n" \
                    f"Subscription Level : `{sub_level}` \n" \
                    f"Role ID : `{role_id}` "
            embed.add_field(name=name, value=value)
        await ctx.reply(embed=embed)

    @commands.command()
    @bot_checks.is_whitelist()
    @bot_checks.check_permission_level(6)
    async def delete_subscription(self, ctx: Context, sub_level: int):
        sub_level = int(sub_level)
        await self.db.delete_subscription(ctx.guild.id, int(sub_level))
        await ctx.reply(f"Deleted subscription of level : {sub_level}")

    @commands.command()
    @bot_checks.is_whitelist()
    @bot_checks.check_permission_level(6)
    async def give_subscription(self, ctx: Context, user_obj: Union[discord.Member, int]):
        user = await fetch_guild_member(ctx.guild, user_obj)
        if not user:
            return await ctx.reply("The Bot doesnt have permission to access the guild or can't find the user!")
        subscription = await self.db.get_user_subscription(ctx.guild.id, user.id)
        if subscription is not None:
            await ctx.reply(f'{user.display_name} already has a subscription. '
                            f'Please wait until the subscription ends to give another one.')
            return
        subscriptions = await self.db.get_subscriptions(ctx.guild.id)
        description = 'Please select the required subscription:'
        embed = generate_embed(f'Subscription selection for {user.display_name}', ctx.author, description=description,
                               color=0)
        emotes_list = []
        for _, sub_level, sub_name, role_id, duration, _ in subscriptions:
            emote = NUMERIC_EMOTES[sub_level]
            emotes_list.append(emote)
            name = f"{emote} **{sub_name}**"
            value = f"Duration : `{duration}` day(s) \n" \
                    f"Subscription Level : `{sub_level}` "
            embed.add_field(name=name, value=value)

        chosen_emote = await emoji_selection_detector(ctx, emotes_list, embed, 30)
        if chosen_emote is None:
            return
        index = NUMERIC_EMOTES.index(chosen_emote)
        subscription = next((sub for sub in subscriptions if sub[1] == index), None)
        _, sub_level, sub_name, role_id, duration, _ = subscription
        try:
            await self.db.add_user_subscription(ctx.guild.id, user.id, sub_level, date.today(), ctx.author.id)
            role = ctx.guild.get_role(role_id)
            await user.add_roles(role, reason=f'`{ctx.author.display_name}` - `{ctx.author.id}` assigned membership!')
            await ctx.reply(f'`{user.display_name}` got a `{sub_name}` Subscription.')
        except DatabaseDuplicateEntry:
            await ctx.reply(f'`{user.display_name}` already has a subscription. '
                            f'Please wait until the subscription ends to give another one.')

    async def __user_sub_data_generator(self, server_id: int, user_id: int, *, include_extra=False) -> \
            Union[Tuple, None]:
        subscription = await self.db.get_user_subscription(server_id, user_id)
        if subscription is not None:
            sub_name, _, sub_date, duration, author_id, role_id = subscription
            end_date = sub_date + timedelta(days=duration)
            remaining = {'days': 0}
            if end_date > date.today():
                remaining = end_date - date.today()
            name = f"{sub_name}"
            value = f"Subscribed Date : `{sub_date.strftime('%d/%m/%Y')}` \n" \
                    f"Duration Remaining : `{remaining.days}` day(s) \n"
            if include_extra:
                author = await self.bot.fetch_user(int(author_id))
                if author:
                    author_text = author.display_name
                else:
                    author_text = author_id
                value += f"Subscription End Date : `{end_date.strftime('%d/%m/%Y')}` \n" \
                         f"Assigner : `{author_text}` \n"
            return name, value
        return None

    @commands.command()
    @bot_checks.is_whitelist()
    @bot_checks.check_permission_level(6)
    async def show_subscription(self, ctx: Context, user_obj: Union[discord.Member, int]):
        user = await fetch_guild_member(ctx.guild, user_obj)
        if not user:
            return await ctx.reply("The Bot doesnt have permission to access the guild or can't find the user!")
        data = await self.__user_sub_data_generator(ctx.guild.id, user.id, include_extra=True)
        if data is not None:
            embed = generate_embed(f'{user.display_name}\'s Subscription ', ctx.author, description='', color=0)
            sub_name, value = data
            embed.add_field(name=sub_name, value=value)
            await ctx.reply(embed=embed)
        else:
            await ctx.reply(f"User: `{user.display_name}` doesnt have any subscriptions!")

    @commands.command()
    async def status(self, ctx: Context):
        data = await self.__user_sub_data_generator(ctx.guild.id, ctx.author.id)
        if data is not None:
            embed = generate_embed(f'{ctx.author.display_name}\'s Subscription ', ctx.author, description='', color=0)
            sub_name, value = data
            embed.add_field(name=sub_name, value=value)
            await ctx.reply(embed=embed)
        else:
            await ctx.reply("You dont have any active subscriptions!")

    @commands.command()
    @bot_checks.is_whitelist()
    @bot_checks.check_permission_level(6)
    async def remove_subscription(self, ctx: Context, user_obj: Union[discord.Member, int]):
        user = await fetch_user(self.bot, user_obj)
        if not user:
            return await ctx.reply("The Bot can't find the user to remove roles!")
        subscription = await self.db.get_user_subscription(ctx.guild.id, user.id)
        if subscription is not None:
            await self.db.delete_user_subscription(ctx.guild.id, user.id)
            await ctx.reply(f"Removed the subscription for User: `{user.display_name}`")
            role = ctx.guild.get_role(subscription[5])
            await user.remove_roles(role, reason=f'`{ctx.author.display_name}` - `{ctx.author.id}` removed membership!')
            await ctx.reply(f"Removed the role - `{role.name}` for User: `{user.display_name}`")
        else:
            await ctx.reply(f"`{user.display_name}` doesn't have an active subscriptions.")

    @tasks.loop(seconds=120)
    async def membership_maintainer(self):
        print('Running membership Maintainer....')
        log_channel = await self.bot.fetch_channel(798213155884105738)
        all_subscriptions = await self.db.get_all_user_subscription()
        guilds = {}
        for subscription in all_subscriptions:
            guild_id, user_id, _, _, sub_date, duration, _, role_id = subscription
            if guilds.get(guild_id) is None:
                guilds[guild_id] = await self.bot.fetch_guild(guild_id)
            if sub_date + timedelta(days=duration) <= date.today():
                print(f'{user_id} subscription has expired!')
                await self.db.delete_user_subscription(guild_id, user_id)
                user_text = user_id
                user = await fetch_guild_member(guilds[guild_id], user_id)
                if user:
                    user_text = user.display_name
                await log_channel.send(f"Removed the subscription for user: `{user_text}`")
                try:
                    role = guilds[guild_id].get_role(role_id)
                    await user.remove_roles(role, reason=f'Membership starting at {sub_date} expired now!')
                    await log_channel.send(f"Removed the role - `{role.name}` for User: `{user.display_name}`")
                except Exception as e:
                    await log_channel.send(f'Exception : {type(e)} - {e}')

    @membership_maintainer.before_loop
    async def before_membership_maintainer(self):
        print('Waiting until bot is ready...')
        await self.bot.wait_until_ready()


def setup(bot):
    cog = Subscriptions(bot)
    bot.add_cog(cog)
