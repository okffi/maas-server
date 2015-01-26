import sys
import BaseHTTPServer
import SimpleHTTPServer

import SocketServer
import time
import datetime
import cgi
import urlparse
import json
import re
import copy

import geohash

from math import radians, cos, sin, asin, sqrt
#from random import randint

import psycopg2 as db
import ppygis

class BadRequestException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return self.value

class App():
    
    def cursor(self):
        if not hasattr(self, 'connection'):
            self.connection=db.connect("dbname=sujuvuusnavigaattori")
        if not hasattr(self, '_cursor'):
            self._cursor=self.connection.cursor()
        return self._cursor
    
    def __exit__(self, type, value, traceback):
        self.connection.close()
        
    def savePlan(self, plan):
        cursor = self.cursor()
        if not 'journey_id' in plan or plan['journey_id'] is None or plan['journey_id'] == '':
            raise BadRequestException('plan journey_id is missing')
        if not 'timestamp' in plan or plan['timestamp'] is None or plan['timestamp'] == '':
            raise BadRequestException('plan timestamp is missing')
        if not 'coordinates' in plan or type(plan['coordinates']) is not list:
            raise BadRequestException('plan coordinates are missing')
        linestring=[]
        for point in plan['coordinates']:
            # as per http://geojson.org/geojson-spec.html
            longitude=float(point[0])
            latitude=float(point[1])
            if len(point) > 2:
                altitude=float(point[2])
            else:
                altitude=0
            linestring.append(ppygis.Point(longitude, latitude, altitude, srid=4326))
        cursor.execute("INSERT INTO plan (geometry, journey_id, timestamp) VALUES (%s, %s, %s) RETURNING plan_id", 
                           (ppygis.LineString(linestring, srid=4326), plan['journey_id'], plan['timestamp']))
        plan_id = cursor.fetchone()[0]
        self.connection.commit()
        return plan_id

    def saveTraces(self, traces):
        if type(traces) is not list:
            traces = [traces]
        cursor = self.cursor()
        for trace in traces:
            if not 'journey_id' in trace or trace['journey_id'] is None or trace['journey_id'] == '':
                raise BadRequestException('trace journey_id is missing')
            if not 'timestamp' in trace or trace['timestamp'] is None or trace['timestamp'] == '':
                raise BadRequestException('trace timestamp is missing')
            if not 'latitude' in trace or trace['latitude'] is None or trace['latitude'] == '':
                raise BadRequestException('trace latitude is missing')
            if not 'longitude' in trace or trace['longitude'] is None or trace['longitude'] == '':
                raise BadRequestException('trace longitude is missing')
            if not 'speed' in trace or trace['speed'] is None or trace['speed'] == '':
                raise BadRequestException('trace speed is missing')
            if not 'altitude' in trace or trace['altitude'] is None or trace['altitude'] == '':
                trace['altitude']=0
            cursor.execute("INSERT INTO trace (geometry, journey_id, timestamp) VALUES (%s, %s, %s)", 
                           (ppygis.Point(float(trace['longitude']), float(trace['latitude']), float(trace['altitude']), srid=4326), trace['journey_id'], trace['timestamp']))
        self.connection.commit()
        return

    def saveRoutes(self, routes):
        if type(routes) is not list:
            routes = [routes]
        cursor = self.cursor()
        for route in routes:
            if not 'journey_id' in route or route['journey_id'] is None or route['journey_id'] == '':
                raise BadRequestException('route journey_id is missing')

            if not 'timestamp' in route or route['timestamp'] is None or route['timestamp'] == '':
                raise BadRequestException('route timestamp is missing')

            if not 'points' in route or route['points'] is None or route['points'] == '' or type(route['points']) is not list or len(route['points'])!=2:
                raise BadRequestException('route points are wrong, missing or incorrect length')

            if not 'mode' in route or route['mode'] is None or route['mode'] == '':
                raise BadRequestException('route mode is missing')

            if not 'speed' in route or route['speed'] is None or route['speed'] == '':
                raise BadRequestException('route speed is missing')
                
            sql = """INSERT INTO route (geometry, journey_id, timestamp, speed, mode, was_on_route)
                     VALUES (""" + "ST_GeomFromText('LINESTRING(%.10f %.10f, %.10f %.10f)', 4326)" % (float(route['points'][0][1]), 
                               float(route['points'][0][0]),
                               float(route['points'][1][1]),
                               float(route['points'][1][0])
                            ) + ", %s, %s, %s, %s, %s)"
            cursor.execute(sql, (route['journey_id'], 
                                 route['timestamp'], 
                                 float(route['speed']),
                                 "" if (not 'mode' in route or route['mode'] is None or route['mode'] == '') else route['mode'], 
                                 0 if (not 'was_on_route' in route or route['was_on_route'] is None or route['was_on_route'] == '') else 1
                                 ))
            self.connection.commit()
        # if 'trace_seq' in route:
          # self.saveTrace(cursor, trace_seq, route['journey_id'])
        return
    
    def getPlan(self, plan_id=''):
        if not plan_id:
            raise BadRequestException('plan_id cannot be empty')
        cursor = self.cursor()
        sql = """select plan_id, 
                        ST_AsGeoJSON(geometry) as geometry,
                        journey_id,
                        timestamp
                        from plan where plan_id = %s"""
        cursor.execute(sql, (plan_id,))
        plan = cursor.fetchone()        
        result={}
        if plan is not None:
            result['plan_id']=plan[0]
            result['geometry']=json.loads(plan[1])
            result['journey_id']=plan[2]
            result['timestamp']=plan[3].isoformat()
            plan=result
        return plan

    def getAverageSpeedsReport(self, boundary='', type='', planID='', after='', before=''):
        if len(boundary):
            boundary=boundary[0].split(",")
            boundary=[float(i) for i in boundary]
        if len(boundary)!=4:
            boundary=[]
        if type!='baseline':
            if type!='realtime':
                type='combined'

        cursor = self.cursor()
        
        sql = "SELECT ST_AsGeoJSON(geometry), speed FROM report WHERE type=%s AND timestamp > NOW() - INTERVAL '15 minutes' ORDER BY timestamp ASC"

        cursor.execute(sql, (type,))
        
        records = cursor.fetchall()
        if not len(records):
            records=self.buildAverageSpeedsReport(type)
            
        collection={
            "type": "FeatureCollection",
            "features": []
        }
        for record in records:
            collection['features'].append({
                'type': 'Feature',
                'geometry': json.loads(record[0]),
                'properties': {
                    'speed': float(record[1])
                }
            })            
        return collection
        
    def buildAverageSpeedsReport(self, type='realtime'):
        if type!='baseline':
            if type!='realtime':
                type='combined'
        
        min_length=250 # shorter segments will be grouped 
        
        cursor = self.cursor()

        speeds = {}
        
        # Clean up

        sql = "DELETE FROM report"
        if type == 'realtime':
            sql += " WHERE realtime=true"
        elif type == 'baseline':
            sql += " WHERE realtime=false"
        cursor.execute(sql)

        # Build average speed cache for routes
        
        sql = "SELECT ST_GeoHash(geometry, 30), AVG(speed) FROM route"
        if type == 'realtime':
            sql += " WHERE realtime=true"
        elif type == 'baseline':
            sql += " WHERE realtime=false"
        sql += " GROUP BY geometry"

        cursor.execute(sql)
        
        for record in cursor.fetchall():
            speeds[record[0]]=float(record[1])
            
        # Group raw routes into linestring geometries

        sql = "SELECT ST_AsGeoJSON((ST_Dump(ST_LineMerge(ST_Collect(route.geometry)))).geom)::json->'coordinates' FROM (SELECT DISTINCT geometry FROM route) AS route"
        
        cursor.execute(sql)    
        collection=[]
        for record in cursor.fetchall():
            linestring=json.loads(record[0])
            feature={
                "coordinates": [],
                "speed": 0,
                "speeds": [],
                "lengths": []
            }
            
            # run through each group to detect speed category change and exclude short routes
            for i, point in enumerate(linestring):
                # start bulding route segments upon reaching second linestring point
                if len(feature['coordinates'])>0: 
                    route=[]
                    route.append(ppygis.Point(linestring[i-1][0], linestring[i-1][1], linestring[i-1][2], srid=4326))
                    route.append(ppygis.Point(linestring[i][0], linestring[i][1], linestring[i][2], srid=4326))
                    route=ppygis.LineString(route, srid=4326)
                    cursor.execute("select ST_Length(ST_Transform(%s::geometry, 2839)), ST_GeoHash(%s::geometry, 30)",  (route, route))
                    record=cursor.fetchone()
                    length=record[0]
                    if record[1] in speeds:
                        speed=speeds[record[1]]
                    else:
                        speed=-1
                        
                    if len(feature['speeds']):
                        if self.categorizeSpeed(speed) != self.categorizeSpeed(feature['speeds'][-1]):
                            # make sure that non-trailing line segments shorter than 200m are combined together
                            if sum(feature['lengths']) >= min_length:
                                feature['speed']=float(sum(feature['speeds']))/len(feature['speeds'])
                                collection.append([copy.deepcopy(feature['coordinates']), feature['speed']])
                                # reset
                                feature['coordinates']=[feature['coordinates'][-1]]
                                feature['speed']=0
                                feature['lengths']=[]
                                feature['speeds']=[]                            
                        
                    feature['coordinates'].append([point[0], point[1], point[2]])
                    
                    feature['speeds'].append(speed)                    
                    feature['lengths'].append(length)                    
                    
                else:
                    feature['coordinates'].append([point[0], point[1], point[2]])
            
            feature['speed']=float(sum(feature['speeds']))/len(feature['speeds'])
            collection.append([copy.deepcopy(feature['coordinates']), feature['speed']])
                    
        now=datetime.datetime.fromtimestamp(time.time())
        for i, feature in enumerate(collection):            
            cursor.execute("INSERT INTO report (geometry, speed, type, timestamp) VALUES (ST_GeomFromGeoJSON(%s), %s, %s, %s)", 
                           (json.dumps({'type': 'LineString', 'coordinates': feature[0], 'crs': {'type':'name', 'properties': {'name': 'EPSG:4326'}}}), feature[1], type, now))
            collection[i][0]=json.dumps({'type': 'LineString', 'coordinates': feature[0]}) # just as the database would have returned it
            self.connection.commit()
                            
        return collection        
        
    def categorizeSpeed(self, speed):
        speed=speed*3.6
        if speed<=10:
            return 1
        if speed<=12:
            return 2
        if speed<=15:
            return 3
        if speed<=20:
            return 4
        if speed<=25:
            return 5
        if speed<=30:
            return 6
        if speed<=35:
            return 7
        if speed<=45:
            return 8
        if speed>45:
            return 9
        return -1

class ServerHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            parsed_path = urlparse.urlparse(self.path)        
            query_components = urlparse.parse_qs(parsed_path.query)
            match=re.compile("/plans/(?P<planID>[0-9]+)").match(parsed_path.path)
            if match and match.group('planID'):
                self.send_response_body(App().getPlan(int(match.group('planID'))))
            elif "/reports/speed-averages" == parsed_path.path:
                self.send_response_body(App().getAverageSpeedsReport(query_components['boundary'][0] if 'boundary' in query_components else "",
                                                                int(query_components['planID'][0]) if 'planID' in query_components else "",
                                                                int(query_components['after'][0]) if 'after' in query_components else "",
                                                                int(query_components['before'][0]) if 'before' in query_components else ""))
            elif "/" == parsed_path.path:
                self.send_response_body({"name": "MaaS API Server", "documentation": "https://github.com/okffi/sujuvuusnavigaattori-server", "version": "1.0"})
            else:
                self.send_error(404, "Not found")
        except BadRequestException as e:
            self.send_error(400, str(e))
        except Exception as e:
            self.send_error(500, str(e))
            raise
        except:
            self.send_error(500)
            raise
        return

    def do_POST(self):
        try:
            parsed_path = urlparse.urlparse(self.path)
            query_components = urlparse.parse_qs(parsed_path.query)
            length = int(self.headers.getheader('content-length'))
            post = self.rfile.read(int(length))
            if self.headers.getheader('Content-type').startswith('application/json'):
                data = json.loads(unicode(post.decode()))
            else:
                data=urlparse.parse_qs(post.decode())
                if 'payload' not in data:
                    raise BadRequestException('must use application/json or payload parameter to submit data')
                data = json.loads(unicode(data['payload'][0]))
            if "/plans" == parsed_path.path:
                self.send_response_body(App().savePlan(data))
            elif "/traces" == parsed_path.path:
                self.send_response_body(App().saveTraces(data))
            elif "/routes" == parsed_path.path:
                self.send_response_body(App().saveRoutes(data))
            else:
                self.send_error(404, "Not found")
        except BadRequestException as e:
            self.send_error(400, str(e))
        except Exception as e:
            self.send_error(500, str(e))
        except:
            self.send_error(500)
        return

    def do_OPTIONS(self):
        self.send_response(200, 'OK')
        self.send_cors_headers(True)
        self.end_headers()

    def send_cors_headers(self, options=False):
        if options==True:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Expose-Headers", "Access-Control-Allow-Origin")
            self.send_header("Access-Control-Allow-Headers", "Origin, X-Requested-With, Accept, Content-type, Accept-Timezone, *")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        else:        
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header("Access-Control-Allow-Origin", "*")
        
    def send_response_body(self, body):        
        if body is None or body=='':
            self.send_response(204, 'No Content')
            self.send_cors_headers()
            self.end_headers()
        else:
            self.send_response(200, 'OK')
            try:
                data=bytes(unicode(json.dumps(body)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self.send_error(500, str(e))
                raise
            except:
                self.send_error(500)
                raise

    def send_error(self, code, message=''):
        if code == 400:
            self.send_response(code, "Bad request")
        elif code == 404:
            self.send_response(code, "Not Found")
        elif code == 500:
            self.send_response(code, "Internal Server Error")
        else:
            self.send_response(code, "Generic error")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(bytes(unicode(json.dumps({"error": code, "description": message}))))

class ForkingHTTPServer(SocketServer.ForkingMixIn, BaseHTTPServer.HTTPServer):
    def finish_request(self, request, client_address):
        request.settimeout(600)
        # "super" can not be used because BaseServer is not created from object
        BaseHTTPServer.HTTPServer.finish_request(self, request, client_address)

def httpd(handler_class=ServerHandler, server_address=('localhost', 80)):
    print "MaaS API Server starting"
    try:
        srvr = ForkingHTTPServer(server_address, handler_class)
        srvr.serve_forever()  # serve_forever
    except KeyboardInterrupt:
        srvr.socket.close()

if __name__ == "__main__":
    if sys.argv[1:]:
        port = int(sys.argv[1])
    else:
        port = 80
    server_address = ('0.0.0.0', port)
    httpd(server_address=server_address)