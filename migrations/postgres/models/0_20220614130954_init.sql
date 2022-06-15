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
    "departure_city_id" INT NOT NULL REFERENCES "city" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "cityname" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "locale" VARCHAR(2) NOT NULL,
    "name" VARCHAR(254) NOT NULL,
    "city_id" INT NOT NULL REFERENCES "city" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "cityrank" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "enabled" BOOL NOT NULL,
    "rank" INT NOT NULL,
    "carrier_id" INT NOT NULL REFERENCES "carrier" ("id") ON DELETE CASCADE,
    "city_id" INT NOT NULL REFERENCES "city" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);
