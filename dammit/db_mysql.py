
# -*- coding: utf-8 -*-
import time
import MySQLdb
from MySQLdb import IntegrityError
from uri import URI
import db_cache, constants

def todatetime(dt):
    return time.strftime("%Y-%m-%d %H:%M:%S", dt.timetuple())

def reconnect(func):
    """
    Decorator - reconnect and retry if we
    get an OperationalError
    """
    def retry(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except MySQLdb.OperationalError, e:
            del self.db
            self.db = self._connect()
            return func(self, *args, **kwargs)
    return retry

class MySQL(object):
    """
    MySQL backend support
    
    >>> from datetime import datetime; now = datetime.now
    >>>
    >>> conf = {}
    >>> conf['db_name'] = 'urldammit_doctest'
    >>> m = MySQL(conf, dropfirst = True)
    >>> u = URI()
    >>> u.uri = 'http://local.ch/test1.html'
    >>> u.status = 200
    >>> u.created = now()
    >>> u.updated = now()
    >>> u.tags = ['foo','bar']
    >>> u.pairs = {'foo':'hello', 'bar':'world'}
    >>> m.insert(u)
    >>> u1 = m.load(u.id)
    >>> u1.uri == u.uri
    True
    >>> u1.tags == u.tags
    True
    >>> u1.pairs == u.pairs
    True
    >>> todatetime(u1.created) == todatetime(u.created)
    True
    >>> todatetime(u1.updated) == todatetime(u.updated)
    True
    >>> u1.tags = ['abc','xyz']
    >>> u1.pairs = {'foo':'goodbye', 'bar':'world!'}
    >>> m.update(u1)
    >>> u2 = m.load(u1.id)
    >>> u2.tags == u1.tags
    True
    >>> u2.pairs == u1.pairs
    True
    >>> m.delete(u2.id)
    >>> None == m.load(u2.id)
    True
    """    
    def __init__(self, config = None, dropfirst = False, bootstrap = True):
        self.config = self._default_config(config)
        if bootstrap:
            self.db = self._connect()
            self.bootstrap(dropfirst)
        else:
            self.db = self._connect(usedb = True)

    def fresh_connection(self):
        """
        Make sure we have a fresh connection for each request
        """
        return MySQL(config = self.config, bootstrap = False)

    @db_cache.load
    @reconnect
    def load(self, id):
        """
        Takes a SHA-1 id
        """
        cursor = self.db.cursor()

        sql = """SELECT
        uri, location, status, created, updated
        FROM urldammit_uris WHERE id = %s"""
        cursor.execute(sql, (id, ))
        row = cursor.fetchone()

        if not row:
            return None

        data = {}
        data['uri'] = None
        if isinstance(row[0], unicode):
            data['uri'] = row[0].encode('utf8')

        data['location'] = None
        if isinstance(row[1], unicode):
            data['location'] = row[1].encode('utf8')

        data['status'] = int(row[2])
        data['created'] = row[3]
        data['updated'] = row[4]

        data['tags'] = None
        sql = "SELECT tag FROM urldammit_tags WHERE id = %s"
        cursor.execute(sql, (id, ))
        rows = cursor.fetchall()
        for row in rows:
            if data['tags'] == None:
                data['tags'] = []
            data['tags'].append(row[0].encode('utf8'))

        data['pairs'] = None
        sql = "SELECT pair_key, pair_value FROM urldammit_pairs WHERE id = %s"
        cursor.execute(sql, (id, ))
        rows = cursor.fetchall()
        for row in rows:
            if data['pairs'] == None:
                data['pairs'] = dict()
            data['pairs'][row[0].encode('utf8')] = row[1].encode('utf8')

        return URI.load(data)

    @db_cache.insert
    @reconnect
    def insert(self, uri):
        """
        Takes a URI object
        """
        cursor = self.db.cursor()
        
        sql = """INSERT INTO urldammit_uris
        ( id, uri, created, location, status, updated )
        VALUES
        ( %s, %s, %s, %s, %s, %s )
        ON DUPLICATE KEY UPDATE
        location = %s, status = %s, updated = %s
        """

        create_date = todatetime(uri.created)
        update_date = todatetime(uri.updated)
        
        params = (
            uri.id, uri.uri, create_date,
            uri.location, uri.status, update_date
            )

        # Duplicate the UPDATE params
        params = params + params[3:]
        print "Got here: " + str(params)

        cursor.execute( sql, params )

        self._store_tags(cursor, uri, deletefirst = False)
        self._store_pairs(cursor, uri, deletefirst = False)

        self.db.commit()

    @db_cache.update
    @reconnect
    def update(self, uri):
        """
        Takes a URI object

        TODO: only update tags / pairs if changed
        """
        cursor = self.db.cursor()

        sql = """UPDATE urldammit_uris SET
        location = %s, status = %s, updated = %s
        WHERE id = %s"""

        params = (
            uri.location,
            uri.status,
            todatetime(uri.updated),
            uri.id
            )

        cursor.execute(sql, params)

        self._store_tags(cursor, uri)
        self._store_pairs(cursor, uri)
        
        self.db.commit()

    @db_cache.delete
    @reconnect
    def delete(self, id):
        """
        Takes a SHA-1 id
        """
        cursor = self.db.cursor()
        sql = "DELETE FROM urldammit_uris WHERE id = %s"
        cursor.execute(sql, (id, ))

        sql = "DELETE FROM urldammit_tags WHERE id = %s"
        cursor.execute(sql, (id, ))

        sql = "DELETE FROM urldammit_pairs WHERE id = %s"
        cursor.execute(sql, (id, ))

        self.db.commit()

    def bootstrap(self, dropfirst = False):
        """
        Setup the database, tables etc.
        """
        import warnings
        warnings.simplefilter('ignore')
        
        cursor = self.db.cursor()

        if dropfirst:
            sql = "DROP DATABASE IF EXISTS %s"\
                  % self.config['db_name']
            cursor.execute(sql)
        
        sql = "CREATE DATABASE IF NOT EXISTS %s"\
              % self.config['db_name']
        cursor.execute(sql)

        sql = "USE %s" % self.config['db_name']
        cursor.execute(sql)
        
        sql = """CREATE TABLE IF NOT EXISTS urldammit_uris (
            id BINARY( 40 ) NOT NULL ,
            uri VARCHAR( %s ) NOT NULL ,
            location VARCHAR( %s ) NULL ,
            status MEDIUMINT UNSIGNED NOT NULL ,
            created DATETIME NOT NULL ,
            updated DATETIME NOT NULL ,
            PRIMARY KEY ( id )
            ) ENGINE = innodb CHARACTER SET utf8 COLLATE utf8_unicode_ci;
            """ % ( constants.URI_LEN, constants.URI_LOCATION_LEN )
        cursor.execute(sql)

        sql = """CREATE TABLE IF NOT EXISTS urldammit_tags (
        id BINARY( 40 ) NOT NULL ,
        tag VARCHAR( %s ) NOT NULL ,
        KEY id_index (id)
        ) ENGINE = innodb CHARACTER SET utf8 COLLATE utf8_unicode_ci;
        """ % ( constants.URI_TAG_LEN )
        cursor.execute(sql)

        sql = """CREATE TABLE IF NOT EXISTS urldammit_pairs (
        id BINARY( 40 ) NOT NULL ,
        pair_key VARCHAR( %s ) NOT NULL ,
        pair_value VARCHAR( %s ) NOT NULL ,
        KEY id_index (id)
        ) ENGINE = innodb CHARACTER SET utf8 COLLATE utf8_unicode_ci;
        """ % ( constants.URI_PAIR_KEY_LEN, constants.URI_PAIR_VALUE_LEN )
        cursor.execute(sql)
        
        warnings.resetwarnings()

    def purge(self, **kwargs):
        """
        Clean up old data
        """
        pass

    def _default_config(self, config):
        if not config: config = {}
        
        config['db_host'] = config.get('db_host', 'localhost')
        config['db_user'] = config.get('db_user', 'urldammit')
        config['db_pass'] = config.get('db_pass', 'where1sMyUrl')
        config['db_name'] = config.get('db_name', 'urldammit_live')

        return config
        
    def _connect(self, usedb = False):
        if usedb:
            try:
                # This will fail on MySQL < 4.1
                db = MySQLdb.connect(
                    host = self.config['db_host'],
                    user = self.config['db_user'],
                    passwd = self.config['db_pass'],
                    db = self.config['db_name'],
                    charset='utf8',
                    use_unicode=1,
                    connect_timeout = 5,
                    init_command="set names utf8"
                    )
            except MySQLdb.OperationalError:
                db = MySQLdb.connect(
                    host = self.config['db_host'],
                    user = self.config['db_user'],
                    passwd = self.config['db_pass'],
                    db = self.config['db_name'],
                    connect_timeout = 5,
                    charset='utf8',
                    use_unicode=1
                    )
        else:
            # When bootstrapping, we may not yet have a
            # DB to use...
            try:
                # This will fail on MySQL < 4.1
                db = MySQLdb.connect(
                    host = self.config['db_host'],
                    user = self.config['db_user'],
                    passwd = self.config['db_pass'],
                    use_unicode=1,
                    connect_timeout = 5,
                    init_command="set names utf8"
                    )
            except MySQLdb.OperationalError:
                db = MySQLdb.connect(
                    host = self.config['db_host'],
                    user = self.config['db_user'],
                    passwd = self.config['db_pass'],
                    connect_timeout = 5,
                    use_unicode=1
                    )

        db.charset = 'utf8'
        return db

    def _store_tags(self, cursor, uri, deletefirst = True):
        if uri.tags_updated:
            if deletefirst:
                sql = "DELETE FROM urldammit_tags WHERE id = %s"
                cursor.execute(sql, (uri.id, ))
            
            sql = """INSERT INTO urldammit_tags
            ( id, tag ) VALUES ( %s, %s )"""

            for tag in uri.tags:
                cursor.execute(sql, (uri.id, tag))

    def _store_pairs(self, cursor, uri, deletefirst = True):
        if uri.pairs_updated:
            if deletefirst:
                sql = "DELETE FROM urldammit_pairs WHERE id = %s"
                cursor.execute(sql, (uri.id, ))
            
            sql = """INSERT INTO urldammit_pairs
            ( id, pair_key, pair_value )
            VALUES ( %s, %s, %s)"""

            for k, v in uri.pairs.items():
                cursor.execute(sql, (uri.id, k, v))        

def _test():
    import doctest
    doctest.testmod()


if __name__ == '__main__':
    _test()


