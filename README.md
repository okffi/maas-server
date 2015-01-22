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
        coordinates: [[0, 0], [0,1], [1,1], [1,0]
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

### Status handling

The server suports [CORS](http://en.wikipedia.org/wiki/Cross-origin_resource_sharing).

Successful responses with payload generate status code 200.

Empty responses generate status code 204.

Bad requeste generate status code 400.

Server errors generate status code 500.

### Posting data

Data posted to the API server may come in either regular `application/x-www-form-urlencoded` format or as a JSON object with `application/json` content type.
Please note that posting arrays (i.e. multiple traces) is only supported in JSON mode.

Requests are accepted only if every part of the data is correct, i.e. if one array element is missing a mandatory field, 
all request data will be rejected.

### Journey handling

A client is expected to generate a GUID-like unique ID that is meant to identify a user actually following a travel plan and thus
performing a journey. This ID is called `journey_id` and has to be provided in the API calls as per documentation below.

Please see the workflow description for working with `journey_id`.

### Workflow

A typical workflow of client application is to:

1. Generate `journey_id` as a sufficiently long (30+ characters) random string
2. Request an OTP plan
3. Supply the plan and `journey_id` to the API server, obtaining the `plan_id`
4. Display speed report for a plan using `plan_id`
5. If a user confirms the journey plan, start collecting traces, otherwise go back to 2
6. Submit traces to the API server regularly
7. If the user reaches the destination, hits the stop button, cancels the journey or does not move
   for a significant amount of time, go back to 1.
8. If the user just requests a new plan on the way, go back to 2.

Another common type of workflow is to diplay speed situation using geoJSON coordinates of
a user's viewport as a `boundaries` parameter.

### Plans

Plans are produced by [Open Trip Planner](http://www.opentripplanner.org/) based on [Open Street Map](http://www.openstreetmap.org/) and are used to spatially describe a travel intention of a user.

The `geometry` field is expected to be a LineString.

Plans are used to map traces onto existing map objects (streets etc.) to correct potentially inaccurate GSM data.

`POST /plans`

Parameters:

Name              | Format   | Mandatory | Notes
----------------- | -------- | --------- | --------
journey_id        | string   | yes       |
coordinates       | array    | yes       | This must be a from->to ordered array of 2 or more [geoJSON-compatible coordinates](http://geojson.org/geojson-spec.html)
timestamp         | string   | yes       | This should be in ISO8601 format (see [toJSON()](http://www.w3schools.com/jsref/jsref_tojson.asp) method)

Such request will return a unique plan id that can be used to retrieve plan details later via the following request:

`GET /plans/{planID}`

or to obtain a report on average speeds (see below).

### Traces

Traces are momentary snapshots of data about a moving bycicle rider as collected from a mobile client.
Each trace contains a single set of spatial coordinates and momentary speed as reported by the client GPS.
The speed unit is meters per second.

Traces form a very raw dataset of information about bycicle travel.

`POST /traces` 

supports both single-object and array-of-objects formats.

Parameters:

Name              | Format   | Mandatory | Notes
----------------- | -------- | --------- | --------
journey_id        | string   | yes       | 
timestamp         | string   | yes       | This should be in ISO8601 format (see [toJSON()](http://www.w3schools.com/jsref/jsref_tojson.asp) method)
latitude          | float    | yes       | Geographical latitude of a point in the travel plan closest to the user at timestamp.
longitude         | float    | yes       | Geographical longitude of a point in the travel plan closest to the user at timestamp.

This endpoint also supports posting multiple traces as an `application/json` JSON array.

### Reports

Reports generate aggregated data about average bycicle speeds in various spatial areas.

`GET /reports/speed-averages`

Parameters:

Name              | Format   | Mandatory | Notes
----------------- | -------- | --------- | --------
plan_id           | integer  | no        |
boundaries        | array    | no        | This must be an array of 2 [geoJSON-compatible coordinates](http://geojson.org/geojson-spec.html)
after             | string   | no        | 
before            | string   | no        |

There are optional parameters that provide for limiting aggregation and averages based on space and/or time.
Specifically, `boundaries` is a geoJSON bounding box; `before` and `after` are timestamps to limit selection 
(moments of time indicated by either of the timestamps are excluded from selection).

If a `plan_id` is provided, the report will only cover areas that are part of the specified plan.

## Database schema

Fluency related data is stored in the following db tables (PostgreSQL/PotGIS data types):

Trace:

Name              | Type           | notnull   | PK        | Notes
----------------- | -------------- | --------- | --------- | -------
trace_id          | BIGSERIAL      | true      | true      |
journey_id        | TEXT           | true      |           |
timestamp         | TIMESTAMP      | true      |           |
geometry          | geometry       | true      |           | POINT

Plan:

Name                | Type          | notnull   | PK     | notes
------------------- | ------------- | --------- | ------ | -------
plan_id             | BIGSERIAL     | true      | true   |
journey_id          | TEXT          | true      |        |
timestamp           | TIMESTAMP     | true      |        | WITH TIME ZONE
geometry            | geometry      | true      |        | LINESTRING

Route *:

Name            | Type           | notnull   | PK       | Notes
--------------- | -------------- | --------- | -------- | -----
route_id        | BIGSERIAL      | true      | true     |
journey_id      | TEXT           | true      |          |
timestamp       | TIMESTAMP      | true      |          | WITH TIMEZONE
geometry        | geometry       | true      |          | LINESTRING
speed           | DECIMAL(21,16) | true      |          |
mode            | TEXT           | true      |          |
was_on_route    | BOOLEAN        | false     |          |

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