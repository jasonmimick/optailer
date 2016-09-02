#!/usr/bin/env python

# optailer.py - manage db local copies of oplog data

import sys,time,os
import signal
import argparse
import pymongo
import bson
import datetime
from pymongo import MongoClient, CursorType
#from bson import TimeStamp
from threading import Thread
import logging
import yaml
from daemon import runner
import atexit

class App():

    def __init__(self,config,logger):
        self.stop_called = False
        self.stop_requested = False
        self.config = config
        self.logger = logger
        self.stdin_path = '/dev/null'
        pf =  os.path.abspath(self.config['pidfile'])
        self.pidfile_path = pf
        self.pidfile_timeout = 3
        self.vprint("__init__")
        #self.stdout_path = os.path.abspath(self.config['logfile'])
        #self.stderr_path = os.path.abspath(self.config['logfile'])
        self.stdout_path = os.path.abspath('./op.out')
        self.stderr_path = os.path.abspath('./op.err')
        self.logger.debug("optailer initialized for operation " + sys.argv[1])

    def run(self):
        self.logger.info("optailer run called")
        self.tail()


    # verbose print message only if args.verbose=True
    def vprint(self,message):
        if self.config['verbose']==True:
            logger.debug(message)

    def tail(self):
        self.logger.info("optailer tail")
        namespaces = self.config['namespaces'].keys()
        self.logger.info("namespaces to tail: " + ", ".join(namespaces))

        threads = []
        for namespace in namespaces:
            db_name,coll_name = namespace.split('.')
            t = Thread(target=self.tail_ns, args=(db_name,coll_name))
            t.setDaemon(True)
            threads.append(t)

        [t.start() for t in threads]
        while True:
             threads = [t.join(20) for t in threads if t is not None and t.isAlive()]
        self.vprint("main thread ending>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

    def tail_ns(self,db_name,coll_name):
        # connect up to mongodb
        ns = db_name + '.' + coll_name
        local_oplog = 'oplog.' + coll_name
        connection = pymongo.MongoClient(self.config['mongodb'])
        mode = self.config['mode']
        if mode == 'stream':
            if self.config['sinkMongodb']:
                sinkConnection = pymongo.MongoClient( self.config['sinkMongodb'] )
                if self.config['namespaces'][ns]:
                    sinkNS = self.config['namespaces'][ns]
                else:
                    self.logger.error("mode is 'stream' but no mapping for namespace="+ns);
                    return
            else:
                self.logger.error("mode is 'stream' but no 'sinkMongodb' setting found in config file")
                return
        else:
            sinkConnection = connection
            sinkNS= db_name + "." + local_oplog
        db = connection[db_name]
        local_db = connection['local']
        query = { "ns" : ns }
        self.logger.info(query);
        if mode == 'local':
            self.logger.info("mode=local");
            if local_oplog in db.collection_names():
                try:
                    last_local_oplog_entry = db[local_oplog].find({}).sort("ts",-1).limit(1).next()
                    query["ts"]={ "$gt" : last_local_oplog_entry['ts'] }
                except StopIteration:   #thrown when out of data so wait a little
                    self.vprint(db_name+"."+local_oplog+' exists, but no entries found')
            else:
                size_bytes = self.config['local_oplog_size_megabytes']*1024*1024
                self.logger.info(db_name+"."+local_oplog+' not found, attempting to create size='+str(size_bytes)+' bytes')
                db.create_collection(local_oplog,capped=True,size=size_bytes)
        if mode == 'stream':
            self.logger.info("stream mode")
            query['ts']={ "$gt" : bson.timestamp.Timestamp(datetime.datetime.now(),0) }
        self.logger.info("after query set")
        #start tailable cursor
        self.logger.info(connection)
        oplog = connection['local']['oplog.rs'].find(query,cursor_type = CursorType.TAILABLE_AWAIT)
        if 'ts' in query:
            oplog.add_option(8)     # oplogReplay
        while oplog.alive:
            try:
                if self.stop_requested:
                    self.logger.info("Tail for " + local_oplog + " stopping.")
                    oplog.close()
                    break
                else:
                    self.vprint("gonna get next() from oplog")
                    doc = oplog.next()
                    self.vprint(doc)
                    self.logger.info("xxx")
                    self.try_insert(sinkConnection,sinkNS,doc)
            except StopIteration:   #thrown when out of data so wait a little
                self.vprint("sleep")
                time.sleep(self.config['tailSleepTimeSeconds'])

    def try_insert(self,connection,ns, doc):
        db, coll_name = ns.split('.')
        for i in range(5):
            try:
                wr = connection[db][coll_name].insert_one(doc)
                self.vprint(dir(wr))       # TODO: Check write result!
                self.vprint("Inserted into " + coll_name)
                return
            except pymongo.errors.AutoReconnect:
                self.logger.error("AutoReconnect error, try #" + str(i))
                time.sleep(pow(2, i))

        # if here, then we failed 5 times - log fatal error
        self.logger.critical("Unable to insert target MongoDB: " + connection)
        self.logger.critical("Unable to insert document into " + ns + " - MongoDB unavailable?")
        raise Exception("Unable to insert into MongoDB")

    def cleanup(self):
        if self.stop_called:
            return
        self.stop_called = True
        self.logger.info("cleanup starting")
        self.stop_requested = True
        time.sleep(5)       # sleep to let tailing thread cleanup
        self.logger.info("cleanup complete - optailer shutting down.")

print(sys.argv)
config_file = sys.argv[2]
if not os.path.isfile( config_file ):
    print "config file '",config_file," not found"
    sys.exit(1)

config = yaml.safe_load(open( config_file ))
print config
logger = logging.getLogger("optailer")
logger.setLevel(getattr(logging,config.get('loglevel','INFO').upper()))
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler = logging.FileHandler(os.path.abspath(config['logfile']))
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.info("log level set to " + logging.getLevelName(logger.getEffectiveLevel()))
app = App(config,logger)
if not sys.argv[1]=='stop':
    atexit.register(app.cleanup)

daemon_runner = runner.DaemonRunner(app)
#This ensures that the logger file handle does not get closed during daemonization
daemon_runner.daemon_context.files_preserve=[handler.stream]
daemon_runner.do_action()
