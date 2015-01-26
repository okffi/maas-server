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
    "realtime"          BOOLEAN NOT NULL DEFAULT TRUE
);

SELECT AddGeometryColumn('trace', 'geometry', 4326, 'POINT', 3);
SELECT AddGeometryColumn('plan', 'geometry', 4326, 'LINESTRING', 3);
SELECT AddGeometryColumn('route', 'geometry', 4326, 'LINESTRING', 3);
CREATE INDEX trace_geometry_gix ON trace USING GIST (geometry);
CREATE INDEX plan_geometry_gix ON plan USING GIST (geometry);
CREATE INDEX route_geometry_gix ON route USING GIST (geometry);

CREATE TABLE IF NOT EXISTS report (
    "speed"             DECIMAL(21,16),
    "type"              TEXT,
    "timestamp"         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);

SELECT AddGeometryColumn('report', 'geometry', 4326, 'LINESTRING', 3);
CREATE INDEX averages_geometry_gix ON trace USING GIST (geometry);

-- CREATE OR REPLACE VIEW journey AS 
--    SELECT  journey_id, 
--            MIN(timestamp) AS start_time, 
--            MAX(timestamp) AS end_time, 
--            ST_LineMerge(ST_Union(geometry)) as geometry
            -- array_agg(speed) AS speed
--    FROM route 
--    GROUP BY journey_id;

-- CREATE OR REPLACE VIEW web AS 
--    SELECT
--        ST_LineMerge(ST_Union(geometry)) as geometry
--    FROM route;