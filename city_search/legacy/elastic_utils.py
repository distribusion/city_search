import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Union

import aiohttp
import pytz
from fastapi.exceptions import HTTPException

from city_search.legacy.serde import PriceInfo
from city_search.legacy.utils import GlobalsAccess

ELASTIC_URL = "http://es.xbus.prod.internal.distribusion.com"
ELASTIC_SCROLL_SIZE = 1000
ELASTIC_MAX_SIZE = 10000

logger = logging.getLogger()


def convert_tz(dt, tz_from, tz_to):
    """Converts naive datetime from timezone 'tz_from' to timezone 'tz_to'"""
    if isinstance(tz_from, str):
        tz_from = pytz.timezone(tz_from)
    if isinstance(tz_to, str):
        tz_to = pytz.timezone(tz_to)

    assert dt.tzinfo is None

    rv = tz_from.localize(dt).astimezone(tz_to)
    return rv.replace(tzinfo=None)


def timestamp_to_dttm(timestamp_millis):
    """Converts timestamp_millis to naive datetime"""
    rv = datetime(1970, 1, 1) + timedelta(seconds=timestamp_millis / 1000)
    return rv


def dttm_to_timestamp_millis(dttm: datetime):
    assert dttm.tzinfo == pytz.utc

    return int((dttm - datetime(1970, 1, 1)).total_seconds() * 1000)


def convert_xbus_to_utc(
    timestamp_millis: int, station_timezone: Union[str, pytz.BaseTzInfo]
) -> datetime:
    """Converts distribusion's elasticsearch timestamp to utc timestamp"""
    step1 = timestamp_to_dttm(timestamp_millis)
    step2 = convert_tz(step1, "UTC", "europe/Berlin")
    step3 = convert_tz(step2, station_timezone, "UTC")
    result = pytz.utc.localize(step3)
    return result


def _trips_query(
    gacc: GlobalsAccess,
    departure_stations: List[str],
    arrival_stations: List[str],
    from_dttm: datetime,
    to_dttm: datetime,
    max_size=1000,
    with_return: bool = False,
):
    assert isinstance(from_dttm, datetime)
    assert isinstance(to_dttm, datetime)
    assert from_dttm.tzinfo is None
    assert to_dttm.tzinfo is None
    assert to_dttm >= from_dttm

    all_enabled_carriers = gacc.get_all_enabled_carriers(with_return)

    return {
        "size": max_size,
        "query": {
            "bool": {
                "must": [
                    {
                        "terms": {
                            "departure_station.uid": departure_stations,
                            "boost": 1.0,
                        }
                    },
                    {"terms": {"arrival_station.uid": arrival_stations, "boost": 1.0}},
                    {
                        "terms": {
                            "marketing_carrier.uid": all_enabled_carriers,
                            "boost": 1.0,
                        }
                    },
                    {"term": {"booked_out": {"value": False, "boost": 1.0}}},
                    {
                        "range": {
                            "departure_time": {
                                "from": from_dttm.strftime("%Y-%m-%d %H:%M:%S"),
                                "to": to_dttm.strftime("%Y-%m-%d %H:%M:%S"),
                                "include_lower": True,
                                "include_upper": False,
                                "boost": 1.0,
                            }
                        }
                    },
                ],
                "boost": 1.0,
            }
        },
        "_source": True,
    }


def _trips_dates_query(
    gacc: GlobalsAccess,
    departure_stations,
    arrival_stations,
    departure_date: datetime,
    with_return: bool,
):
    assert isinstance(departure_date, datetime)

    # Search in UTC timezone
    departure_date_utc = departure_date.astimezone(pytz.utc)
    departure_date_from_str = departure_date_utc.strftime("%Y-%m-%d %H:%M:%S")

    dates_list = list()
    current_date = departure_date_utc
    for i in range(30):  # Scan 30 days in advance
        next_date = current_date + timedelta(days=1)
        dates_list.append((current_date, next_date))
        current_date = next_date

    departure_date_to_str = current_date.strftime("%Y-%m-%d %H:%M:%S")

    ranges_query = list()
    for d_from, d_to in dates_list:
        ranges_query.append(
            {
                "from": d_from.strftime("%Y-%m-%dT%H:%M:%S"),
                "to": d_to.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )

    all_enabled_carriers = gacc.get_all_enabled_carriers(with_return)

    return {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {
                        "terms": {
                            "departure_station.uid": departure_stations,
                            "boost": 1.0,
                        }
                    },
                    {"terms": {"arrival_station.uid": arrival_stations, "boost": 1.0}},
                    {
                        "terms": {
                            "marketing_carrier.uid": all_enabled_carriers,
                            "boost": 1.0,
                        }
                    },
                    {"term": {"booked_out": {"value": False, "boost": 1.0}}},
                    {
                        "range": {
                            "departure_time": {
                                "from": departure_date_from_str,
                                "to": departure_date_to_str,
                                "include_lower": True,
                                "include_upper": False,
                                "boost": 1.0,
                            }
                        }
                    },
                ],
                "boost": 1.0,
            }
        },
        "aggs": {
            "range": {
                "date_range": {
                    "field": "departure_time",
                    "format": "yyyy-MM-dd'T'HH:mm:ss",
                    "ranges": ranges_query,
                },
                "aggs": {
                    "min_price": {
                        "terms": {
                            "field": "currency",
                            "size": 3,
                        },
                        "aggs": {
                            "min_price": {"min": {"field": "total_price"}},
                        },
                    }
                },
            }
        },
        "_source": True,
    }


async def _destination_city_query(
    gacc: GlobalsAccess, departure_stations, departure_date: datetime, p_id, p_num
):
    departure_date_utc = departure_date.astimezone(pytz.utc)
    departure_date_from_str = departure_date_utc.strftime("%Y-%m-%d %H:%M:%S")
    departure_date_to_str = (departure_date_utc + timedelta(days=1)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    all_enabled_carriers = gacc.get_all_enabled_carriers(False)

    return {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {
                        "terms": {
                            "departure_station.uid": departure_stations,
                            "boost": 1.0,
                        }
                    },
                    {
                        "terms": {
                            "marketing_carrier.uid": all_enabled_carriers,
                            "boost": 1.0,
                        }
                    },
                    {"term": {"booked_out": {"value": False, "boost": 1.0}}},
                    {
                        "range": {
                            "departure_time": {
                                "from": departure_date_from_str,
                                "to": departure_date_to_str,
                                "include_lower": True,
                                "include_upper": False,
                                "boost": 1.0,
                            }
                        }
                    },
                ],
                "boost": 1.0,
            }
        },
        "_source": False,
        "aggs": {
            "arrival_stations": {
                "terms": {
                    "field": "arrival_station.uid",
                    "include": {"partition": p_id, "num_partitions": p_num},
                    "size": 1000,
                }
            }
        },
    }


async def elastic_request(query):
    async with aiohttp.ClientSession(raise_for_status=True) as session:
        async with session.get(f"{ELASTIC_URL}/trips/_search", json=query) as resp:
            try:
                resp_json = await resp.json()
            except Exception:
                resp_json = None

            try:
                resp.raise_for_status()
            except Exception:
                logger.error("Query that raised an error: %s", query)
                if resp_json is not None:  # Log response if it exists
                    logger.error(resp_json)
                raise

    if resp_json is None:
        raise ValueError("resp_json is None!")

    return resp_json


async def elastic_scroll(query, scroll_size="1m"):
    global ELASTIC_URL
    global ELASTIC_SCROLL_SIZE
    global ELASTIC_MAX_SIZE

    async with aiohttp.ClientSession(raise_for_status=True) as session:
        async with session.get(
            f"{ELASTIC_URL}/trips/_search?scroll={scroll_size}", json=query
        ) as resp_raw:

            try:
                resp = await resp_raw.json()
            except Exception:
                resp = None

            try:
                resp_raw.raise_for_status()
            except Exception:
                if resp is not None:
                    logger.error(resp)
                raise

            if resp is None:
                raise ValueError("response is None!")

        hits_total = resp["hits"]["total"]["value"]
        scroll_id = resp["_scroll_id"]
        hits_fetched = len(resp["hits"]["hits"])

        yield resp

        if hits_fetched == 0:
            return

        while hits_fetched < hits_total:
            async with session.post(
                f"{ELASTIC_URL}/_search/scroll",
                json={"scroll": scroll_size, "scroll_id": scroll_id},
            ) as resp_next:
                resp_next = await resp_next.json()
            scroll_id = resp_next["_scroll_id"]
            hits_fetched += len(resp_next["hits"]["hits"])
            if len(resp_next["hits"]["hits"]) == 0 or hits_fetched >= ELASTIC_MAX_SIZE:
                break
            yield resp_next


async def _get_destination_cities_by_stations(
    gacc: GlobalsAccess, departure_stations: List[str], departure_date: datetime
):
    destination_cities = dict()
    query = await _destination_city_query(
        gacc, departure_stations, departure_date, 0, 100
    )
    response = await elastic_request(query)

    for bucket in response["aggregations"]["arrival_stations"]["buckets"]:
        station = bucket["key"]
        city = station[:5]
        if city not in destination_cities:
            destination_cities[city] = 0
        destination_cities[city] += bucket["doc_count"]
    return sorted(destination_cities.items(), key=lambda x: -x[1])


async def get_destination_cities(
    gacc: GlobalsAccess, departure_city: str, departure_date: datetime
):
    assert isinstance(departure_date, datetime)

    departure_stations = gacc.get_city_stations_by_code(departure_city)
    if departure_stations is None:
        raise HTTPException(404, f"City {departure_city} not found")

    return await _get_destination_cities_by_stations(
        gacc, departure_stations, departure_date
    )


def any_value(arr: Iterable[Any]) -> Any:
    try:
        return next(iter(arr))
    except StopIteration:
        raise ValueError("Array is empty")


async def city_operated_days(
    gacc: GlobalsAccess, departure_city: str, arrival_city: str, with_return: bool
) -> Dict[str, PriceInfo]:
    departure_stations = gacc.get_city_stations_by_code(departure_city)
    arrival_stations = gacc.get_city_stations_by_code(arrival_city)

    # Start date in departure city local timezone
    departure_city_tz = gacc.get_city_timezone_by_code(departure_city)
    if departure_city_tz is None:
        departure_city_tz = pytz.timezone("GMT-0")

    start_date_local = (
        datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(departure_city_tz)
    )

    # Set start date to the begging of the day
    start_date_local = start_date_local.replace(hour=0, minute=0, second=0)

    start_date_utc = start_date_local.astimezone(pytz.utc)

    query_dates = _trips_dates_query(
        gacc,
        departure_stations,
        arrival_stations,
        start_date_utc,
        with_return=with_return,
    )
    response_dates = await elastic_request(query_dates)

    # Convert response dates back to departure city local timezone
    currency_counts = dict()

    buckets = list()
    for bucket in response_dates["aggregations"]["range"]["buckets"]:
        bucket_from = datetime.strptime(
            bucket["from_as_string"], "%Y-%m-%dT%H:%M:%S"
        ).replace(tzinfo=pytz.utc)
        bucket_from_local = bucket_from.astimezone(departure_city_tz)

        min_prices = dict()
        for currency_bucket in bucket["min_price"]["buckets"]:
            currency = currency_bucket["key"]
            price = currency_bucket["min_price"]["value"]
            if price:
                min_prices[currency] = int(price / 100)
                currency_counts[currency] = currency_counts.get(currency, 0) + 1

        buckets.append(
            {
                "date": bucket_from_local.strftime("%Y-%m-%d"),
                "trips": bucket["doc_count"],
                "min_price": min_prices,
            }
        )

    # Choose primary currency to show
    if currency_counts:
        top_currency = sorted(list(currency_counts.items()), key=lambda x: -x[1])[0][0]
    else:
        top_currency = "EUR"

    for bucket in buckets:
        if bucket["min_price"]:
            if top_currency in bucket["min_price"]:
                price = bucket["min_price"][top_currency]
                bucket["min_price"] = PriceInfo(value=price, currency=top_currency)
            else:
                some_currency = any_value(bucket["min_price"].keys())
                price = bucket["min_price"][some_currency]
                bucket["min_price"] = PriceInfo(value=price, currency=some_currency)
        else:
            bucket["min_price"] = None

    day_prices = {i["date"]: i["min_price"] for i in buckets if i["min_price"]}

    return day_prices


async def city_search(
    gacc: GlobalsAccess,
    departure_city,
    arrival_city,
    from_dttm: datetime,
    to_dttm: datetime,
    with_return: bool,
):
    assert isinstance(from_dttm, datetime)
    assert isinstance(to_dttm, datetime)
    assert from_dttm.tzinfo is not None
    assert to_dttm.tzinfo is not None

    departure_stations = gacc.get_city_stations_by_code(departure_city)

    if departure_stations is None:
        raise HTTPException(404, f"City not found: {departure_city}")

    arrival_stations = gacc.get_city_stations_by_code(arrival_city)

    if arrival_stations is None:
        raise HTTPException(404, f"City not found: {arrival_city}")

    # Get raw to and from dates that will definitely enclose our time range
    raw_from = (from_dttm - timedelta(days=1)).astimezone(pytz.utc).replace(tzinfo=None)
    raw_to = (to_dttm + timedelta(days=1)).astimezone(pytz.utc).replace(tzinfo=None)

    query = _trips_query(
        gacc,
        departure_stations,
        arrival_stations,
        raw_from,
        raw_to,
        with_return=with_return,
    )

    response = await elastic_request(query)
    response = response["hits"]["hits"]

    # Filter out booked out
    response = filter(lambda x: not x["_source"]["booked_out"], response)

    def departure_dttm_within_range(connection):
        departure_millis = connection["_source"]["departure_time"]
        departure_station_uid = connection["_source"]["departure_station"]["uid"]
        # Timezones
        departure_tz = gacc.get_station_timezone_by_code(departure_station_uid)
        if departure_tz is None:
            logger.error(f"Could not find timezone for station {departure_station_uid}")
            return False

        departure_dttm = convert_xbus_to_utc(departure_millis, departure_tz)

        return from_dttm <= departure_dttm < to_dttm

    response = filter(departure_dttm_within_range, response)

    response = list(response)

    return response
