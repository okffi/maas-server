# maas-server

OKFFI Fluency Navigator MaaS API server

See [Sujuvuusnavigaattori](https://github.com/okffi/sujuvuusnavigaattori) for further info.

## Server API overview

### Introduction

API server is used to collect, process and build reports on bicycle travel data.

API client applications can serve two purposes:

1. contribute travel data to the server 
2. request reports to visualize travel situation

API clients specifically submit user's travel plans, traces, routes and may request and visualize reports.

Default format is JSON encoded as UTF-8.

Input data should be submitted with `Content-type: application/json` header, in which case request
body must contain a JSON object.

In case `Content-type: application/json` header is not present, all data should be submitted as
a JSON-encoded string in a `payload` parameter.

#### Examples

Consider this plan object to be submitted:

```
var obj={
        journey_id: 'abcdefghijklmnopqrstuvwxyz0123456789', 
        timestamp: (new Date()).toJSON(), 
        coordinates: [[0,0], [0,1], [1,1], [1,0]]
    };
```

Standard approach:

```
$.ajax({
    url: 'http://maas.okf.fi/plans',
    type: 'POST',
    contentType: 'application/json',
    data: JSON.stringify(obj)
})
.done(...)
```

Conservative approach:

```
$.ajax({
    url: 'http://maas.okf.fi/plans',
    type: 'POST',
    data: { payload:JSON.stringify(obj) }
})
.done(...)
```

### Status and error handling

The server supports [CORS](http://en.wikipedia.org/wiki/Cross-origin_resource_sharing).

Successful responses with payload generate status code 200.

Empty responses generate status code 204.

Bad requests generate status code 400.

Server errors generate status code 500.

Requests are rejected entirely even if one of data elements is missing a mandatory field.

### Journey handling

A client is expected to generate a UUID-like unique ID that is meant to identify a user actually following a travel plan and thus
performing a journey. This ID is called `journey_id` and has to be provided in the API calls as per documentation below.

Please see the workflow description for working with `journey_id`.

### Workflow

A typical workflow of client application is to:

1. Generate `journey_id` as a sufficiently long (30+ characters) random string
2. Request an OTP plan
3. Supply the plan and `journey_id` to the API server, obtaining the `plan_id`
4. Display speed report for a plan using `plan_id`
5. If user confirms the journey plan, start collecting traces/routes, otherwise go back to 2
6. Submit traces/routes to the API server regularly
7. If user reaches the destination, hits the stop button, cancels the journey or does not move
   for a significant amount of time (15+ minutes), go back to 1.
8. If user requests a new plan on the way, go back to 2.

Another common type of workflow is to diplay speed situation using coordinates of a user's viewport as a `boundaries` parameter.

### Endpoints

Below is a list of currently implementes server endpoints.

URI                              | Description
-------------------------------- | ------------------------------------------------------------------
`GET /reports/speed-averages`    | Obtain average speed report as a geoJSON FeatureCollection
`GET /plans/{planID}`            | Obtain a previously saved plan as a geoJSON Feature
`POST /plans`                    | Save a plan
`POST /traces`                   | Save a trace or several traces
`POST /routes`                   | Save a route or several routes
`GET /demo.html`                 | Open a demo page (`Content-type: text/html`)
`GET /wfs.xml?`                  | A very simple [WFS](http://www.opengeospatial.org/standards/wfs)-compatible interface to report data (`Content-type: text/xml`)

### Plans

Plans are produced by [Open Trip Planner](http://www.opentripplanner.org/) based on [Open Street Map](http://www.openstreetmap.org/) and are used to spatially describe a travel intention of a user.

Plans are used to map traces onto existing map objects (streets etc.) to correct potentially inaccurate GPS data.

`POST /plans`

Parameters:

Name              | Format   | Mandatory | Notes
----------------- | -------- | --------- | --------
journey_id        | string   | yes       |
coordinates       | array    | yes       | This must be a from->to array of 2 or more coordinates as in a [geoJSON](http://geojson.org/geojson-spec.html) LINESTRING: longitude, latitude [, altitude]
timestamp         | string   | yes       | This should be in ISO8601 format with time zone (see [toJSON()](http://www.w3schools.com/jsref/jsref_tojson.asp) method). Submitting time in UTC time zone is strongly recommended

Such request will return a unique plan id that can be used to retrieve plan details later via the following request:

`GET /plans/{planID}`

or to obtain a report on average speeds (see below).

### Routes

Routes are segments (lines) in a travel plan that the traveller has just completed. A route is a just a single line with an 
average speed (in m/s) calculated for that line.

Routes form a dataset for average speeds report.

`POST /routes` 

supports both single-object and array-of-objects formats.

Parameters:

Name              | Format   | Mandatory | Notes
----------------- | -------- | --------- | --------
journey_id        | string   | yes       | 
timestamp         | string   | yes       | This should be in ISO8601 format with time zone (see [toJSON()](http://www.w3schools.com/jsref/jsref_tojson.asp) method). Submitting time in UTC time zone is strongly recommended.
coordinates       | array    | yes       | This must be a from->to array of exactly 2 coordinates as in a [geoJSON](http://geojson.org/geojson-spec.html) LINESTRING: longitude, latitude [, altitude]
speed             | float    | yes       | Average speed along the route.
mode              | string   | yes       | OTP plan mode

### Traces

Traces are momentary snapshots of data about a moving bicycle rider as collected from a mobile client.
Each trace contains a single set of spatial coordinates.

Traces form a very basic dataset about actual bicycle travel.

`POST /traces` 

supports both single-object and array-of-objects formats.

Parameters:

Name              | Format   | Mandatory | Notes
----------------- | -------- | --------- | --------
journey_id        | string   | yes       | 
timestamp         | string   | yes       | This should be in ISO8601 format with time zone (see [toJSON()](http://www.w3schools.com/jsref/jsref_tojson.asp) method). Submitting time in UTC time zone is strongly recommended.
latitude          | float    | yes       | Geographical latitude of a user
longitude         | float    | yes       | Geographical longitude of a user
altitude          | float    | no        | Geographical altitude of a user

### Reports

Reports generate aggregated data about average bicycle speeds in various spatial areas.

Data returned is a `FeatureCollection` from [geoJSON specification](http://geojson.org/geojson-spec.html).

Each feature has a `geometry` attribute, containing a linestring, and a `speed` custom property that contains an array of average speed
values in meter/second, matching al of the segments in that linestring.

`GET /reports/speed-averages`

Parameters:

Name                | Format   | Mandatory | Notes
------------------- | -------- | --------- | --------
plan_id             | integer  | no        | Obtained in a separate POST call (see above)
boundary_sw_lon     | float    | no        | Longitude of the south-western boundary (all four must be present)
boundary_sw_lat     | float    | no        | Latitude of the south-western boundary
boundary_ne_lon     | float    | no        | Longitude of the north-eastern boundary
boundary_ne_lat     | float    | no        | Latitude of the north-eastern boundary
after               | string   | no        | This should be in ISO8601 format with time zone (see [toJSON()](http://www.w3schools.com/jsref/jsref_tojson.asp) method). Submitting time in UTC time zone is strongly recommended.
before              | string   | no        | Same as above
type                | string   | no        | can be either `baseline`, `realtime` or `combined` (default: `combined`)


There are optional parameters that provide for limiting aggregation and averages based on space and/or time.
Specifically, `boundaries` is used to specify spatial limit; `before` and `after` are timestamps to limit selection 
(moments of time indicated by either of the timestamps are excluded from selection).

If a `plan_id` is provided, the report will only cover areas that are part of the specified plan.

Baseline reports are based on carefully processed data, realtime reports are based on community data.

## Database schema

Fluency related data is stored in the following db tables (PostgreSQL/PotGIS data types):

`trace` table:

Name              | Type           | notnull   | PK        | Notes
----------------- | -------------- | --------- | --------- | -------
trace_id          | BIGSERIAL      | true      | true      |
journey_id        | TEXT           | true      |           |
timestamp         | TIMESTAMP      | true      |           |
geometry          | geometry       | true      |           | POINT

`plan` table:

Name              | Type           | notnull   | PK        | notes
----------------- | -------------- | --------- | --------- | -------
plan_id           | BIGSERIAL      | true      | true      |
journey_id        | TEXT           | true      |           |
timestamp         | TIMESTAMP      | true      |           | WITH TIME ZONE
geometry          | geometry       | true      |           | LINESTRING

`route` table:

Name              | Type           | notnull   | PK        | Notes
----------------- | -------------- | --------- | --------- | -----
route_id          | BIGSERIAL      | true      | true      | 
journey_id        | TEXT           | true      |           | 
timestamp         | TIMESTAMP      | true      |           | WITH TIMEZONE
geometry          | geometry       | true      |           | LINESTRING, simple, two points
speed             | DECIMAL(21,16) | true      |           |
mode              | TEXT           | true      |           | obtained from an OTP plan
realtime          | BOOLEAN        | false     |           | default: true

`report` table (used as a cache for quicker delivery of report data):

Name              | Type           | notnull   | PK        | Notes
----------------- | -------------- | --------- | --------- | -----
report_id         | BIGSERIAL      | true      | true      | 
timestamp         | TIMESTAMP      | true      |           | WITH TIMEZONE, contains report generation time
geometry          | geometry       | true      |           | LINESTRING
speed             | DECIMAL(21,16) | true      |           | average speed per linestring, defaults to 0
reading           | DECIMAL(21,16) | true      |           | average number of readings per linestring, defaults to 0
type              | TEXT           | true      |           | either 'realtime', 'baseline' or 'combined'

## Server dockerization 

Maas-docker is a utility that facilitates deployment and running
of MaaS API Server via Docker container with the use of Packer.

[Packer](https://packer.io/) is a utility to streamline creation and deployment of virtual
machine images.

[Docker](http://docker.io/) is a flavor of machine virtualization tools with neat features.

`maas-docker.sh` script allows you to:

1. create Docker image from official ubuntu:latest and build MaaS API Server environment inside it
2. run MaaS API API Server as a docker container
3. view running Docker containers
4. stop a running Docker container

The script is also capable of updating the base operating system.

Run script to see the usage help.