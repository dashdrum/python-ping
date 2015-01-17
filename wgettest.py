from time import sleep, time
from datetime import datetime
import sys
import sqlite3
import wget
import os

def open_db():
 
	conn = sqlite3.connect("pingtest.db") # or use :memory: to put it in RAM
	 
	cursor = conn.cursor()
	 
	# create the table if needed
	try:
		cursor.execute("""CREATE TABLE wget
						  (round_trip_time REAL, wget_time DATE) 
					   """)
		conn.commit()
	except:
		pass

	return conn, cursor


url = 'http://gentryville.net/links.htm'

conn, cursor = open_db()


while True:
	try:
		try:
			starttime = time()
			f = wget.download(url)
			rtt = time() - starttime
			print 'RTT',rtt, 'Now',datetime.now()
			cursor.execute('INSERT INTO wget (round_trip_time, wget_time) VALUES(?,?)', ( rtt, datetime.now(), ) )
		except:
			print 'Error', 'Now', datetime.now()
			cursor.execute('INSERT INTO wget (round_trip_time, wget_time) VALUES(?,?)', ( -1, datetime.now(),))
		conn.commit();
		os.remove('links.htm')
		sleep(20)
	except:
		print "Unexpected error:", sys.exc_info()[0]
		break


cursor.execute('''SELECT * FROM wget where round_trip_time < 0 order by wget_time''')
for row in cursor:
    print(row)

conn.close()


