optailer
========

``optailer`` is a MongoDB tool which exposes oplog data.

Well configured MongoDB systems have authentication enabled. Typically, each application using a cluster will have ``readWrite`` permissions on a particular database, but not have any visibility into other databases. This presents a challenge when those applications wish to leverage the ability to monitor all the operations occurring, which is usually done by tailing the oplog. The problem is that there is only one oplog (in the ```local``` database) and it contains all the operations for the entire MongoDB instance. Security restrictions inhibit allowing all applications to read this data.

``optailer`` solves this issue, by writing a database "local" version of the oplog which is only then accessible by users with read access on their database.

Other tools, such as the [mongo-connector](https://github.com/mongodb-labs/mongo-connector), provide similar functionality. ``optailer`` also adds a linux-level service wrapper to facilitate operations.

## Design

Each collection defined in the ```namespaces``` property of ```optailer```'s configuration file is monitored by a separate thread. Each monitoring thread starts a tailable cursor on the oplog looking for entries for it's namespace. When entries are found they are written to a capped collection in the target namespaces' database. For example, if you wanted to monitor entries for the ```test.foo.bar``` collection, they would appear in ```test.oplog.foo.bar```. The word "oplog" is prepended to the name of the target collection.

## Installation

Install requirements (*Note:* ``python-daemon`` only required if running < Python 2.7)

```
$sudo pip install pymongo
$sudo pip install python-daemon
```

Download

```
git clone https://github.com/jasonmimick/optailer
```

The repo contains some test scripts, at minimum you need, optailer.py, optailer, and optailer.conf.

Edit configuration file. See [configuration-options](Configuration Options).

Optionally, you can move files into the ```/etc/init.d``` filesystem. One way to do this:

```
$cp ./optailer.py /etc
$cp ./optailer.conf /etc
$cp ./optailer /etc/init.d
```
Then edit ```/etc/optailer``` and make sure the ```OPTAILER``` and ```CONFIG``` variables point
to the correct locations.

## Usage

Assuming the optional step 4 above was followed, to run optailer as a background 'service':

```$/etc/init.d/optailer start```

To stop:

```$/etc/init.d/optailer stop```

Tail the optailer log file to view activity.

If you wish to be able to independently start/stop monitoring for different collections, then you can run multiple instances of the service, each with it's own configuration file.

## Configuration Options

```
mongodb: <connection string>
namespaces: <comma delimited list of namespaces to tail - for example, test.foo,foo.bar,test.foobar
logfile: <full path and name of log file>
loglevel: <loglevel, standard Python loglevels>
verbose: <true|false>
local_oplog_size_megabytes: <size of local oplog collections, e.g. 192>
pidfile: <name of pid file, e.g. /var/run/optailer.pid>
tailSleepTimeSeconds: <number of seconds to sleep when no new entries for a given namespace, like 5>

```
## Future functionality

Add the ability to write local copies of collection specific oplog entries to another MongoDB instance.
