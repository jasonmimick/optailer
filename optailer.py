#!/usr/bin/env python

# optailer.py - manage db local copies of oplog data

import sys,time,os
import signal
import argparse
import pymongo
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
        self.stdout_path = os.path.abspath(self.config['logfile'])
        self.stderr_path = os.path.abspath(self.config['logfile'])
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
        namespaces = self.config['namespaces'].split(',')
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
        local_db = connection['local']
        db = connection[db_name]
        query = { "ns" : ns }

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

        self.logger.info(query)
        #start tailable cursor
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
                    doc = oplog.next()
                    self.vprint(doc)
                    wr = db[local_oplog].insert(doc)
                    self.vprint(vars(wr))       # TODO: Check write result!
                    self.vprint("Inserted into " + local_oplog)
            except StopIteration:   #thrown when out of data so wait a little
                self.vprint("sleep")
                time.sleep(self.config['tailSleepTimeSeconds'])

    def cleanup(self):
        if self.stop_called:
            return
        self.stop_called = True
        self.logger.info("cleanup")
        self.stop_requested = True
        time.sleep(5)       # sleep to let tailing thread cleanup
        self.logger.info("cleanup complete")

config_file = sys.argv[2]
if not os.path.isfile( config_file ):
    print "config file '",config_file," not found"
    sys.exit(1)

config = yaml.safe_load(open( config_file ))
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
