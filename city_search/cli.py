"""
Aerich entrypoint, import configuration and init tortoise
"""

import asyncio
import logging
import os
import sys
from typing import Any, List

import typer

logger = logging.getLogger(__name__)

app = typer.Typer(name="city_search")
state = {"loglevel": logging.INFO}


def configure_logging(level: int) -> None:
    """
    Basic logging setup
    """
    logging.basicConfig(
        stream=sys.stdout,
        format="%(asctime)-15s [%(levelname)s] %(message)s",
        level=logging.WARNING,
    )
    logging.getLogger("city_search").setLevel(level)

    if level <= logging.DEBUG:
        logging.getLogger("tortoise").setLevel(
            level
        )  # When set to debug, will log all db queries


def run_aerich_command(command: str, **kwargs: Any) -> None:
    """
    Initialize db, run aerich command, terminate connections
    """

    from aerich import Command  # pylint: disable=[C0415]
    from tortoise import Tortoise  # pylint: disable=[C0415]

    from city_search.settings import TORTOISE_ORM  # pylint: disable=[C0415]
    from city_search.settings import settings  # pylint: disable=[C0415]

    # Get migrations location based on database connection type
    # To make sure we do not apply migrations generated on sqlite to postgresql database
    db_engine = settings.db_url.split("://", maxsplit=1)[0]

    aerich_app = Command(
        tortoise_config=TORTOISE_ORM,
        app="models",
        location=os.path.join(settings.db_migrations_location, db_engine),
    )

    configure_logging(state["loglevel"])

    async def _run_async() -> None:
        try:
            await aerich_app.init()
            if command == "downgrade":
                await aerich_app.downgrade(
                    version=kwargs["version"], delete=kwargs["delete"]
                )
            elif command == "heads":
                await aerich_app.heads()
            elif command == "history":
                _print_table(await aerich_app.history())
            elif command == "init":
                await aerich_app.init()
            elif command == "init-db":
                await aerich_app.init_db(safe=kwargs["safe"])
            elif command == "migrate":
                from city_search.aerich_monkeypatch import (  # pylint: disable=[C0415]
                    Migrate,
                )

                Migrate.app = aerich_app.app
                await Migrate.init(
                    aerich_app.tortoise_config, aerich_app.app, aerich_app.location
                )
                await Migrate.migrate(name=kwargs["name"])
            elif command == "upgrade":
                await aerich_app.upgrade()
            else:
                raise NotImplementedError()
        finally:
            await Tortoise.close_connections()

    asyncio.run(_run_async())


@app.command()
def db_example_data() -> None:
    from aerich import Command  # pylint: disable=[C0415]
    from tortoise import Tortoise  # pylint: disable=[C0415]

    from city_search.mock_db_init import create_test_data
    from city_search.settings import TORTOISE_ORM  # pylint: disable=[C0415]
    from city_search.settings import settings  # pylint: disable=[C0415]

    db_engine = settings.db_url.split("://", maxsplit=1)[0]

    aerich_app = Command(
        tortoise_config=TORTOISE_ORM,
        app="models",
        location=os.path.join(settings.db_migrations_location, db_engine),
    )

    async def _run_async():

        try:
            logger.warning("Launching aerich app init")
            logger.warning(settings.db_url)

            await aerich_app.init()

            await create_test_data()

        finally:
            await Tortoise.close_connections()

    asyncio.run(_run_async())


@app.command()
def db_downgrade(version: int, delete: bool) -> None:
    """
    Downgrade to specified version.
    """
    configure_logging(state["loglevel"])
    run_aerich_command("downgrade", version=version, delete=delete)


@app.command()
def db_heads() -> None:
    """
    Show current available heads in migrate location.
    """
    configure_logging(state["loglevel"])
    run_aerich_command("heads")


@app.command()
def db_history() -> None:
    """
    List all migrate items.
    """
    configure_logging(state["loglevel"])
    run_aerich_command("history")


@app.command()
def db_init(safe: bool = True) -> None:
    """
    Generate schema and generate app migrate location.
    """
    configure_logging(state["loglevel"])
    run_aerich_command("init", safe=safe)


@app.command()
def db_migrate_initial(safe: bool = True) -> None:
    """
    Generate initial migration
    """
    configure_logging(state["loglevel"])
    run_aerich_command("init-db", safe=safe)


@app.command()
def db_migrate(name: str) -> None:
    """
    Generate migrate changes file.
    """
    configure_logging(state["loglevel"])
    run_aerich_command("migrate", name=name)


@app.command()
def db_upgrade() -> None:
    """
    Upgrade to latest version.
    """
    configure_logging(state["loglevel"])
    run_aerich_command("upgrade")


def _print_table(table: List[List[str]]) -> None:
    if len(table) == 0:
        return

    if not isinstance(table[0], list):
        table = [[row] for row in table]  # type: ignore

    longest_cols = [
        (max(len(str(row[i])) for row in table) + 3) for i in range(len(table[0]))
    ]
    row_format = "".join(
        ["{:>" + str(longest_col) + "}" for longest_col in longest_cols]
    )
    for row in table:
        print(row_format.format(*row))


@app.command()
def debug() -> None:
    """
    Run application in debug mode

    For production use run:

    gunicorn city_search.main:app
    """
    import uvicorn  # pylint: disable=[C0415]

    from city_search.main import app  # pylint: disable=[C0415, W0621]

    uvicorn.run(app)  # type: ignore


@app.callback()
def main(verbose: bool = False) -> None:
    """
    Run/manage city-search server
    """
    if verbose:
        state["loglevel"] = logging.INFO


if __name__ == "__main__":
    app()
