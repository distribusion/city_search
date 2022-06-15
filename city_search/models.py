"""
Models
"""

from tortoise import fields
from tortoise.models import Model


class Carrier(Model):
    id = fields.IntField(pk=True, db_index=True, unique=True)
    code = fields.CharField(max_length=4, null=False, unique=True, db_index=True)
    name = fields.CharField(max_length=254, null=False)
    supports_return = fields.BooleanField()
    enabled = fields.BooleanField()
    city_ranks: fields.ReverseRelation["CityRank"]
    city_connections: fields.ReverseRelation["CityConnection"]


class Country(Model):
    id = fields.IntField(pk=True, db_index=True, unique=True)
    name = fields.CharField(max_length=254, null=False)
    cities: fields.ReverseRelation["City"]


class City(Model):
    id = fields.IntField(pk=True, db_index=True, unique=True)
    code = fields.CharField(max_length=5, null=False, unique=True, db_index=True)
    timezone = fields.CharField(max_length=254, null=False)
    country: fields.ForeignKeyRelation[Country] = fields.ForeignKeyField(
        "models.Country",
        related_name="cities",
        null=False,
        description="Country of the city",
    )
    ranks: fields.ReverseRelation["CityRank"]
    names: fields.ReverseRelation["CityName"]


class CityName(Model):
    id = fields.IntField(pk=True, db_index=True, unique=True)
    city: fields.ForeignKeyRelation[City] = fields.ForeignKeyField(
        "models.City",
        related_name="names",
        null=False,
    )
    locale = fields.CharField(max_length=2, null=False)
    name = fields.CharField(max_length=254, null=False)

    class Meta:
        unique_together = (
            "city",
            "locale",
        )
        indexes = (("city", "locale"),)


class CityRank(Model):
    id = fields.IntField(pk=True, db_index=True, unique=True)
    city: fields.ForeignKeyRelation[City] = fields.ForeignKeyField(
        "models.City",
        related_name="ranks",
        null=False,
    )
    carrier: fields.ForeignKeyRelation[Carrier] = fields.ForeignKeyField(
        "models.Carrier",
        related_name="city_ranks",
        null=False,
    )
    enabled = fields.BooleanField()
    rank = fields.IntField()

    class Meta:
        unique_together = (
            "city",
            "carrier",
        )
        indexes = (("city", "carrier"),)


class CityConnection(Model):
    id = fields.IntField(pk=True, db_index=True, unique=True)
    carrier: fields.ForeignKeyRelation[Carrier] = fields.ForeignKeyField(
        "models.Carrier",
        related_name="connections",
        null=False,
    )
    departure_city: fields.ForeignKeyRelation[City] = fields.ForeignKeyField(
        "models.City",
        related_name="departure_connections",
        null=False,
    )
    arrival_city: fields.ForeignKeyRelation[City] = fields.ForeignKeyField(
        "models.City",
        related_name="arrival_connections",
        null=False,
    )
    rank = fields.IntField(null=True)

    class Meta:
        unique_together = ("carrier", "departure_city", "arrival_city")
        indexes = (("carrier", "departure_city", "arrival_city"),)
