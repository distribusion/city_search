"""
Async bigquery utils
"""

import asyncio
import concurrent.futures
from base64 import b64decode
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict

import janus
import simplejson
from google.cloud import bigquery
from google.oauth2.service_account import Credentials

from city_search.settings import settings


def get_bigquery_client_from_env() -> bigquery.Client:
    """
    Create bigquery client based on environment variable credentials
    """

    account_key_str = settings.gs_account_key

    if account_key_str is None:
        raise ValueError("Google cloud service account key not specified")

    return bigquery.Client(
        project=settings.bq_project,
        location=settings.bq_location,
        credentials=Credentials.from_service_account_info(
            info=simplejson.loads(
                b64decode(account_key_str.encode("ascii")).decode("ascii")
            )
        ),
    )


def bq_query(query: str, output_queue: janus.SyncQueue, poison_pill: Any):
    """
    Execute bigquery synchronously and ensure that poison_pill is pushed into the queue
    """
    try:
        client = get_bigquery_client_from_env()

        result = client.query(query).result()
        columns = [field.name for field in result.schema]
        for item in result:
            output_queue.put(dict(zip(columns, item)))

    finally:
        output_queue.put(poison_pill)


async def async_bq_query(query: str) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Executes bigquery non-blocking way in a separate thread
    """

    loop = asyncio.get_running_loop()

    # Create queue and poison
    poison_pill = object()
    result_queue = janus.Queue(maxsize=1000)

    # Run query non-blocking in separate thread
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = asyncio.ensure_future(
            loop.run_in_executor(
                pool, bq_query, query, result_queue.sync_q, poison_pill
            )
        )

        # Read for results and yield them asyncronously untill we encounter poison
        while True:
            poision_or_data = await result_queue.async_q.get()
            if poision_or_data is poison_pill:
                break
            yield poision_or_data

        # Get result (or raise exception)
        await future


@dataclass
class City:
    code: str
    country_code: str
    name: str
    timezone: str


CITY_QUERY = """
select city.city_cd                 as code,
       city.country_cd              as country_code,
       city.name                    as name,
       any_value(station.time_zone) as timezone
from cdm_latest.carrier_x_station
  left join cdm_latest.station
    on (carrier_x_station.station_cd = station.station_cd)
  left join cdm_latest.city
    on (station.city_cd = city.city_cd)
where carrier_cd = '{carrier_cd}'
group by 1, 2, 3
"""


async def get_cities(carrier_code: str) -> AsyncGenerator[City, None]:
    async for row in async_bq_query(CITY_QUERY.format(carrier_cd=carrier_code)):
        yield City(
            code=row["code"],
            country_code=row["country_code"],
            name=row["name"],
            timezone=row["timezone"],
        )


@dataclass
class CityRank:
    code: str
    name: str
    rank: int


CITY_RANKS_QUERY = """
with stats as (
  select station.city_cd,
         sum(booking_p90d_cnt) as booking_p90d_cnt,
         sum(booking_f14d_cnt) as booking_f14d_cnt,
         max(connectivity_p90d) as connectivity_p90d,
         max(connectivity_f14d) as connectivity_f14d
  from agg.carrier_station_stats
    left join cdm_latest.station
      on (station.station_cd = carrier_station_stats.station_cd)
  where report_dt = (select max(report_dt) from agg.carrier_station_stats where carrier_cd = '{carrier_cd}')
    and carrier_cd = '{carrier_cd}'
  group by 1
)
select stats.city_cd,
       city.name,
       (booking_p90d_cnt+booking_f14d_cnt) * 10
        + (connectivity_p90d+connectivity_f14d) * 2 as city_rank
from stats
  left join cdm_latest.city
   on (city.city_cd = stats.city_cd)
where booking_p90d_cnt + booking_f14d_cnt + connectivity_p90d + connectivity_f14d > 0
"""


async def get_city_ranks(carrier_code: str) -> AsyncGenerator[CityRank, None]:
    async for row in async_bq_query(CITY_RANKS_QUERY.format(carrier_cd=carrier_code)):
        yield CityRank(
            code=row["city_cd"],
            name=row["name"],
            rank=int(round(row["city_rank"])),
        )


CONNECTIONS_QUERY = """
with connection_counts as (
    select dep_station.city_cd as dep_city_cd,
           arr_station.city_cd as arr_city_cd,
           count(*)            as n_connections
    from cdm_latest.connection
      left join cdm_latest.station as dep_station
        on (dep_station.station_cd = connection.dep_station_cd)
      left join cdm_latest.station as arr_station
        on (arr_station.station_cd = connection.arr_station_cd)
    where carrier_cd = "{carrier_cd}"
      and date(dep_dttm) between date_sub(current_date(), interval 90 day) and date_add(current_date(), interval 14 day)
    group by 1, 2
), booking_counts as (
    select dep_station.city_cd as dep_city_cd,
           arr_station.city_cd as arr_city_cd,
           count(*) as n_bookings
    from cdm_latest.booking
      left join cdm_latest.station as dep_station
        on (dep_station.station_cd = conn_dep_station_cd)
      left join cdm_latest.station as arr_station
        on (arr_station.station_cd = conn_arr_station_cd)
    where conn_carrier_cd = "{carrier_cd}"
      and date(conn_dep_dttm) between date_sub(current_date(), interval 90 day) and date_add(current_date(), interval 14 day)
    group by 1, 2
), all_city_pairs as (
    select dep_city_cd,
           arr_city_cd
    from connection_counts
    union all
    select dep_city_cd,
           arr_city_cd
    from booking_counts
), all_city_paris_unique as (
    select distinct dep_city_cd,
                    arr_city_cd
    from all_city_pairs
)
select all_city_paris_unique.dep_city_cd,
       all_city_paris_unique.arr_city_cd,
       coalesce(connection_counts.n_connections,0)
        + coalesce(booking_counts.n_bookings,0) * 10 as rank
from all_city_paris_unique
    left join connection_counts
        on (connection_counts.dep_city_cd = all_city_paris_unique.dep_city_cd
            and connection_counts.arr_city_cd = all_city_paris_unique.arr_city_cd)
    left join booking_counts
        on (booking_counts.dep_city_cd = all_city_paris_unique.dep_city_cd
            and booking_counts.arr_city_cd = all_city_paris_unique.arr_city_cd)
where all_city_paris_unique.dep_city_cd != all_city_paris_unique.arr_city_cd
"""


@dataclass
class Connection:
    dep_city_cd: str
    arr_city_cd: str
    rank: int


async def get_connections(carrier_code: str) -> AsyncGenerator[Connection, None]:
    async for row in async_bq_query(CONNECTIONS_QUERY.format(carrier_cd=carrier_code)):
        yield Connection(
            dep_city_cd=row["dep_city_cd"],
            arr_city_cd=row["arr_city_cd"],
            rank=int(round(row["rank"])),
        )
