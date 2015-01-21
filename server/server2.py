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

import geohash

from math import radians, cos, sin, asin, sqrt
#from random import randint

import psycopg2 as db

""" 

These are data type conversion rules between old and new schemas

ALTER TABLE traces
    ALTER COLUMN "speed" TYPE float8
        USING CAST("speed" as double precision)
    ALTER COLUMN "accuracy" TYPE float8
        USING CAST("accuracy" as double precision)
    ALTER COLUMN "aaccuracy" TYPE float8
        USING CAST("aaccuracy" as double precision)
    ALTER COLUMN "heading" TYPE float8
        USING CAST("heading" as double precision)
    ALTER COLUMN "altitude" TYPE float8
        USING CAST("altitude" as double precision);
    ALTER COLUMN "timestamp" TYPE timestamptz
        USING to_timestamp("timestamp", 'YYYY-MM-DD"T"HH24:MI:SS.USZ') at time zone 'UTC';
    ALTER COLUMN geometry TYPE geometry(POINT, 4326)
        USING ST_SetSRID(geometry,4326);

ALTER TABLE routes
    ALTER COLUMN geometry TYPE geometry(LINESTRING, 4326) 
        USING ST_SetSRID(geometry,4326);


A few fields needed to be renamed as well

"""
class BadRequestException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return self.value

class App():
    
    def cursor(self):
        self.connection=db.connect("dbname=sujuvuusnavigaattori")
        self.cursor=self.connection.cursor()
        return self.cursor
    
    def __exit__(self, type, value, traceback):
        self.connection.close()
        
    def savePlan(self, plan):
        
        raise Exception("Not implemented")
        cursor = self.cursor()
        
        
        sql = """INSERT INTO Plans (journey_id, geometry, timestamp)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
        cursor.execute(sql, (plan['journey_id'], max_walk_distance,
                             min_transfer_time, walk_speed, mode, timestamp))
        self.connection.commit()
        return

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

            sql = """INSERT INTO traces (geometry, journey_id, timestamp, speed, accuracy, altitude, altitude_accuracy, heading)
                     VALUES (""" + "ST_GeomFromText('POINT(%.10f %.10f)', 4326)" % (float(trace['longitude']), float(trace['latitude'])) + """, %s, %s, %s, %s, %s, %s, %s)"""

            cursor.execute(sql, (trace['journey_id'], 
                                 trace['timestamp'], 
                                 float(trace['speed']),
                                 0 if (not 'accuracy' in trace or trace['accuracy'] is None or trace['accuracy'] == '') else float(trace['accuracy']), 
                                 0 if (not 'altitude' in trace or trace['altitude'] is None or trace['altitude'] == '') else float(trace['altitude']), 
                                 0 if (not 'altitude_accuracy' in trace or trace['altitude_accuracy'] is None or trace['altitude_accuracy'] == '') else float(trace['altitude_accuracy']), 
                                 0 if (not 'heading' in trace or trace['heading'] is None or trace['heading'] == '') else float(trace['heading'])
                                 ))
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
                
            sql = """INSERT INTO Routes (geometry, journey_id, timestamp, speed, mode, was_on_route)
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
                        from plans where plan_id = %s"""
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

    def getAverageSpeedsReport(self, boundary='', planID='', after='', before=''):
        if len(boundary):
            boundary=boundary[0].split(",")
            boundary=[float(i) for i in boundary]
        if len(boundary)!=4:
            boundary=[]
            lengthLimit=250
        else:
            lengthLimit=haversine(boundary[0], boundary[1], boundary[2], boundary[3])/30

        cursor = self.cursor()

        sql = "select ST_asGeoJSON(geometry), avg(speed) from Routes group by geometry"
        cursor.execute(sql)
        routes = cursor.fetchall()
        if len(routes)==0:
            return null

        speeds={}
        
        for i, route in enumerate(routes):
            pointA=json.loads(route[0])["coordinates"][0]
            pointB=json.loads(route[0])["coordinates"][1]
            key=geohash.encode(pointA[0], pointA[1])+'/'+geohash.encode(pointB[0], pointB[1])
            if key in speeds:
                print "duplicate key. old speed: ", speeds[key], " new speed: ", route[1]
            speeds[key]=route[1]

        sql = "select ST_asGeoJSON(ST_LineMerge(ST_Union(geometry))) from (select DISTINCT geometry from Routes) as r"

        if len(boundary)==4:
            sql += " WHERE MBRContains(buildMBR(?,?,?,?), geometry)"
            cursor.execute(sql, (boundary[0], boundary[1], boundary[2], boundary[3]))
        else:
            cursor.execute(sql)
        routes = cursor.fetchone()
        if routes[0] is not None:
            routes=json.loads(routes[0])["coordinates"]
            street_vectors = []
            for i, route in enumerate(routes):
                length=0
                line=[]
                speed=[]
                for j, point in enumerate(route):
                    if j<len(route)-1:
                        nextpoint = route[j+1]
                        key=geohash.encode(point[0], point[1])+'/'+geohash.encode(nextpoint[0], nextpoint[1])
                        if key in speeds:
                            length += self.haversine(point[0], point[1], nextpoint[0], nextpoint[1])
                            line.append(point)
                            speed.append(speeds[key])
                            if length >= lengthLimit or j >= len(route)-2:
                                line.append(nextpoint)
                                # *3.6 is legacy, should be all m/s
                                if len(speed):
                                    street_vectors.append({"geometry": {"type": "LineString", "coordinates": line}, "speed": 3.6*sum(speed)/float(len(speed))})
                                else:
                                    street_vectors.append({"geometry": {"type": "LineString", "coordinates": line}, "speed": 0})
                                length=0
                                line=[]
                                speed=[]
                        else:
                            street_vectors.append({"geometry": {"type": "LineString", "coordinates": [point, nextpoint]}, "speed": 0})
                            print "segment missing in avgspeed cache ", point, nextpoint

                            #linestring ="LINESTRING("
                            #for k, point in enumerate(line):
                            #    linestring+='%.10f' % float(point[0]) + " " + '%.10f' % float(point[1])
                            #     if k < len(line)-1:
                            #         linestring+=", "
                            #linestring += ")"
                            #sql="select avg(speed), ST_asGeoJSON(ST_Simplify(geometryFromText('" + linestring +"'), " + str(simplify) + ")) from Routes where ST_Intersects(geometry, geometryFromText('" + linestring + "', 4326))"
                            #sql="select avg(speed) from Routes where ST_Intersects(geometry, geometryFromText('" + linestring + "', 4326))"
                            #cursor.execute(sql)
                            #result=cursor.fetchone()
                            #avg=result[0]
                            #geometry=result[1]
            return street_vectors
        return 

    def categorizeSpeed(self, speed):
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
        return 9

    def haversine(self, lon1, lat1, lon2, lat2):
        """
        Calculate the great circle distance between two points 
        on the earth (specified in decimal degrees)
        """
        # convert decimal degrees to radians 
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

        # haversine formula 
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a)) 

        # 6372800 is the radius of the Earth
        m = 6372800 * c
        return m 

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
                self.send_response({"name": "MaaS API Server", "documentation": "https://github.com/okffi/sujuvuusnavigaattori-server", "version": "1.0"})
            else:
                self.send_error(404, "Not found")
        except BadRequestException as e:
            self.send_error(400, str(e))
        except Exception as e:
            self.send_error(500, str(e))
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
            try:
                data = json.loads(unicode(post.decode()))
            except ValueError:
                # dict(parse_qsl()) makes it impossible to pass arrays into methods via regular POST
                # additional code to detect lists needs to be added for versatility
                data = dict(urlparse.parse_qsl(post.decode()))
            except:
                self.send_error(500)
            if "/plans" == parsed_path.path:
                self.send_response_body(App().savePlans(data))
            elif "/traces" == parsed_path.path:
                self.send_response_body(App().saveTraces(data))
            elif "/routes" == parsed_path.path:
                self.send_response_body(App().saveRoutes(data))
            else:
                self.send_error(404, "Not found")
        except BadRequestException as e:
            self.send_error(400, str(e))
            raise
        except Exception as e:
            self.send_error(500, str(e))
            raise
        except:
            self.send_error(500)
            raise
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
        request.settimeout(30)
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