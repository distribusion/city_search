import logging
import urllib.parse
from datetime import datetime, timedelta

import aiohttp
import pytz
from fastapi.applications import FastAPI

from city_search.legacy.elastic_utils import city_search, convert_xbus_to_utc
from city_search.legacy.serde import BookingData, Fare, RowCell, TripInfo
from city_search.legacy.utils import GlobalsAccess

fare_classes_url = "http://master-data.prod.internal.distribusion.com/api/v1/carriers/{carrier_cd}/fare_classes?locale=en"

logger = logging.getLogger()


def td_format(td_object):
    seconds = int(td_object.total_seconds())
    periods = [
        ("y", 60 * 60 * 24 * 365),
        ("m", 60 * 60 * 24 * 30),
        ("d", 60 * 60 * 24),
        ("h", 60 * 60),
        ("m", 60),
        ("s", 1),
    ]

    strings = []
    for period_name, period_seconds in periods:
        if seconds > period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            strings.append(f"{period_value}{period_name}")

    return ", ".join(strings)


def make_booking_url(
    carrier,
    departure_timezone: pytz.BaseTzInfo,
    arrival_timezone: pytz.BaseTzInfo,
    departure_station: str,
    departure_dttm: datetime,
    arrival_station: str,
    arrival_dttm: datetime,
    currency: str,
    locale: str,
    pax: int,
    retailer_partner_number: str,
):
    assert departure_dttm.tzinfo is not None
    assert arrival_dttm.tzinfo is not None

    endpoint = "http://www.bustickets-eurolines.ch/vx/bookings/new"
    parameters = {
        "action": "new",
        "arrival_station_code": arrival_station,
        "arrival_time": arrival_dttm.astimezone(arrival_timezone).strftime(
            "%Y-%m-%dT%H:%M"
        ),
        "controller": "bookings",
        "currency": currency,
        "departure_station_code": departure_station,
        "departure_time": departure_dttm.astimezone(departure_timezone).strftime(
            "%Y-%m-%dT%H:%M"
        ),
        "locale": locale,
        "marketing_carrier_code": carrier,
        "pax": str(pax),
        "retailer_partner_number": retailer_partner_number,
    }

    params_str = "&".join(
        [
            f"{urllib.parse.quote(k)}={urllib.parse.quote(v)}"
            for k, v in parameters.items()
        ]
    )
    return f"{endpoint}?{params_str}"


FARE_CLASS_CACHE = dict()


async def get_fare_classes(carrier_cd):
    if carrier_cd in FARE_CLASS_CACHE:
        return FARE_CLASS_CACHE[carrier_cd]
    timeout = aiohttp.ClientTimeout(total=1)
    async with aiohttp.ClientSession(raise_for_status=True, timeout=timeout) as session:
        async with session.get(fare_classes_url.format(carrier_cd=carrier_cd)) as resp:
            resp.raise_for_status()
            resp = await resp.json()
    FARE_CLASS_CACHE[carrier_cd] = resp
    return resp


async def get_fare_class_name(carrier_cd: str, fare_class_cd: str):
    fare_data = await get_fare_classes(carrier_cd)
    fare_names = {
        i["attributes"]["code"]: i["attributes"]["marketing_carrier_fare_class_name"]
        for i in fare_data["data"]
    }
    fare_class_name = fare_names.get(fare_class_cd)
    return fare_class_name


async def get_trips(
    app: FastAPI,
    departure_city,
    arrival_city,
    departure_date: datetime,
    booking_url_currency,
    booking_url_locale,
    booking_url_pax,
    booking_url_rpn,
    with_return,
):
    assert isinstance(departure_date, datetime)
    assert departure_date.tzinfo is not None
    assert departure_date.hour == 0
    assert departure_date.minute == 0
    assert departure_date.second == 0
    assert departure_date.microsecond == 0

    # Global indexes accessor
    gacc = GlobalsAccess(app.state.globals)

    d_from = departure_date
    d_to = departure_date + timedelta(days=1)

    if d_from < pytz.utc.localize(datetime.utcnow()):
        d_from = pytz.utc.localize(datetime.utcnow())

    trips = await city_search(
        gacc, departure_city, arrival_city, d_from, d_to, with_return=with_return
    )

    result = list()
    trip_i = 0
    for trip in trips:

        fares = list()
        for fare in trip["_source"]["fares"]:
            fares.append((fare["price"], fare["fare_class"]["uid"]))

        departure_station_uid = trip["_source"]["departure_station"]["uid"]
        arrival_station_uid = trip["_source"]["arrival_station"]["uid"]

        departure_tz = gacc.get_station_timezone_by_code(departure_station_uid)
        if departure_tz is None:
            logger.error(f"Could not find timezone for station {departure_station_uid}")
            continue
        arrival_tz = gacc.get_station_timezone_by_code(arrival_station_uid)
        if arrival_tz is None:
            logger.error(f"Could not find timezone for station {arrival_station_uid}")
            continue

        carrier_code = trip["_source"]["marketing_carrier"]["uid"]

        carrier_title = gacc.get_carrier_title_by_code(carrier_code)
        if carrier_title is None:
            logger.error(f"Unknown carrier: {carrier_code}")
            continue

        departure_millis = trip["_source"]["departure_time"]
        arrival_millis = trip["_source"]["arrival_time"]

        departure_dttm = convert_xbus_to_utc(departure_millis, departure_tz)
        arrival_dttm = convert_xbus_to_utc(arrival_millis, arrival_tz)

        duration = td_format(arrival_dttm - departure_dttm)

        departure_dttm_local = departure_dttm.astimezone(departure_tz)
        arrival_dttm_local = arrival_dttm.astimezone(arrival_tz)

        departure_time = departure_dttm_local.astimezone(departure_tz).strftime("%H:%M")
        arrival_time = arrival_dttm_local.astimezone(arrival_tz).strftime("%H:%M")

        departure_station_title = gacc.get_station_title_by_code(departure_station_uid)
        arrival_station_title = gacc.get_station_title_by_code(arrival_station_uid)

        if departure_station_title is None:
            logger.error(f"Unknown station code: {departure_station_uid}")
            continue

        if arrival_station_title is None:
            logger.error(f"Unknown station code: {arrival_station_uid}")
            continue

        additional_fares = list()
        for price, fare_class in fares:
            price = round(price / 100, 2)
            if round(price) == price:
                price_str = "{:.0f}".format(price)
            else:
                price_str = "{:.2f}".format(price)

            try:
                fare_class_name = await get_fare_class_name(carrier_code, fare_class)
            except Exception as ex:
                logger.error(
                    f"Error while trying to get fare class names: {ex.__class__.__name__}: {ex}"
                )
                continue

            additional_fares.append(
                Fare(
                    code=fare_class,
                    marketing_carrier_fare_class_name=fare_class_name,
                    price=price_str,
                    currency=trip["_source"]["currency"],
                )
            )

        for price, fare_class in fares:

            if fare_class != "FARE-1":
                continue

            price = round(price / 100, 2)
            if round(price) == price:
                price_str = "{:.0f}".format(price)
            else:
                price_str = "{:.2f}".format(price)

            price_str = trip["_source"]["currency"] + " " + price_str
            segments = trip["_source"]["segments"]

            if len(segments) == 1:
                transfers_caption = "Direct"
            elif len(segments) == 2:
                transfers_caption = "1 Transfer"
            else:
                transfers_caption = f"{len(segments) - 1} Transfers"

            trip_i += 1
            result.append(
                TripInfo(
                    id=trip_i - 1,
                    carrier=RowCell(
                        primary=carrier_title,
                        secondary="test",
                    ),
                    times=RowCell(
                        primary=f"{departure_time} - {arrival_time}",
                        secondary="",
                    ),
                    duration=RowCell(primary=duration, secondary=""),
                    stations=RowCell(
                        primary=f"{departure_station_title} - {arrival_station_title}",
                        secondary=f"{carrier_title}",
                    ),
                    segments=RowCell(primary=transfers_caption, secondary=""),
                    price=RowCell(primary=price_str, secondary=""),
                    fares=additional_fares,
                    booking_data=BookingData(
                        departure_station_uid=departure_station_uid,
                        departure_station_title=departure_station_title,
                        departure_station_city=gacc.get_city_title_by_code(
                            departure_city
                        )
                        or departure_city,
                        arrival_station_uid=arrival_station_uid,
                        arrival_station_title=arrival_station_title,
                        arrival_station_city=gacc.get_city_title_by_code(arrival_city)
                        or arrival_city,
                        departure_time_utc=departure_dttm,
                        departure_time_local=departure_dttm_local,
                        arrival_time_utc=arrival_dttm,
                        arrival_time_local=arrival_dttm_local,
                        carrier_code=carrier_code,
                        carrier_title=carrier_title,
                        duration_str=duration,
                        price=price,
                        currency=trip["_source"]["currency"],
                        n_segments=len(segments),
                        fare_class=fare_class,
                        booking_url=make_booking_url(
                            carrier_code,
                            departure_tz,
                            arrival_tz,
                            departure_station_uid,
                            departure_dttm_local,
                            arrival_station_uid,
                            arrival_dttm_local,
                            booking_url_currency or trip["_source"]["currency"],
                            booking_url_locale,
                            booking_url_pax,
                            booking_url_rpn,
                        ),
                    ),
                )
            )

    return result
