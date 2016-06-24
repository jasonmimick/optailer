optailer
========

{{optailer}} is a MongoDB tool which exposes oplog data.

Well configured MongoDB systems have authentication enabled. Typically, each application using a cluster will have readWrite permissions on a particular database, but not have any visibility into other databases. This presents a challenge when those applications wish to leverage the ability to monitor all the operations occurring, which is usually done by tailing the oplog. The problem is that there is only one oplog (in the local database) and it contains all the operations for the entire instance. Security restrictions inhibit allowing all applications to read this data.

{{optailer}} solves this issue, by writing a database "local" version of the oplog which is only then accessible by users with read access on their database.


Usage
-----
