import sqlite3
import os
# from datetime import datetime
from dateutil import parser

SCHEMA_VERSION = 3


class Db(object):
    def __init__(self, db_file):
        """
        Lets get started.
        
        :param db_file: 
        """
        self.db_file = db_file
        self.conn = get_db_conn(db_file)

    def get_orbit_proctime(self, facility, granule):
        """
        docstring
        :param facility: 
        :param granule: 
        :return: 
        """
        q = self.conn.execute('''SELECT MAX(proc_date) FROM sighting 
                                 WHERE orbit = ? AND success = ? AND source = ?''',
                              (granule.orbit, True, facility))
        r = q.fetchone()
        if r is None or r[0] is None:
            return None
        else:
            # parse value, SQLITE type conversion doesn't seem to work with MAX
            return parser.parse(r[0])

    def get_granule_proctime(self, facility, granule):
        """
        Find the most recent proctime for a given channel, reguardless of band.
        
        :param facility: 
        :param granule: 
        :return: 
        """
        q = self.conn.execute('''SELECT MAX(proc_date) FROM sighting 
                                 WHERE granule_date = ? AND success = ? AND source = ?''',
                              (granule.start, True, facility))
        r = q.fetchone()
        if r is None or r[0] is None:
            return None
        else:
            # parse value, SQLITE type conversion doesn't seem to work with MAX
            return parser.parse(r[0])

    def get_orbit_granule_count(self, orbit, facility):
        q = self.conn.execute('''SELECT count(*) FROM 
                                (SELECT DISTINCT granule_date FROM sighting 
                                WHERE orbit = ? AND source = ?)''', (orbit, facility))
        r = q.fetchone()
        if r is None:
            return None
        else:
            return r[0]

    def insert_obs(self, facility, granule, sight_date, success):
        """
        
        :param facility: 
        :param granule: 
        :param sight_date: 
        :param success: 
        :return: 
        """

        sql = '''SELECT count FROM sighting 
                 WHERE source = ? AND granule_date = ? 
                 AND granule_channel = ? AND proc_date = ?'''
        q = self.conn.execute(sql, (facility, granule.start, granule.channel, granule.proc_date))
        r = q.fetchone()
        if r is None:
            sql = '''INSERT INTO sighting 
                     (source, granule_date, granule_channel, orbit, sight_date, 
                      proc_date, count, success) 
                      VALUES (?, ?, ?, ?, ?, ?, 1, ?)'''
            self.conn.execute(sql, (facility, granule.start, granule.channel, granule.orbit,
                                    sight_date, granule.proc_date, success))
        else:
            sql = '''UPDATE sighting set count = ?, success = ? 
                     WHERE source = ? AND granule_date = ? and granule_channel = ? and proc_date = ?'''
            self.conn.execute(sql, (r[0] + 1, success, facility, granule.start,
                                    granule.channel, granule.proc_date))

        self.conn.commit()

    def get_proc_count(self, granule, facility):
        q = self.conn.execute('SELECT COUNT(*) FROM sighting WHERE granule_date = ?' +
                              ' AND granule_channel = ? AND success = ? AND source = ?',
                              (granule.start, granule.channel, True, facility))

        return q.fetchone()[0]

    def close(self):
        self.conn.close()


def get_db_conn(db_dir):
    """
    Connect to a sqlite3 database file. Create the database if needed. 
    Not using foreign key constraints to maximize compatibility.
    :param db_dir: The database file to connect to 
    :return: The connection object
    """

    try:
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
    except OSError as e:
            pass

    db_file = os.path.join(db_dir, 'viirs-v%d.db' % SCHEMA_VERSION)
    conn = sqlite3.connect(db_file, detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS sighting (
                    source text,
                    granule_date timestamp, 
                    granule_channel text,
                    proc_date timestamp,
                    orbit int,
                    sight_date timestamp, 
                    count int,
                    success int,
                    PRIMARY KEY (source, granule_date, granule_channel, proc_date));''')

    conn.commit()

    return conn
