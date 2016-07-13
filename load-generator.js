
while ( true ) {
    try {
	db.getSiblingDB('test').foo.insert({'ts':new Date(),'d':'X'.pad(99,true,'X')});
	db.getSiblingDB('foo').bar.insert({'ts':new Date(),'W':'X'.pad(99,true,'X')});
	sleep(500);
    } catch (error) {
	printjson(error);
	sleep(1000);
    }
}
