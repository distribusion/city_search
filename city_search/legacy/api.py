import logging
import math
import traceback
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import aiohttp
import pytz
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.requests import Request
from fastapi.routing import APIRouter
from slugify import slugify
from tortoise import Tortoise
from tortoise.backends.asyncpg.client import AsyncpgDBClient
from tortoise.backends.sqlite.client import SqliteClient

from city_search import models  # Uses non-legacy API
from city_search.legacy import trips
from city_search.legacy.elastic_utils import city_operated_days
from city_search.legacy.serde import (
    CityGetResponse,
    CitySuggestionsResponse,
    PriceInfo,
    TripPricesResponse,
    TripsResponse,
)
from city_search.legacy.utils import (
    CarrierInfo,
    CityCode,
    Globals,
    GlobalsAccess,
    Item,
    ItemsIndex,
    StationCode,
    StationInfo,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_city_dict(app: FastAPI) -> Dict[str, Any]:
    city_dict = app.state.globals.city_dict
    if city_dict is not None:
        return city_dict
    raise HTTPException(503, "City dict not loaded yet")


async def _get_city_items() -> List[Item]:
    rv = list()
    async for city in models.City.all().prefetch_related(
        "country", "names", "ranks", "ranks__carrier"
    ):
        translations = dict()
        for translation in city.names:
            translations[translation.locale] = translation.name

        ranks = dict()
        for rank in city.ranks:
            if rank.enabled:
                ranks[rank.carrier.code] = rank.rank

        rank_sum = 0
        if len(ranks) != 0:
            rank_sum = sum(ranks.values())

        if "en" in translations:
            name = translations["en"]
            del translations["en"]
        else:
            name = city.code

        rv.append(
            Item(
                title=name,
                label=city.code,
                group=city.country.name,
                rank=rank_sum,
                type="city",
                translations=translations,
                timezone=city.timezone,
            )
        )
    return rv


async def update_city_dict() -> Dict[str, Item]:
    rv = dict()
    for item in await _get_city_items():
        rv[item.label] = item
    return rv


def get_cities_index(app: FastAPI, with_return: bool) -> ItemsIndex:
    if with_return:
        cities_index = app.state.globals.cities_index_wr
    else:
        cities_index = app.state.globals.cities_index_nr

    if cities_index is not None:
        return cities_index
    raise HTTPException(503, "Cities index not loaded yet")


def iter_ngrams(text: str):
    for word in slugify(text, separator=" ").split():
        word = slugify(word)
        word = "__" + word
        for ngram in zip(word, word[1:], word[2:]):
            yield "".join(tuple(map(lambda x: x or "_", ngram)))


async def update_cities_index(with_return: bool) -> ItemsIndex:
    cities = models.City.filter(ranks__enabled=True)
    if with_return:
        cities = models.City.filter(ranks__carrier__supports_return=True)

    ngrams = defaultdict(set)
    keys = list()
    keys_idx = dict()

    async for city in cities.all().prefetch_related("names", "country"):
        if city.code not in keys_idx:
            keys_idx[city.code] = len(keys)
            keys.append(city.code)

        city.country.name

        key_idx = keys_idx[city.code]

        # Add country name
        for ngram in iter_ngrams(city.country.name):
            ngrams[ngram].add(key_idx)

        # Add all of the translations
        for translation in city.names:
            for ngram in iter_ngrams(translation.name):
                ngrams[ngram].add(key_idx)

    return ItemsIndex(keys=keys, ngrams=ngrams)


def get_cities_top(app: FastAPI, with_return: bool) -> List[CityCode]:
    if with_return:
        cities_top = app.state.globals.cities_top_wr
    else:
        cities_top = app.state.globals.cities_top_nr

    if cities_top is not None:
        return cities_top

    raise HTTPException(503, "Top cities not loaded yet")


async def update_cities_top(with_return: bool) -> List[CityCode]:
    cities = models.City.filter(ranks__enabled=True)
    if with_return:
        cities = models.City.filter(ranks__carrier__supports_return=True)

    city_ranks = dict()

    async for city in cities.all().prefetch_related("ranks", "ranks__carrier"):
        rank_sum = 0
        for rank in city.ranks:
            if (with_return and not rank.carrier.supports_return) or not rank.enabled:
                continue
            rank_sum += rank.rank

        city_ranks[city.code] = rank_sum

    top_cities = sorted(city_ranks.items(), key=lambda x: -x[1])
    return [code for code, _ in top_cities[:20]]


def get_city_connections(app: FastAPI, with_return: bool) -> Dict[str, Any]:
    if with_return:
        city_connections = app.state.globals.city_connections_wr
    else:
        city_connections = app.state.globals.city_connections_nr

    if city_connections is not None:
        return city_connections
    raise HTTPException(503, "City connections not loaded yet")


async def update_city_connections(with_return: bool) -> Dict[CityCode, List[CityCode]]:
    conn = Tortoise.get_connection("default")

    if not isinstance(conn, (SqliteClient, AsyncpgDBClient)):
        raise NotImplementedError()

    if with_return:
        supports_return_query = "and carrier.supports_return = True"
    else:
        supports_return_query = ""

    sub_query = f"""
    select departure_city.code as departure_city_code,
           arrival_city.code as arrival_city_code,
           sum(departure_city_rank.rank)
            + sum(arrival_city_rank.rank)
            + coalesce(cityconnection.rank,0) as rank
    from cityconnection
        left join city as departure_city
            on (departure_city.id = departure_city_id)
        left join city as arrival_city
            on (arrival_city.id = arrival_city_id)
        left join cityrank as departure_city_rank
            on (departure_city_rank.city_id = departure_city_id
            and departure_city_rank.carrier_id = cityconnection.carrier_id)
        left join cityrank as arrival_city_rank
            on (arrival_city_rank.city_id = arrival_city_id
            and arrival_city_rank.carrier_id = cityconnection.carrier_id)
        left join carrier
            on (carrier.id = cityconnection.carrier_id)
    where departure_city_rank.enabled = True
      and arrival_city_rank.enabled = True
      {supports_return_query}
    group by 1, 2
    """

    row_number_query = f"""
    select departure_city_code,
           arrival_city_code,
           rank,
           row_number() over (partition by departure_city_code order by rank desc) as rn
    from ({sub_query})
    """

    data = await conn.execute_query_dict(
        f"""
        select departure_city_code,
               arrival_city_code,
               rank
        from ({row_number_query})
        where rn < 10
        """
    )

    city_connections = dict()

    for item in data:
        departure_city_code = item["departure_city_code"]
        arrival_city_code = item["arrival_city_code"]

        if departure_city_code not in city_connections:
            city_connections[departure_city_code] = list()

        city_connections[departure_city_code].append(arrival_city_code)

    return city_connections


MASTERDATA_URL = "http://master-data.prod.internal.distribusion.com/api/v1"


async def get_station_info() -> Tuple[
    Dict[CityCode, List[StationCode]], Dict[StationCode, StationInfo]
]:
    async with aiohttp.ClientSession(raise_for_status=True) as session:
        async with session.get(f"{MASTERDATA_URL}/stations") as resp:
            resp.raise_for_status()
            resp = await resp.json()

    city_stations = dict()
    station_info = dict()

    for station in resp["data"]:
        attrs = station["attributes"]
        rels = station["relationships"]
        code = attrs["code"]
        city_code = rels["city"]["data"]["id"]

        if city_code not in city_stations:
            city_stations[city_code] = list()

        city_stations[city_code].append(code)

        station_info[code] = StationInfo(
            name=attrs["name"], timezone=attrs["time_zone"]
        )

    return city_stations, station_info


async def get_carrier_info() -> Dict[str, CarrierInfo]:
    carrier_info = dict()
    async for carrier in models.Carrier.all():
        carrier_info[carrier.code] = CarrierInfo(
            name=carrier.name,
            supports_return_trips=carrier.supports_return,
            enabled=carrier.enabled,
        )
    return carrier_info


async def update_indexes(app: FastAPI) -> None:
    print_final_msg = False
    try:
        if getattr(app.state, "globals", None) is None:
            print_final_msg = True
            logger.warning("Initializing globals")
            app.state.globals = Globals(
                city_dict=None,
                cities_index_wr=None,
                cities_top_wr=None,
                city_connections_wr=None,
                cities_index_nr=None,
                cities_top_nr=None,
                city_connections_nr=None,
                city_stations=None,
                station_info=None,
                carrier_info=None,
            )

        # Used just for getting city info
        city_dict_new = await update_city_dict()

        # With-return indexes
        cities_index_new_wr = await update_cities_index(True)
        cities_top_new_wr = await update_cities_top(True)
        city_connections_new_wr = await update_city_connections(True)

        # Without-return indexes
        cities_index_new_nr = await update_cities_index(False)
        cities_top_new_nr = await update_cities_top(False)
        city_connections_new_nr = await update_city_connections(False)

        city_stations, station_info = await get_station_info()

        carrier_info = await get_carrier_info()

        # Update globals
        app.state.globals.city_dict = city_dict_new
        app.state.globals.cities_index_wr = cities_index_new_wr
        app.state.globals.cities_index_nr = cities_index_new_nr
        app.state.globals.cities_top_wr = cities_top_new_wr
        app.state.globals.cities_top_nr = cities_top_new_nr
        app.state.globals.city_connections_wr = city_connections_new_wr
        app.state.globals.city_connections_nr = city_connections_new_nr
        app.state.globals.city_stations = city_stations
        app.state.globals.station_info = station_info
        app.state.globals.carrier_info = carrier_info

        if print_final_msg:
            logger.warning(
                "Globals initialized. Carriers: %d, Cities: %d, Stations: %d",
                len(app.state.globals.carrier_info),
                len(app.state.globals.city_dict),
                len(app.state.globals.station_info),
            )

    except Exception:
        logger.error(traceback.format_exc())


@router.get("/city", tags=["cities"], response_model=CityGetResponse)
async def city_get(id: str) -> CityGetResponse:
    return CityGetResponse(
        title="",
        label="",
        group="",
        rank=0,
        type="",
    )


def search(index: ItemsIndex, query: str) -> List[CityCode]:
    ngrams = index.ngrams
    keys = index.keys
    found_candidates: List[Set[int]] = list()
    for ngram in iter_ngrams(query):
        try:
            found_candidates.append(ngrams[ngram])
        except KeyError:
            del found_candidates[:]
            break

    if found_candidates:
        print(found_candidates)
        rv = set.intersection(*found_candidates)
    else:
        rv = set()
    return sorted(list(map(lambda x: keys[x], rv)))


def ngram_city_search(
    city_dict: Dict[CityCode, Item], city_index: ItemsIndex, query: str
) -> List[Item]:
    city_codes = search(city_index, query)
    city_items = [city_dict[code] for code in city_codes]
    return sorted(city_items, key=lambda item: -item.rank)


@router.get(
    "/suggestions/cities", tags=["cities"], response_model=CitySuggestionsResponse
)
async def city_suggestions(
    request: Request,
    q: Optional[str] = None,
    c: Optional[str] = None,
    d: Optional[str] = None,
    user_timezone: Optional[str] = None,
    r: Optional[str] = None,  # type: ignore
) -> CitySuggestionsResponse:
    r: bool = r == "true"

    # Load indexes

    CITY_DICT = get_city_dict(request.app)
    CITIES_INDEX = get_cities_index(request.app, with_return=r)
    CITIES_TOP = get_cities_top(request.app, with_return=r)
    CITY_CONNECTIONS = get_city_connections(request.app, with_return=r)

    if q:
        found = ngram_city_search(CITY_DICT, CITIES_INDEX, q)
    else:
        found = [CITY_DICT[city_code] for city_code in CITIES_TOP]

    if c and d and not q:
        city_connections = CITY_CONNECTIONS.get(c)
        if city_connections:
            found_mapped = list()
            for city_id in city_connections:
                city = CITY_DICT.get(city_id)
                if city and city_id != c:
                    found_mapped.append(city)
            if found_mapped:
                found = found_mapped
    else:
        found = found[:20]

    return CitySuggestionsResponse(
        data=[
            CityGetResponse(
                title=i.title,
                label=i.label,
                group=i.group,
                rank=i.rank,
                type=i.type,
            )
            for i in found
        ]
    )


@router.get("/trips_prices", tags=["trips"], response_model=TripPricesResponse)
async def get_operated_days(
    request: Request, departure_city: str, arrival_city: str, with_return: Optional[str] = None  # type: ignore
) -> Dict[str, PriceInfo]:
    with_return: bool = with_return == "true"
    gacc = GlobalsAccess(request.app.state.globals)

    return await city_operated_days(
        gacc, departure_city, arrival_city, with_return=with_return
    )


@router.get("/trips", tags=["trips"], response_model=TripsResponse)
async def get_trips(
    request: Request,
    departure_city: str,
    arrival_city: str,
    date: str,
    direct: str,  # type: ignore
    bu_currency: Optional[str] = None,
    bu_locale: str = "en",
    bu_pax: int = 1,
    bu_rpn: str = "222222",
    page: int = 0,
    page_size: int = 1000,
    with_return: Optional[str] = None,  # type: ignore
):
    direct: bool = direct == "true"
    with_return: bool = with_return == "true"

    # Assume date in departure city timezone
    try:
        if request.app.state.globals.city_dict is None:
            raise HTTPException(503, f"City cache not initialized yet")
        departure_city_tz = pytz.timezone(
            request.app.state.globals.city_dict[departure_city].timezone
        )
    except KeyError:
        raise HTTPException(500, f"Could not find city: {departure_city}")

    schedule_data = await trips.get_trips(
        request.app,
        departure_city,
        arrival_city,
        departure_city_tz.localize(datetime.strptime(date, "%Y-%m-%d")),
        bu_currency,
        bu_locale,
        bu_pax,
        bu_rpn,
        with_return=with_return,
    )

    if direct:
        schedule_data = list(
            filter(lambda x: x.booking_data.n_segments == 1, schedule_data)
        )

    page = int(page)
    page_size = int(page_size)
    offset = page_size * page
    total = len(schedule_data)
    page_max = max(math.ceil(total / page_size) - 1, 0)

    return TripsResponse(
        data=schedule_data[offset : offset + page_size],
        total=total,
        page=page,
        page_max=page_max,
        page_size=page_size,
    )
