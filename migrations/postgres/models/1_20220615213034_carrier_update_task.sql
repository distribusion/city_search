-- upgrade --
CREATE TABLE IF NOT EXISTS "carrierupdatetask" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "code" VARCHAR(4) NOT NULL,
    "task_code" VARCHAR(31) NOT NULL UNIQUE,
    "started" TIMESTAMPTZ NOT NULL,
    "heartbeat" TIMESTAMPTZ NOT NULL,
    "ended" TIMESTAMPTZ,
    "success" BOOL,
    "traceback" TEXT,
    "parameters" JSONB NOT NULL,
    "result" JSONB
);
-- downgrade --
DROP TABLE IF EXISTS "carrierupdatetask";
