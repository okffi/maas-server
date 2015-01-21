# maas-server

OKFFI Fluency Navigator MaaS API server

See [Sujuvuusnavigaattori](https://github.com/okffi/sujuvuusnavigaattori) for further info.

## Server API overview

### Introduction

API server is used to collect, process and build reports on bycicle travel data.

API client applications can serve two purposes:

1. contribute travel data to the server 
2. request reports to visualize travel situation

API clients specifically submit a user's travel plans, travel traces and request reports.

All communication is done in JSON, encoded as UTF-8.

### Status handling

The server is implemented using CORS.

Empty responses generate 204 status code.

Bad requeste generate 400 status code.

Server errors generate 500 status code.

### Posting data

Data posted to the API server may come in either regular `application/x-www-form-urlencoded` format or as a JSON object with `application/json` content type.
Please note that posting arrays (i.e. multiple traces) is only supported in JSON mode.

Requests are accepted only if every part of the data is correct, i.e. if one array element is missing a mandatory field, 
all request data will be rejected.

### Journey handling

A client is expected to generate a GUID-like unique ID that is meant to identify a user actually following a travel plan and thus
performing a journey. This ID is called `journey_id` and has to be provided in the API calls as per documentation below.

Please note the following:

1. Whenever a new travel plan is accepted by the user, a new `journey_id` should be generated.
2. Whenever a long break occurs (15+ minutes of not travelling), a client application is expected to generate a new `journey_id`.

### Workflow

A typical workflow of the client application is to:

1. Generate `journey_id` as a sufficiently long (30+ characters) random string
2. Request an OTP plan
3. Supply the plan and `journey_id` to the API server, obtaining the `plan_id`
3. Display speed report for a plan using `plan_id`
4. If a user confirms the journey plan, start collecting traces, otherwise go back to 2
5. Submit traces to the API server regularly
6. If the user reaches the destination, changes the plan half-way, cancels the journey or stops
   for a significant amount of time, go back to 1.

Another common type of workflow is to diplay speed situation using geoJSON coordinates of
a user's viewport as a `boundaries` parameter.

### Plans

Plans are produced by [Open Trip Planner](http://www.opentripplanner.org/) based on [Open Street Map](http://www.openstreetmap.org/) and are used to spatially describe a travel intention of a user.

The `geometry` field is expected to be a LineString.

Plans are used to map traces onto existing map objects (streets etc.) to correct potentially inaccurate GSM data.

`POST /plans`

Parameters:

name              | format   | units | mandatory | example
----------------- | -------- | ----- | --------- | --------
journey_id        | string   |       | yes       |
geometry          | geoJSON  |       | yes       | This should be an array of 
timestamp         | string   |       | yes       | This should be in ISO8601 format (see [toJSON()](http://www.w3schools.com/jsref/jsref_tojson.asp) method)

Such request will return a unique plan id that can be used to retrieve plan details later via the following request:

`GET /plans/{planID}`

or to obtain a report on average speeds (see below).

### Traces

Traces are momentary snapshots of data about a moving bycicle rider as collected from a mobile client.
Each trace contains a single set of spatial coordinates and momentary speed as reported by the client GPS.
The speed unit is meters per second.

Data structure is based on [Leaflet API reference](http://leafletjs.com/reference.html).

the `accuracy` and `alt_accuracy` units are meters.

The `heading` is measured in degrees, ranged 0-360, north-referenced.

The `point` attribute is expected to have a Point type.

Traces form a very raw dataset of information about bycicle travel.

`POST /traces`

Parameters:

name              | format   | mandatory | Note
----------------- | -------- | --------- | --------
journey_id        | string   | yes       | 
timestamp         | string   | yes       | This should be in ISO8601 format (see [toJSON()](http://www.w3schools.com/jsref/jsref_tojson.asp) method)
latitude          | float    | yes       | Detected geographical latitude of the user. 
longitude         | float    | yes       | Detected geographical longitude of the user.
speed             | float    | yes       | Current velocity in meters per second.
accuracy          | float    | no        | Accuracy of location in meters.
altitude          | float    | no        | Height of the position above the WGS84 ellipsoid in meters.
altitude_accuracy | float    | no        | Accuracy of altitude in meters.
heading           | float    | no        | The direction of travel in degrees counting clockwise from true North.

This endpoint also supports posting multiple traces as an `application/json` JSON array.

### Reports

Reports generate aggregated data about average bycicle speeds in various spatial areas.

`GET /reports/speed-averages`

Parameters:

name              | format   | mandatory | example
----------------- | -------- | --------- | --------
plan_id           | integer  | no        |
boundaries        | geoJSON  | no        |
after             | string   | no        | 
before            | string   | no        |

There are optional parameters that provide for limiting aggregation and averages based on space and/or time.
Specifically, `boundaries` is a geoJSON bounding box; `before` and `after` are timestamps to limit selection 
(moments of time indicated by either of the timestamps are excluded from selection).

If a `plan_id` is provided, the report will only cover areas that are part of the specified plan.

## Database schema

Fluency related data is stored in the following db tables (PostgreSQL/PotGIS data types):

Trace:

Name              | Type         | notnull   | PK        | Notes
----------------- | ------------ | --------- | --------- | -------
trace_id          | int8         | true      | true      |
journey_id        | varchar      | true      |           |
timestamp         | timestamptz  | true      |           |
geometry          | geometry     | true      |           | POINT
speed             | float        | true      |           |
accuracy          | float        | false     |           |
altitude          | float        | false     |           |
altitude_accuracy | float        | false     |           |
heading           | float        | false     |           |

Plan:

Name                | Type          | notnull   | PK     | notes
------------------- | ------------- | --------- | ------ | -------
plan_id             | int8          | true      | true   |
journey_id          | varchar       | true      |        |
timestamp           | timestamptz   | true      |        |
geometry            | geometry      | true      |        | LINESTRING
<!---
mode                | varchar       | false     |        |
max_walk_distance   | int4          | false     |        |
min_transfer_time   | float         | false     |        |
walk_speed          | float         | false     |        |
--->

Route *:

Name            | Type         | notnull   | PK       | Notes
--------------- | ------------ | --------- | -------- | -----
route_id        | int8         | true      | true     |
journey_id      | varchar      | true      |          |
timestamp       | timestamptz  | true      |          |
geometry        | geometry     | true      |          | LINESTRING
speed           | float        | true      |          |
mode            | varchar      | true      |          |
was_on_route    | bool         | false     |          |

* routes are to be obsoleted in the near future

## Server dockerization 

Maas-docker is a utility that facilitates deployment and running
of MaaS API Server via Docker container with the use of Packer.

[Packer](https://packer.io/) is a utility to streamline creation and deployment of virtual
machine images.

[Docker](http://docker.io/) is a flavor of machine virtualization tools with neat features.

This script allows you to:

    a) create Docker image from official ubuntu:latest and build MaaS API Server environment inside it

    b) run MaaS API API Server as a docker container

    d) view running Docker containers

    e) stop a running Docker container

The script is also capable of updating the base operating system.

Run script to see the usage help.