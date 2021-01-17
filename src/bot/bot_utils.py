import asyncio
from typing import Union, List

import discord
from discord.ext.commands import Context


def generate_embed(title: str, author: discord.Member, *, description: str, color: int) -> discord.Embed:
    return discord.Embed(
        title=title,
        color=color,
        description=description
    ).set_footer(text=author.display_name, icon_url=author.avatar_url)


async def fetch_guild_member(guild: discord.Guild, user: Union[discord.Member, int]):
    if not isinstance(user, discord.Member):
        try:
            return await guild.fetch_member(int(user))
        except (discord.Forbidden, discord.HTTPException):
            return
    return user


async def fetch_user(bot: discord.ext.commands.Bot, user: Union[discord.Member, int]):
    if not isinstance(user, discord.Member):
        try:
            return await bot.fetch_user(int(user))
        except (discord.Forbidden, discord.HTTPException):
            return
    return user


async def emoji_selection_detector(ctx: Context, emoji_list: List[Union[discord.Emoji, discord.PartialEmoji, str]],
                                   embed: discord.Embed = None, wait_for: int = 30, *, message_content: str = None,
                                   show_reject: bool = True) -> Union[None, discord.Emoji, discord.PartialEmoji, str]:
    def reaction_check(reaction, user_obj):
        if ctx.author.id == user_obj.id and reaction.emoji in [*emoji_list, '✕']:
            return True
        return False

    m = await ctx.send(content=message_content, embed=embed)
    await asyncio.gather(*[m.add_reaction(emote) for emote in emoji_list])
    if show_reject:
        await m.add_reaction('❌')
    try:
        reaction_used, user = await ctx.bot.wait_for('reaction_add', check=reaction_check, timeout=wait_for)
        await m.delete()
        if show_reject and reaction_used.emoji == '❌':
            return None
        if reaction_used.emoji in emoji_list:
            return reaction_used.emoji
    except asyncio.TimeoutError:
        return None
