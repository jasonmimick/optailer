#!/bin/bash

# optailer-test
# setup a replicaSet, write data, and
# then test the optailer tool.

killall mongo
killall mongod
sleep 2
PORT=28000
rm -rf ./data
mkdir ./data
mongod --replSet optailer --fork --dbpath ./data --logpath ./data/mongod.log --port $PORT
sleep 1

mongo --port $PORT --eval 'rs.initiate();sleep(5000)'

rm __optailer-test-loader-1.js
echo "db.getSiblingDB('test').foo.insert({'ts':new Date(),'d':'X'.pad(99,true,'X')})" > __optailer-test-loader-1.js

rm __optailer-test-loader-2.js
echo "db.getSiblingDB('foo').bar.insert({'ts':new Date(),'W':'X'.pad(99,true,'X')})" > __optailer-test-loader-2.js

echo "starting data load processes..."
mongo --port $PORT --eval 'while (true) { load("./__optailer-test-loader-1.js");sleep(1000);}' &
mongo --port $PORT --eval 'while (true) { load("./__optailer-test-loader-2.js");sleep(1000);}' &
sleep 2
echo "data load process running"
ps -ef | grep mongo | grep $PORT

#echo "optailer starting..."
#./optailer.py --mongodb mongodb://localhost:$PORT/?replicaSet=optailer --namespaces test.foo,foo.bar --verbose
