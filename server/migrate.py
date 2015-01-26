import sys

import psycopg2 as db
import ppygis

from pyspatialite import dbapi2 as spatialite

class App():
    
    def cursor(self):
        self.connection=db.connect("dbname=sujuvuusnavigaattori")
        self.cursor=self.connection.cursor()
        return self.cursor
    
    def __exit__(self, type, value, traceback):
        self.connection.close()

    def migrate(self):

        from_conn = spatialite.connect('navirec.sqlite')
        from_cursor = from_conn.cursor()
        to_cursor = self.cursor()
        
        # traces

        print "Migrating traces"

        sql = "select session_id, X(geom) as longitude, Y(geom) as latitude, altitude, timestamp from Traces"
        from_cursor.execute(sql)
        traces = from_cursor.fetchall()
        if traces is not None and len(traces) > 0:
            for trace in traces:
                journey_id = trace[0]
                longitude = trace[1]
                latitude = trace[2]
                altitude = trace[3]
                timestamp = trace[4]
                if altitude is None:
                    altitude = 0
                to_cursor.execute("SELECT * FROM trace WHERE journey_id=%s AND timestamp=%s AND ST_Equals(geometry, %s)", (journey_id, timestamp, ppygis.Point(longitude, latitude, altitude, srid=4326)));
                matching_traces=to_cursor.fetchall()
                if len(matching_traces)==0:
                    sys.stdout.write('.')
                    to_cursor.execute("INSERT INTO trace (journey_id, timestamp, geometry) VALUES  (%s, %s, %s)", (journey_id, timestamp, ppygis.Point(longitude, latitude, altitude, srid=4326)))
                else:
                    sys.stdout.write('!')

        # routes
        
        print "Migrating routes"

        sql = "select session_id, X(PointN(geom, 1)) as longitude1, Y(PointN(geom, 1)) as latitude1, X(PointN(geom, 2)) as longitude2, Y(PointN(geom, 2)) as latitude2, timestamp, speed, mode from Routes"
        from_cursor.execute(sql)
        routes = from_cursor.fetchall()
        if routes is not None and len(routes) > 0:
            for route in routes:
                journey_id = route[0]
                longitude1 = route[1]
                latitude1 = route[2]
                longitude2 = route[3]
                latitude2 = route[4]
                timestamp = route[5]
                speed = route[6] / 3.6
                mode = route[7]
                altitude = 0
                point1 = ppygis.Point(longitude1, latitude1, altitude, srid=4326)
                point2 = ppygis.Point(longitude2, latitude2, altitude, srid=4326)
                line = ppygis.LineString((point1, point2), srid=4326)
                to_cursor.execute("SELECT * FROM route WHERE journey_id=%s AND timestamp=%s AND ST_Equals(geometry, %s)", (journey_id, timestamp, line));
                matching_routes=to_cursor.fetchall()
                if len(matching_routes)==0:
                    sys.stdout.write('.')
                    to_cursor.execute("INSERT INTO route (journey_id, timestamp, geometry, speed, mode) VALUES  (%s, %s, %s, %s, %s)", (journey_id, timestamp, line, speed, mode))
                else:
                    sys.stdout.write('!')

        self.connection.commit()
        from_conn.close()
        return

if __name__ == "__main__":
    App().migrate()