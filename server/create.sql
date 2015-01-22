CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS trace (
    "trace_id"           BIGSERIAL PRIMARY KEY,
    "journey_id"         TEXT NOT NULL,
    "timestamp"          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS plan (
    "plan_id"            BIGSERIAL PRIMARY KEY,
    "journey_id"         TEXT NOT NULL,
    "timestamp"          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp    
);

CREATE TABLE IF NOT EXISTS route (
    "route_id"          BIGSERIAL PRIMARY KEY,
    "journey_id"        TEXT NOT NULL,
    "timestamp"         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp,
    "speed"             DECIMAL(21,16) NOT NULL DEFAULT 0,
    "mode"              TEXT NOT NULL,
    "was_on_route"      BOOLEAN 
);

SELECT AddGeometryColumn('trace', 'geometry', 4326, 'POINT', 2);
SELECT AddGeometryColumn('plan', 'geometry', 4326, 'LINESTRING', 2);
SELECT AddGeometryColumn('route', 'geometry', 4326, 'LINESTRING', 2);
CREATE INDEX trace_geometry_gix ON trace USING GIST (geometry);
CREATE INDEX plan_geometry_gix ON plan USING GIST (geometry);
CREATE INDEX route_geometry_gix ON route USING GIST (geometry);

-- just ignore this for now
-- 
-- CREATE TABLE traces
--    ALTER COLUMN "speed" TYPE float8
--        USING CAST("speed" as double precision)
--    ALTER COLUMN "accuracy" TYPE float8
--        USING CAST("accuracy" as double precision)
--    ALTER COLUMN "aaccuracy" TYPE float8
--        USING CAST("aaccuracy" as double precision)
--    ALTER COLUMN "heading" TYPE float8
--        USING CAST("heading" as double precision)
--    ALTER COLUMN "altitude" TYPE float8
--        USING CAST("altitude" as double precision);
--    ALTER COLUMN "timestamp" TYPE timestamptz
--        USING to_timestamp("timestamp", 'YYYY-MM-DD"T"HH24:MI:SS.USZ') at time zone 'UTC';
--    ALTER COLUMN geometry TYPE geometry(POINT, 4326)
--        USING ST_SetSRID(geometry,4326);

-- ALTER TABLE routes
--     ALTER COLUMN geometry TYPE geometry(LINESTRING, 4326) 
--        USING ST_SetSRID(geometry,4326);



