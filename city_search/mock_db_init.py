import logging
from typing import Any, Dict

from city_search import models

logger = logging.getLogger(__name__)


async def create_country(name: str) -> models.Country:
    country, _ = await models.Country.get_or_create(name=name)
    return country


async def create_carrier(code: str, name: str, supports_return: bool) -> models.Carrier:
    carrier, _ = await models.Carrier.get_or_create(
        code=code,
        defaults=dict(
            name=name,
            enabled=True,
            supports_return=supports_return,
        ),
    )

    return carrier


async def create_city(
    code: str, country: models.Country, translations: Dict[str, Any]
) -> models.City:
    city, _ = await models.City.get_or_create(
        code=code,
        defaults=dict(
            timezone="Europe/London",
            country=country,
        ),
    )

    for locale, translation in translations.items():
        translation = await models.CityName.get_or_create(
            city=city, locale=locale, defaults=dict(name=translation)
        )

    return city


async def add_city_rank(city: models.City, carrier: models.Carrier, rank: int) -> None:
    await models.CityRank.get_or_create(
        city=city,
        carrier=carrier,
        defaults=dict(
            enabled=True,
            rank=rank,
        ),
    )


async def add_city_connection(
    carrier: models.Carrier, dep_city: models.City, arr_city: models.City
) -> None:
    connection, created = await models.CityConnection.get_or_create(
        carrier=carrier,
        departure_city=dep_city,
        arrival_city=arr_city,
        defaults=dict(rank=None),
    )


async def create_test_data():
    country = await create_country("Great Britain")

    city1 = await create_city(
        "GBLON",
        country,
        translations={
            "ru": "Лондон",
            "fr": "Londres",
            "pl": "Londyn",
            "cs": "Londýn",
            "es": "londres",
            "nl": "Londen",
            "pt": "Londres",
            "bg": "Лондон",
            "it": "Londra",
            "en": "London",
        },
    )
    city2 = await create_city("GBEDI", country, translations={"en": "Edinburgh"})

    carrier_nr = await create_carrier("NEXP", "National Express", False)

    carrier_wr = await create_carrier("ALSA", "Alsa", True)

    await add_city_rank(city1, carrier_nr, 0)
    await add_city_rank(city2, carrier_nr, 2)
    await add_city_connection(carrier_nr, city1, city2)
    await add_city_connection(carrier_nr, city2, city1)

    await add_city_rank(city1, carrier_wr, 1)
    await add_city_rank(city2, carrier_wr, 0)
    await add_city_connection(carrier_wr, city1, city2)
