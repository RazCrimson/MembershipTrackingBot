import asyncio
from datetime import date

import asyncpg

from .database_exceptions import DatabaseDuplicateEntry, DatabaseInitError, DatabaseMissingArguments


class Database:
    def __init__(self, database_host: str, database_name: str, database_user: str, database_password,
                 database_port: int = 5432, min_conns: int = 3, max_conns: int = 10,
                 loop: asyncio.AbstractEventLoop = None):
        self.db_connections = {}
        self.db_pool: asyncpg.pool.Pool
        self.running = False
        self._database_data = {'dsn': f'postgres://{database_user}:{database_password}'
                                      f'@{database_host}:{database_port}/{database_name}', 'min_size': min_conns,
                               'max_size': max_conns}

        self.loop = loop
        if self.loop is None:
            self.loop = asyncio.get_event_loop()

        self.__async_init_task = self.loop.create_task(self.__pool_starter__())

    async def __pool_starter__(self):
        try:
            self.db_pool: asyncpg.pool.Pool = await asyncpg.create_pool(**self._database_data)
            self.running = True
            await self.__database_initializer__()
            return True
        except Exception as e:
            raise DatabaseInitError(f'Database Initialization Error: {type(e)}: {e}') from e

    async def __init_check__(self):
        if self.running:
            return
        await self.__async_init_task

    async def test(self):
        await self.__init_check__()
        data = await self.db_pool.fetch('SELECT version();')
        print(data)

    async def __database_initializer__(self):
        try:
            with open('./dependencies/database/database_initialization.sql') as file:
                query = file.read()
                await self.db_pool.execute(query)
        except FileNotFoundError:
            print('Please run the the launcher with the repository as the working directory.')

    async def permission_retriever(self, *ids, with_name=False):
        if len(ids) == 0:
            raise DatabaseMissingArguments('Missing arguments at the permission retriever')
        if with_name:
            query = f'SELECT MAX("LEVEL"), "NAME" FROM "USER_AUTH" INNER JOIN "PERMISSIONS_NAMES" USING ("LEVEL") ' \
                    f'WHERE "ITEM_ID" IN({", ".join(f"${x + 1}" for x in range(len(ids)))})'
        else:
            query = f'SELECT MAX("LEVEL") FROM "USER_AUTH" WHERE "ITEM_ID" IN ' \
                    f'({", ".join(f"${x + 1}" for x in range(len(ids)))}) '
        data = await self.db_pool.fetchrow(query, *ids)
        permission_level = data[0]
        if with_name:
            return permission_level, data[1]
        return permission_level

    async def auth_retriever(self, include_roles: bool = False):
        query = 'SELECT "ITEM_ID", "LEVEL", "NAME", "ROLE" FROM "USER_AUTH" ' \
                'INNER JOIN "PERMISSIONS_NAMES" USING ("LEVEL") '
        if include_roles is False:
            query = ' '.join((query, 'AND USER_AUTH.`ROLE` = 0'))

        data = await self.db_pool.fetch(query)
        return [{'id': item[0], 'level': item[1], 'nick': item[2], 'role': bool(item[3])} for item in data]

    async def auth_adder(self, target_id: int, level: int, role: bool = False, server_id: int = 0):
        query = 'INSERT INTO "USER_AUTH" ("ITEM_ID", "LEVEL", "ROLE", "SERVER_ID") VALUES ($1, $2, $3, $4)'
        try:
            await self.db_pool.execute(query, target_id, level, int(role), server_id)
        except asyncpg.IntegrityConstraintViolationError:
            raise DatabaseDuplicateEntry('USER_AUTH has duplicates!') from asyncpg.IntegrityConstraintViolationError

    async def auth_changer(self, target_id: int, level: int):
        query = 'UPDATE "USER_AUTH" set "LEVEL" = $1 where "ITEM_ID" = $2'
        await self.db_pool.execute(query, level, target_id)

    async def whitelist_check(self, server_id: int, channel_id: int) -> int:
        query = 'SELECT "WHITELIST_LEVEL" FROM "CHANNEL_AUTH" WHERE "SERVER_ID" = $1 AND "CHANNEL_ID" = $2'
        data = await self.db_pool.fetchval(query, server_id, channel_id)
        return data

    async def whitelist_add(self, server_id: int, channel_id: int, whitelist_level: int = 1):
        query = 'INSERT INTO "CHANNEL_AUTH" ("SERVER_ID", "CHANNEL_ID", "WHITELIST_LEVEL") VALUES ($1, $2, $3)'
        try:
            await self.db_pool.execute(query, server_id, channel_id, whitelist_level)
        except asyncpg.IntegrityConstraintViolationError:
            raise DatabaseDuplicateEntry('CHANNEL_AUTH has duplicates!') from asyncpg.IntegrityConstraintViolationError

    async def whitelist_remove(self, server_id: int, channel_id: int):
        query = 'DELETE FROM "CHANNEL_AUTH" WHERE "SERVER_ID" = $1 AND "CHANNEL_ID" = $2'
        await self.db_pool.execute(query, server_id, channel_id)

    async def add_user_subscription(self, server_id: int, user_id: int, sub_level: int, subscribed_time: date,
                                    author_id: int):
        query = 'INSERT INTO "SUBSCRIPTION_LOG" ("SERVER_ID", "USER_ID", "SUBSCRIPTION_LEVEL", "SUBSCRIBED_DATE", ' \
                '"AUTHOR_ID") VALUES ($1, $2, $3, $4, $5)'
        try:
            await self.db_pool.execute(query, server_id, user_id, sub_level, subscribed_time, author_id)
        except asyncpg.IntegrityConstraintViolationError:
            raise DatabaseDuplicateEntry('Duplicate Subscription!') from asyncpg.IntegrityConstraintViolationError

    async def get_user_subscription(self, server_id: int, user_id: int):
        query = 'SELECT "SUBSCRIPTION_NAME", "SUBSCRIPTION_LEVEL", "SUBSCRIBED_DATE", ' \
                '"DURATION", "SUBSCRIPTION_LOG"."AUTHOR_ID", "ROLE_ID" ' \
                'FROM "SUBSCRIPTION_LOG" INNER JOIN "SUBSCRIPTIONS" USING ("SERVER_ID", "SUBSCRIPTION_LEVEL") ' \
                'WHERE "SERVER_ID" = $1 AND "USER_ID" = $2'
        data = await self.db_pool.fetchrow(query, server_id, user_id)
        return data

    async def delete_user_subscription(self, server_id: int, user_id: int):
        query = 'DELETE FROM "SUBSCRIPTION_LOG" WHERE "SERVER_ID" = $1 AND "USER_ID" = $2'
        await self.db_pool.execute(query, server_id, user_id)

    async def get_all_user_subscription(self,):
        query = 'SELECT "SERVER_ID", "USER_ID","SUBSCRIPTION_NAME", "SUBSCRIPTION_LEVEL", "SUBSCRIBED_DATE", ' \
                '"DURATION", "SUBSCRIPTION_LOG"."AUTHOR_ID", "ROLE_ID"  ' \
                'FROM "SUBSCRIPTION_LOG" INNER JOIN "SUBSCRIPTIONS" USING ("SERVER_ID", "SUBSCRIPTION_LEVEL") '
        data = await self.db_pool.fetch(query)
        return data

    async def add_subscription(self, server_id: int, sub_level: int, subscription_name: str, role_id: int,
                               duration: int, author_id: int):
        query = 'INSERT INTO "SUBSCRIPTIONS" ("SERVER_ID", "SUBSCRIPTION_LEVEL", "SUBSCRIPTION_NAME", "ROLE_ID", ' \
                '"DURATION", "AUTHOR_ID") VALUES ($1, $2, $3, $4, $5, $6)'
        try:
            await self.db_pool.execute(query, server_id, sub_level, subscription_name, role_id, duration, author_id)
        except asyncpg.IntegrityConstraintViolationError:
            raise DatabaseDuplicateEntry('Duplicate Subscription!') from asyncpg.IntegrityConstraintViolationError

    async def get_subscriptions(self, server_id: int):
        query = 'SELECT "SERVER_ID", "SUBSCRIPTION_LEVEL", "SUBSCRIPTION_NAME", "ROLE_ID", "DURATION", "AUTHOR_ID" ' \
                'FROM "SUBSCRIPTIONS" WHERE "SERVER_ID" = $1'
        data = await self.db_pool.fetch(query, server_id)
        return data

    async def delete_subscription(self, server_id: int, sub_level: int):
        query = 'DELETE FROM "SUBSCRIPTIONS" WHERE "SERVER_ID" = $1 AND "SUBSCRIPTION_LEVEL" = $2'
        await self.db_pool.execute(query, server_id, sub_level)


