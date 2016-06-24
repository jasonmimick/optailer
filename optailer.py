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

class App():

    def __init__(self,config,logger):
        self.config = config
        self.logger = logger
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/tty'
        self.stderr_path = '/dev/tty'
        pf =  os.path.abspath(self.config['pidfile'])
        print "pf="+pf
        self.pidfile_path = pf
        self.pidfile_timeout = 3
        self.vprint("__init__")
        _base_path = os.getcwd()
        self.stdout_path = os.path.join(_base_path, "op.myapp.out") # Can also be /dev/null
        self.stderr_path =  os.path.join(_base_path, "op.myapp.err") # Can also be /dev/null
        self.pidfile_path =  os.path.join(_base_path, "op.myapp.pid")
        self.logger.info("optailer initialized")

    def run(self):
        print "run"
        self.logger.info("optailer run")
        #while True:
        self.vprint("run")
        self.tail()


    # verbose print message only if args.verbose=True
    def vprint(self,message):
        logger.debug(message)
        if self.config['verbose']==True:
            logger.debug(message)

    def tail(self):
        self.logger.info("optailer tail")
        self.vprint("tail")
        namespaces = self.config['namespaces'].split(',')
        self.vprint(namespaces)
        # TODO: Should fire off a separate thread for each namespace we wish to
        # monitor, then we can check if there already is a local oplog and filter
        # for entries which are newer than the last entry we have

        threads = []
        for namespace in namespaces:
            db_name,coll_name = namespace.split('.')
            t = Thread(target=self.tail_ns, args=(db_name,coll_name))
            t.setDaemon(True)
            threads.append(t)
            #t.start()
        #for t in threads:
        #    self.vprint('Joining ' + str(t),args)
        #    t.join()
        [t.start() for t in threads]
        while True:
             threads = [t.join(20) for t in threads if t is not None and t.isAlive()]
        self.vprint("tail ending>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")




    def tail_ns(self,db_name,coll_name):
        # connect up to mongodb
        ns = db_name + '.' + coll_name
        local_oplog = 'oplog.' + coll_name
        connection = pymongo.MongoClient(self.config['mongodb'])
        local_db = connection['local']
        db = connection[db_name]
        query = { "ns" : ns }

        if 'oplog.'+coll_name in db.collection_names():
            try:
                last_local_oplog_entry = db[local_oplog].find({}).sort("ts",-1).limit(1).next()
                query["ts"]={ "$gt" : last_local_oplog_entry['ts'] }
            except StopIteration:   #thrown when out of data so wait a little
                self.vprint(db_name+"."+local_oplog+' exists, but no entries found')
        else:
            size_bytes = self.config['local_oplog_size_megabytes']*1024*1024
            self.vprint(db_name+"."+local_oplog+' not found, attempting to create size='+str(size_bytes)+' bytes')
            db.create_collection(local_oplog,capped=True,size=size_bytes)

        self.vprint(query)
        #start tailable cursor
        oplog = connection['local']['oplog.rs'].find(query,cursor_type = CursorType.TAILABLE_AWAIT)
        if 'ts' in query:
            oplog.add_option(8)     # oplogReplay
        while oplog.alive:
            try:
                doc = oplog.next()
                self.vprint(doc)
                db[local_oplog].insert(doc)
                self.vprint("Inserted into " + local_oplog)
            except StopIteration:   #thrown when out of data so wait a little
                self.vprint("sleep")
                time.sleep(self.config['tailSleepTimeSeconds'])
            #finally:
            #    oplog.close()


#parser = argparse.ArgumentParser(description="Manage db local versions of the oplog")
#requiredArgs = parser.add_argument_group('required named arguments')
#requiredArgs.add_argument("--config"
#        ,help='yaml formatted config file for optailer, e.g. /etc/optailer.conf'
#        ,default="/etc/optailer.conf"
#        ,required=True)
#parser.add_argument("start",nargs='?',help='start tailing')
#parser.add_argument("stop",nargs='?',help='stop tailing')
#parsed_args = parser.parse_args()

#config = yaml.safe_load(open( parsed_args.config ))
config = yaml.safe_load(open( './optailer.conf' ))


logger = logging.getLogger("optailer")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler = logging.FileHandler(os.path.abspath(config['logfile']))

handler.setFormatter(formatter)
logger.addHandler(handler)
logger.info("Hello optailer!")
app = App(config,logger)
daemon_runner = runner.DaemonRunner(app)
#This ensures that the logger file handle does not get closed during daemonization
daemon_runner.daemon_context.files_preserve=[handler.stream]
print str(daemon_runner)
daemon_runner.do_action()
