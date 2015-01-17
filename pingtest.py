from ping import Handler, TimeoutError
from time import sleep
from datetime import datetime
import sys
import sqlite3

def open_db():
 
	conn = sqlite3.connect("pingtest.db") # or use :memory: to put it in RAM
	 
	cursor = conn.cursor()
	 
	# create the table if needed
	try:
		cursor.execute("""CREATE TABLE ping
						  (round_trip_time REAL, ping_time DATE) 
					   """)
		conn.commit()
	except:
		pass

	return conn, cursor


h = Handler(destination="google-public-dns-b.google.com")

conn, cursor = open_db()


while True:
	try:
		try:
			rtt = h.ping()
			print rtt, datetime.now()
			cursor.execute('''INSERT INTO ping (round_trip_time, ping_time) VALUES(?,?)''', ( rtt, datetime.now(), ) )
		except TimeoutError:
			print 'Timeout', datetime.now()
			cursor.execute('INSERT INTO ping (round_trip_time, ping_time) VALUES(?,?)', ( -1, datetime.now(),))
		conn.commit();
		sleep(60)
	except:
		print "Unexpected error:", sys.exc_info()[0]
		break

h.close()

cursor.execute('''SELECT * FROM ping''')
for row in cursor:
    print(row)

conn.close()


