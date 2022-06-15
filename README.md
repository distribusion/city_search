# City-search bacend

Service for integrating external APIs

## Quick Start

1) Create `.env` from `.env.example`. Fill in variables in file.
2) Run commands.
```shell
> docker-compose build
> docker-compose up -d
````

## Configuration
Configuration is done via environment variables:

- SECRET_KEY - A secret key for a particular. This is used to provide cryptographic signing,
and should be set to a unique, unpredictable value.
- API_ROOT_PATH - path prefix
- DB_URL - "postgres://<user>:<password>@<host>:<port>/<db_name>" (or sqlite://:memory: for in-memory use)

**(for postgresql in docker-compose)**
- POSTGRES_DB - postgres db
- POSTGRES_USER - postgres user
- POSTGRES_PASSWORD - postgres password
- POSTGRES_HOST - postgres host
- POSTGRES_PORT - postgres port


## Update models and make migrate

Background: aerich calculates differences between
current application models and last models
applied to the database based on the field `content`
in the `aerich` table
The problem: table `content` is populated with description of
current models each time you run upgrade. So, recreating
`content` based on migration history only is not possible.
You have to manually rollback git to specific version
to calculate diffs
Solutions:
1. (Easy way) Connect to production database and create migrations
   based on actual live latest database state.
   This will require you to know production (or sandbox)
   database credentials
2. (Hard way) Reproduce production database state locally and create migrations

For the ease of use, aerich commands were implemented in
cdm-api cli, so that they run in the same context as application itself

Also, aerich migration code has a bug that we've manually fixed in aerich_monkeypatch.py

**Before you begin**
You might need to genrate initial migration if it's your first migration
1. Run `DB_URL=... city-search db-migrate-initial`

**The easy way**
1. Run `DB_URL=... city-search db-migrate <migration name>`
   Where DB_URL value you can find in vault

**The hard way**
1. Rollback to current production version
2. Initialize empty database locally in the same database (postresql/mysql/etc..) as production database
3. Upgrade database locally to production version (this populates `content` field in `aerich` table used to calculate diffs)
4. Fetch latest version
5. Generate migrations
6. Done, enjoy your migrations script
