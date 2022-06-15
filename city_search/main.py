"""
Server entrypoint with FastAPI app defined
"""

import logging
import os
import traceback
from typing import Any, Dict, List

import aiohttp
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi_utils.tasks import repeat_every
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware
from tortoise.contrib.fastapi import register_tortoise

from city_search import bigquery, models, serde
from city_search.legacy.api import MASTERDATA_URL
from city_search.legacy.api import router as legacy_api
from city_search.legacy.api import update_indexes
from city_search.settings import TORTOISE_ORM, settings

logger = logging.getLogger(__name__)

app = FastAPI(root_path=os.environ.get("API_ROOT_PATH", "/"))


@app.on_event("startup")
@repeat_every(seconds=10 * 60)  # 10 minutes
async def remove_expired_tokens_task() -> None:
    await update_indexes(app)


# Register DB
register_tortoise(
    app,
    config=TORTOISE_ORM,
    generate_schemas=settings.debug,  # Do not generate schemas by default in non-debug mode!
    add_exception_handlers=True,
)

# Add middleware
if settings.secret_key == "test_secret":
    logger.warning(
        "Please, set secret key as random key on server startup (must be same for all workers)"
    )
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health", include_in_schema=False)  # type: ignore
async def health() -> str:
    """Checks health of application, uncluding database and all systems"""

    if getattr(app.state, "globals", None) is None:
        raise HTTPException(503, "Cache not loaded yet")

    for attribute_name in app.state.globals.__class__.__dict__.keys():

        if attribute_name.startswith("_"):
            continue

        attribute_val = getattr(app.state.globals, attribute_name, None)

        if attribute_val is None:
            raise HTTPException(503, f"{attribute_name} not loaded yet")

    return "OK"


@app.get("/", include_in_schema=False)  # type: ignore
async def index() -> Dict[str, str]:
    return {
        "message": (
            f"Hello World."
            f" Test environment variable is: {os.getenv('TEST_ENV_VAR')}"
        )
    }


@app.get(
    "/carrier",
    tags=["data"],
    response_model=List[serde.Carrier],
    summary="List carriers",
)
async def carrier_list():
    rv = list()
    for carrier in await models.Carrier.all():
        rv.append(
            serde.Carrier(
                code=carrier.code,
                name=carrier.name,
                enabled=carrier.enabled,
                supports_return=carrier.supports_return,
            )
        )
    return rv


@app.get(
    "/carrier/{code}",
    tags=["data"],
    response_model=serde.Carrier,
    summary="Get carrier info by code",
)
async def carrier_get(code: str):
    carrier = await models.Carrier.get(code=code)

    return serde.Carrier(
        code=carrier.code,
        name=carrier.name,
        enabled=carrier.enabled,
        supports_return=carrier.supports_return,
    )


async def get_carrier_name(code: str):
    # Get carrier name
    async with aiohttp.ClientSession(raise_for_status=True) as session:
        async with session.get(
            f"{MASTERDATA_URL}/carriers/by_dis_marketing_carrier_codes"
            + f"?marketing_carrier_codes[]={code}&locale=en"
        ) as resp:
            resp.raise_for_status()
            resp = await resp.json()
    return resp["data"][0]["attributes"]["trade_name"]


@app.post(
    "/carrier/{code}",
    tags=["data"],
    response_model=serde.CarrierControlsResponse,
    summary="Update carrier info (also updates ranks and connections)",
)
async def carrier_post(code: str, carrier_controls: serde.CarrierControls):
    try:
        updates = set()
        errors = set()

        carrier_name = await get_carrier_name(code)
        mdl_carrier, created = await models.Carrier.update_or_create(
            code=code,
            defaults=dict(
                name=carrier_name,
                supports_return=carrier_controls.supports_return,
                enabled=carrier_controls.enabled,
            ),
        )

        # Get all countries
        countries = {country.code: country async for country in models.Country.all()}

        cities = dict()
        n_cities_created = 0
        async for city in bigquery.get_cities(code):

            try:
                mdl_country = countries[city.country_code]
            except KeyError:
                errors.add(f"Country {city.country_code} not found")
                continue

            mdl_city, created = await models.City.get_or_create(
                code=city.code,
                defaults=dict(timezone=city.timezone, country=mdl_country),
            )

            cities[mdl_city.code] = mdl_city

            if created:
                n_cities_created += 1
                updates.add(f"Created city {city.code} {city.name}")
                # City name
                await models.CityName.get_or_create(
                    city=mdl_city, locale="en", defaults=dict(name=city.name)
                )

        # Update ranks

        n_ranks_updated = 0

        async for city_rank in bigquery.get_city_ranks(code):

            try:
                mdl_city = cities[city_rank.code]
            except KeyError:
                errors.add(f"City {city_rank.code} not found")
                continue

            await models.CityRank.update_or_create(
                city=mdl_city,
                carrier=mdl_carrier,
                defaults=dict(enabled=True, rank=city_rank.rank),
            )

            n_ranks_updated += 1

        n_connections_updated = 0
        async for connection in bigquery.get_connections(code):
            try:
                mdl_departure_city = cities[connection.dep_city_cd]
                errors.add(f"City {connection.dep_city_cd} not found")
            except KeyError:
                continue

            try:
                mdl_arrival_city = cities[connection.arr_city_cd]
            except KeyError:
                errors.add(f"City {connection.arr_city_cd} not found")
                continue

            await models.CityConnection.update_or_create(
                carrier=mdl_carrier,
                departure_city=mdl_departure_city,
                arrival_city=mdl_arrival_city,
                defaults=dict(
                    rank=connection.rank,
                ),
            )

            n_connections_updated += 1

        return serde.CarrierControlsResponse(
            success=True,
            n_cities_created=n_cities_created,
            n_ranks_updated=n_ranks_updated,
            n_connections_updated=n_connections_updated,
            errors=sorted(errors),
            updates=sorted(updates),
        )
    except Exception:
        logger.error(traceback.format_exc())
        return HTTPException(500, traceback.format_exc())


@app.get(
    "/country",
    tags=["data"],
    response_model=List[serde.Country],
    summary="List countries",
)
async def country_list():
    rv = list()
    for country in await models.Country.all():
        rv.append(serde.Country(name=country.name))
    return rv


@app.get(
    "/city",
    tags=["data"],
    response_model=List[serde.City],
    summary="List cities",
)
async def city_list():
    rv = list()
    for city in await models.City.all().prefetch_related(
        "country", "names", "ranks", "ranks__carrier"
    ):
        translations = dict()
        for translation in city.names:
            translations[translation.locale] = translation.name

        ranks = dict()
        for rank in city.ranks:
            if rank.enabled:
                ranks[rank.carrier.code] = rank.rank

        if len(translations) == 0:
            name = None
        elif "en" in translations:
            name = translations["en"]
        else:
            name = translations[min(translations.keys())]

        rv.append(
            serde.City(
                code=city.code,
                country=city.country.name,
                name=name,
                translations=translations,
                ranks=ranks,
            )
        )
    return rv


# We need to specify custom openapi to add app.root_path to servers
def custom_openapi() -> Any:
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="City-Search backend service",
        version="0.1.0",
        description="Provides city-search capabilities with elasticsearch",
        routes=app.routes,
    )
    openapi_schema["servers"] = [{"url": app.root_path}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi  # noqa

app.include_router(legacy_api)
