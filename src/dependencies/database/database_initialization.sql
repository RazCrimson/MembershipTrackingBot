/*
  DATABASE INITIALIZATION FILE FOR RAIDER

  Used to verify all constraints and reinforce them
  at the start up of the bot.

*/


/*  TABLE:  PERMISSIONS_NAMES    */
CREATE TABLE IF NOT EXISTS "USER_AUTH"
(
    "ENTRY_ID"  SERIAL primary key,
    "ITEM_ID"   bigint             not null,
    "LEVEL"     int      default 0 not null,
    "ROLE"      smallint default 0 not null,
    "SERVER_ID" bigint   default 0 not null,

    constraint "ENTRY_ID_UNIQUE"
        unique ("ENTRY_ID"),
    constraint "ITEM_ID_UNIQUE"
        unique ("ITEM_ID")
);

/*  TABLE:  PERMISSIONS_NAMES    */
CREATE TABLE IF NOT EXISTS "PERMISSIONS_NAMES"
(
    "ID"    SERIAL primary key,
    "NAME"  varchar(45) not null,
    "LEVEL" int         not null,

    constraint "LEVEL_UNIQUE"
        unique ("LEVEL")
);

/*  TABLE:  CHANNEL_AUTH    */
CREATE TABLE IF NOT EXISTS "CHANNEL_AUTH"
(
    "ENTRY_ID"        SERIAL primary key,
    "SERVER_ID"       bigint   not null,
    "CHANNEL_ID"      bigint   not null,
    "WHITELIST_LEVEL" smallint not null,

    constraint "CHANNEL_ID_UNIQUE"
        unique ("CHANNEL_ID")
);

/*  TABLE:  SUBSCRIPTION_LOG    */
create table "SUBSCRIPTION_LOG"
(
    "SERVER_ID"          bigint   not null,
    "USER_ID"            bigint   not null,
    "SUBSCRIPTION_LEVEL" smallint not null,
    "SUBSCRIBED_DATE"    date     not null,
    "AUTHOR_ID"          bigint   not null,
    constraint "SUBSCRIPTION_LOG_PK"
        primary key ("SERVER_ID", "USER_ID")
);

create table "SUBSCRIPTIONS"
(
    "SERVER_ID"          bigint      not null,
    "SUBSCRIPTION_LEVEL" smallint    not null,
    "SUBSCRIPTION_NAME"  varchar(30) not null,
    "ROLE_ID"            bigint      not null,
    "AUTHOR_ID"          bigint      not null,
    "DURATION"           smallint    not null,
    constraint "SUBSCRIPTIONS_PK"
        primary key ("SERVER_ID", "SUBSCRIPTION_LEVEL")
);
