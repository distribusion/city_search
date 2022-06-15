-- upgrade --
CREATE TABLE IF NOT EXISTS "carrierupdatetask" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "code" VARCHAR(4) NOT NULL,
    "task_code" VARCHAR(31) NOT NULL UNIQUE,
    "started" TIMESTAMP NOT NULL,
    "heartbeat" TIMESTAMP NOT NULL,
    "ended" TIMESTAMP,
    "success" INT,
    "traceback" TEXT,
    "parameters" JSON NOT NULL,
    "result" JSON
);
-- downgrade --
DROP TABLE IF EXISTS "carrierupdatetask";
