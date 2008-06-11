#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, datetime, sha, re

def Property(function):
    """
    object property decorator
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/410698
    """
    keys = 'fget', 'fset', 'fdel'
    func_locals = {'doc':function.__doc__}
    def probeFunc(frame, event, arg):
        if event == 'return':
            locals = frame.f_locals
            func_locals.update(dict((k,locals.get(k)) for k in keys))
            sys.settrace(None)
        return probeFunc
    sys.settrace(probeFunc)
    function()
    return property(**func_locals)

class URI(object):
    """
    Represents a URI we want to track
    """
    __slots__ = (
        '_id','_uri','_location','_status',
        '_created','_updated','_accessed',
        '_tags','_pairs'
        )

    def __init__(self):
        [setattr(self, slot, None) for slot in URI.__slots__]

    def hash(cls, uri):
        """
        Static method - takes a string and returns a SHA-1 hex digest
        
        >>> URI.hash("http://local.ch")
        'c909d39688beb7b00e4fd47788329a61b39f73d5'
        """
        return sha.new(uri).hexdigest()
    hash = classmethod(hash)

    @Property
    def id():
        """
        SHA-1 hash of the URI - read only - set via setting uri property
        
        >>> u = URI()
        >>> u.id == None
        True
        """
        def fget(self):
            return self._id

    @Property
    def uri():
        """
        The URI we want to track
        
        >>> u = URI()
        >>> u.uri = "http://local.ch"
        >>> u.id == URI.hash(u.uri)
        True
        >>> u.uri = "http://local.ch/new"
        Traceback (most recent call last):
        AttributeError: property 'uri' is immutable
        """
        def fget(self):
            return self._uri
        
        def fset(self, url):
            url = str(url)
            if self._uri:
                raise AttributeError("property 'uri' is immutable")
            self._uri = url
            self._id = URI.hash(url)

    @Property
    def location():
        """
        the current location of this uri - nothing
        if it's new but the new uri if it's been
        moved
        >>> u = URI()
        >>> u.status = 200
        >>> u.location = "http://local.ch/new"
        Traceback (most recent call last):
        AttributeError: Cannot set property location unless status is 301 (not 200)
        >>> u.status = 301
        >>> u.location = "http://local.ch/new"
        >>> u.location == "http://local.ch/new"
        True
        """
        def fget(self):
            return self._location

        def fset(self, locn):
            if not self._status == 301:
                raise AttributeError(
                    "Cannot set property location unless status is 301 (not %s)" %\
                    self._status
                    )
            self._location = str(locn)

    @Property
    def status():
        """
        Current HTTP status attached to this URI
        
        >>> u = URI()
        >>> u.status = 404
        Traceback (most recent call last):
        ValueError: New URIs must begin at status '200' not '404'
        >>> u.status = 200
        >>> u.status
        200
        >>> u.status = 500
        Traceback (most recent call last):
        ValueError: Status 500 not supported
        >>> u.status = 404
        >>> u.status
        404
        >>> u.status = 200
        Traceback (most recent call last):
        ValueError: Current status is '404' - cannot change to '200'
        >>> u.status = 301
        >>> u.status
        301
        >>> u.status = 404
        Traceback (most recent call last):
        ValueError: Current status is '301' - cannot change to '404'
        """
        def fget(self):
            return self._status
        
        statuses = {
            200:(200, 301, 404),
            301:(301,),
            404:(301, 404)
            }

        def fset(self, code):
            
            code = int(code)
            
            if not code in statuses:
                raise ValueError("Status %s not supported" % code)

            if self._status in statuses:
                if not code in statuses[self._status]:
                    raise ValueError(
                        "Current status is '%s' - cannot change to '%s'" % (self._status, code)
                        )

            if not self._status and code != 200:
                raise ValueError("New URIs must begin at status '200' not '%s'" % code)
            
            self._status = code
        

    @Property
    def created():
        """
        Creation time - can only be set once
        
        >>> u = URI()
        >>> u.created = "foo"
        Traceback (most recent call last):
        TypeError: Expecting datetime.datetime not <type 'str'>
        >>> u.created = datetime.datetime.now()
        >>> type(u.created)
        <type 'datetime.datetime'>
        >>> u.created = datetime.datetime.now()
        Traceback (most recent call last):
        AttributeError: property 'created' is immutable
        """
        def fget(self):
            return self._created

        def fset(self, time):
            
            if self._created:
                raise AttributeError("property 'created' is immutable")
            
            if not type(time) == datetime.datetime:
                raise TypeError("Expecting datetime.datetime not %s" % type(time))
            
            self._created = time

    @Property
    def updated():
        """
        Time of last change
        
        >>> u = URI()
        >>> u.updated = "foo"
        Traceback (most recent call last):
        TypeError: Expecting datetime.datetime not <type 'str'>
        >>> u.updated = datetime.datetime.now()
        >>> type(u.updated)
        <type 'datetime.datetime'>
        """
        def fget(self):
            return self._updated

        def fset(self, time):
            if not type(time) == datetime.datetime:
                raise TypeError("Expecting datetime.datetime not %s" % type(time))
            self._updated = time

    validtag = re.compile("^[a-zA-Z0-9]{1,20}$")
    @Property
    def tags():
        """
        List of tags associated with this URI.
        Each tag must obey =~ /^[a-zA-Z0-9]{1,20}$/
        
        >>> u = URI()
        >>> u.tags = "foo"
        Traceback (most recent call last):
        AttributeError: Can only modify tags while status is 200 (not None)
        >>> u.status = 200
        >>> u.tags = "foo"
        Traceback (most recent call last):
        TypeError: tags must be a list not <type 'str'>
        >>> u.tags = ['foo', 'bar']
        >>> u.tags
        ['foo', 'bar']
        >>> u.tags = ['1+1']
        Traceback (most recent call last):
        ValueError: Invalid tag '1+1'
        """
        def fget(self):
            return self._tags

        def fset(self, keywords):
            if self._status != 200:
                raise AttributeError("Can only modify tags while status is 200 (not %s)" % self._status)
            if not type(keywords) == list:
                raise TypeError("tags must be a list not %s" % type(keywords))
            for tag in keywords:
                if not type(tag) == str:
                    raise TypeError("Tag '%s' must be a string not %s" % (tag, type(tag)))
                if not URI.validtag.match(tag):
                    raise ValueError("Invalid tag '%s'" % tag)
            
            self._tags = keywords

    @Property
    def pairs():
        """
        Key value pairs to associate with the URI.
        Keys must obey =~ /^[a-zA-Z0-9]{1,20}$/
        Values must be strings, not be longer than 100 bytes
        >>> u = URI()
        >>> u.pairs = "foo"
        Traceback (most recent call last):
        AttributeError: Can only modify pairs while status is 200 (not None)
        >>> u.status = 200
        >>> u.pairs = "foo"
        Traceback (most recent call last):
        TypeError: pairs must be a dictionary not <type 'str'>
        >>> u.pairs = {1:'x'}
        Traceback (most recent call last):
        TypeError: Key '1' must be a string not <type 'str'>
        >>> u.pairs = {'1+1':'x'}
        Traceback (most recent call last):
        ValueError: Invalid key '1+1'
        >>> u.pairs = {'x':1}
        Traceback (most recent call last):
        TypeError: Value for key 'x' must be a string not <type 'int'>
        >>> u.pairs = {'x':'1'}
        >>> u.pairs['x']
        '1'
        """
        def fget(self):
            return self._pairs

        def fset(self, mapping):
            if self._status != 200:
                raise AttributeError("Can only modify pairs while status is 200 (not %s)" % self._status)

            if not type(mapping) == dict:
                raise TypeError("pairs must be a dictionary not %s" % type(mapping))

            for k, v in mapping.items():
                if not type(k) == str:
                    raise TypeError("Key '%s' must be a string not %s" % (k, type(v)))
                if not URI.validtag.match(k):
                    raise ValueError("Invalid key '%s'" % k)
                if not type(v) == str:
                    raise TypeError("Value for key '%s' must be a string not %s" % (k, type(v)))
                if len(v) > 100:
                    raise ValueError("Value for key '%s' too large at %s bytes" % (k, len(v)))
                                     
            self._pairs = mapping

    def is_found(self):
        """
        Whether this is a HTTP status 200 resource

        >>> u = URI()
        >>> u.status = 200
        >>> u.is_found()
        True
        >>> u.status = 404
        >>> u.is_found()
        False
        """
        return 200 <= self.status < 300

    def is_notfound(self):
        """
        Whether this is a HTTP status 404 resource

        >>> u = URI()
        >>> u.status = 200
        >>> u.status = 404
        >>> u.is_notfound()
        True
        >>> u = URI()
        >>> u.status = 200
        >>> u.is_notfound()
        False
        """
        return 400 <= self.status < 500

    def is_redirected(self):
        """
        Whether this is a HTTP status 301

        >>> u = URI()
        >>> u.status = 200
        >>> u.status = 301
        >>> u.status
        301
        >>> u.is_redirected()
        True
        >>> u = URI()
        >>> u.status = 200
        >>> u.is_redirected()
        False
        """
        return 300 <= self.status < 400

class GuardedURI(URI):
    """
    Prevents setting status 301 or 404 or the location. Intended for use
    where the client cannot be trusted e.g. Javascript client to
    urldammit - we restrict their powers

    >>> u = GuardedURI()
    >>> u.uri = "http://local.ch"
    >>> u.id == URI.hash(u.uri)
    True
    """
    @Property
    def location():
        """
        the current location of this uri - nothing
        if it's new but the new uri if it's been
        moved.
        >>> u = GuardedURI()
        >>> u.location = "http://local.ch/new"
        Traceback (most recent call last):
        AttributeError: can't set attribute
        >>> u.location == "http://local.ch/new"
        False
        """
        def fget(self):
            return self._location

    @Property
    def status():
        """
        Current HTTP status attached to this URI
        >>> u = GuardedURI()
        >>> u.status = 200
        >>> u.status
        200
        >>> u.status = 404
        Traceback (most recent call last):
        ValueError: Status 404 not supported
        """
        def fget(self):
            return self._status

        def fset(self, code):
            
            code = int(code)
            
            if not code == 200:
                raise ValueError("Status %s not supported" % code)

            self._status = code

def URIManager(object):

    def __init__(self, db):
        self.db = db

    def load(self, id):
        return self.db.load(id)

    def register(self, uri, status = 200, **kwargs):

        id = URI.hash(uri)

        logging.debug("Looking for URI '%s' with id %s" % ( uri, id ))
        
        u = self.db.load(id)

        if u:
            logging.debug("Found URI %s [%s]" % (u.uri, u.id))
            
            if u.is_redirected():
                logging.warn("URI %s is redirected to %s - i.e. it's immutable" % (u.uri, u.location))
                return u

        else:
            if 200 <= status < 300:
                u = URI()
            else:
                logging.warn("Nothing known about %s - status is %s - ignoring" % (uri, status))
                return False
        
        kwargs['status'] = status
        allowedargs = ('status', 'uri', 'location', 'tags', 'pairs')

        now = datetime.now()
        updated = False

        for k, v in kwargs.items():
            if not k in allowedargs:
                continue
            try:
                if not equal(getattr(u, k), v):
                    setattr(u, k, v)
                    updated = True
            except Exception, e:
                logging.debug(e)

        if not u.updated or updated:
            u.updated = now

        if not u.created:
            u.created = now
            
        return u

def equal(a, b):
    """
    equality to handle quirks of python-couchdb Document
    objects
    """
    logging.debug("Comparing %s with %s" % ( a, b ))
    if type(a) == list:
        return tuple(sorted(a)) == tuple(sorted(b))
    if type(a) == dict:
        return tuple([(k, a[k]) for k in sorted(a.keys())])\
               == tuple([(k, b[k]) for k in sorted(b.keys())])
    return a == b


def _test():
    import doctest
    doctest.testmod()


if __name__ == '__main__':
    _test()