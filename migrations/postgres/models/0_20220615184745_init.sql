-- upgrade --
CREATE TABLE IF NOT EXISTS "carrier" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "code" VARCHAR(4) NOT NULL UNIQUE,
    "name" VARCHAR(254) NOT NULL,
    "supports_return" BOOL NOT NULL,
    "enabled" BOOL NOT NULL
);
CREATE TABLE IF NOT EXISTS "country" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "code" VARCHAR(2) NOT NULL,
    "name" VARCHAR(254) NOT NULL
);
CREATE TABLE IF NOT EXISTS "city" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "code" VARCHAR(5) NOT NULL UNIQUE,
    "timezone" VARCHAR(254) NOT NULL,
    "country_id" INT NOT NULL REFERENCES "country" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "city"."country_id" IS 'Country of the city';
CREATE TABLE IF NOT EXISTS "cityconnection" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "rank" INT,
    "arrival_city_id" INT NOT NULL REFERENCES "city" ("id") ON DELETE CASCADE,
    "carrier_id" INT NOT NULL REFERENCES "carrier" ("id") ON DELETE CASCADE,
    "departure_city_id" INT NOT NULL REFERENCES "city" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_cityconnect_carrier_7f2731" UNIQUE ("carrier_id", "departure_city_id", "arrival_city_id")
);
CREATE INDEX IF NOT EXISTS "idx_cityconnect_carrier_7f2731" ON "cityconnection" ("carrier_id", "departure_city_id", "arrival_city_id");
CREATE TABLE IF NOT EXISTS "cityname" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "locale" VARCHAR(2) NOT NULL,
    "name" VARCHAR(254) NOT NULL,
    "city_id" INT NOT NULL REFERENCES "city" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_cityname_city_id_b0a300" UNIQUE ("city_id", "locale")
);
CREATE INDEX IF NOT EXISTS "idx_cityname_city_id_b0a300" ON "cityname" ("city_id", "locale");
CREATE TABLE IF NOT EXISTS "cityrank" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "enabled" BOOL NOT NULL,
    "rank" INT NOT NULL,
    "carrier_id" INT NOT NULL REFERENCES "carrier" ("id") ON DELETE CASCADE,
    "city_id" INT NOT NULL REFERENCES "city" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_cityrank_city_id_3fa3e9" UNIQUE ("city_id", "carrier_id")
);
CREATE INDEX IF NOT EXISTS "idx_cityrank_city_id_3fa3e9" ON "cityrank" ("city_id", "carrier_id");
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);
