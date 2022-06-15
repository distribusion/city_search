-- upgrade --
CREATE TABLE IF NOT EXISTS "carrier" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "code" VARCHAR(4) NOT NULL UNIQUE,
    "name" VARCHAR(254) NOT NULL,
    "supports_return" INT NOT NULL,
    "enabled" INT NOT NULL
);
CREATE TABLE IF NOT EXISTS "country" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "code" VARCHAR(2) NOT NULL,
    "name" VARCHAR(254) NOT NULL
);
CREATE TABLE IF NOT EXISTS "city" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "code" VARCHAR(5) NOT NULL UNIQUE,
    "timezone" VARCHAR(254) NOT NULL,
    "country_id" INT NOT NULL REFERENCES "country" ("id") ON DELETE CASCADE /* Country of the city */
);
CREATE TABLE IF NOT EXISTS "cityconnection" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "rank" INT,
    "arrival_city_id" INT NOT NULL REFERENCES "city" ("id") ON DELETE CASCADE,
    "carrier_id" INT NOT NULL REFERENCES "carrier" ("id") ON DELETE CASCADE,
    "departure_city_id" INT NOT NULL REFERENCES "city" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_cityconnect_carrier_7f2731" UNIQUE ("carrier_id", "departure_city_id", "arrival_city_id")
);
CREATE INDEX IF NOT EXISTS "idx_cityconnect_carrier_7f2731" ON "cityconnection" ("carrier_id", "departure_city_id", "arrival_city_id");
CREATE TABLE IF NOT EXISTS "cityname" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "locale" VARCHAR(2) NOT NULL,
    "name" VARCHAR(254) NOT NULL,
    "city_id" INT NOT NULL REFERENCES "city" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_cityname_city_id_b0a300" UNIQUE ("city_id", "locale")
);
CREATE INDEX IF NOT EXISTS "idx_cityname_city_id_b0a300" ON "cityname" ("city_id", "locale");
CREATE TABLE IF NOT EXISTS "cityrank" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "enabled" INT NOT NULL,
    "rank" INT NOT NULL,
    "carrier_id" INT NOT NULL REFERENCES "carrier" ("id") ON DELETE CASCADE,
    "city_id" INT NOT NULL REFERENCES "city" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_cityrank_city_id_3fa3e9" UNIQUE ("city_id", "carrier_id")
);
CREATE INDEX IF NOT EXISTS "idx_cityrank_city_id_3fa3e9" ON "cityrank" ("city_id", "carrier_id");
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSON NOT NULL
);
