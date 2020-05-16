from flask import Flask,url_for,redirect, render_template,jsonify,request,abort	
from datetime import datetime
import requests
import sqlite3
from sqlite3 import Error
import re
import os
import json
import docker

count_calls={
	"success":0,
	"failure":0
}



def checkdatetime(todb):
	nowtime=datetime.now()
	try:
		todb=datetime.strptime(todb,"%d-%m-%Y:%S-%M-%H")
		if(nowtime<todb):
			return 1
		return 0
	except:
		return 0

def get_gateway():
	client=docker.DockerClient(base_url='unix:///var/run/docker.sock')
	# print(client)
	k=client.networks.list("bridge")
	# print(k.name)
	try:
		return k[0].attrs['IPAM']['Config'][0]['Gateway']
	except Exception as e:
		print(e)

gateway_ip=get_gateway()
# print(gateway_ip)


app=Flask(__name__)



def read_csv():
    f=open("AreaNameEnum.csv","r")
    k=f.read().splitlines()
    a=[]
    b=dict()
    for i in k[1:]:
        l=i.split(",")
        l[0]=int(l[0])
        b[l[0]]=l[1]
    # print(b)
    return b

def get_with_and(cond):
	c=[]
	for i in cond:
		a=i.split("=")
		b="'{}'".format(a[1])
		c.append(a[0]+" = "+b)
	c=" AND ".join(c)
	return c


@app.route("/")
def main():
    #count_calls["success"]+=1
    message = os.getenv("TEAM_NAME", "no message specified")
    return "<html><head><h1>" + message + "<h1></head></html>"



@app.route('/api/v1/rides',methods=["POST"])
def newride():
	
	'''
	Input
	{
		"created_by":"user1",
		"timestamp":"23-12-2020:12-12-12",
		"source":23,
		"destination":24
	}
	'''
	# if request.method!='POST':
	# 	return jsonify({}),405

	d=request.get_json()
	user_created=d["created_by"]
	ts=d["timestamp"]
	source=d["source"]

	destination=d["destination"]

	l=read_csv()

	print("new ride")
	if(not checkdatetime(ts)):
		count_calls["failure"]+=1
		return jsonify({}),400

	if(int(source) not in l.keys() or int(destination) not in l.keys()):
		count_calls["failure"]+=1
		return jsonify({}),400

	table="Rides"
	to_pass={
		"table":"Users",
		"columns":["username"],
		"where":["username={}".format(user_created)]
	}
	
	# read_user=requests.get(url="http://172.17.0.1:80/api/v1/users")
	headers={
		"Origin":"Rides"
	}
	read_user=requests.get(url="http://"+gateway_ip+":8000/api/v1/users",headers=headers)
	print(read_user.request.headers)
 
	to_ride_table={
		"table":table,
		"columns":["username"],
		"where":["username={}".format(user_created)]
	}
	read_copy_user=requests.post(url="http://"+gateway_ip+":8002/api/v1/db/read",json=to_ride_table)
	
	# print(user_created)
    #not a user
	# print(read_user.json())
	if(user_created not in read_user.json()):
		count_calls["failure"]+=1
		print("user not in usertable")
		return jsonify({}),400

    #source and destination are the same
	if(source==destination):
		count_calls["failure"]+=1
		print("source = destination")
		return jsonify({}),400	

    #duplicate rides not allowed
	if(json.loads(read_copy_user.json())):
		count_calls["failure"]+=1
		print("copy users ")
		return jsonify({}),400

	to_write={
		"action":"insert",
		"insert":[user_created,ts,source,destination],
		"column":["username","timestamp","source","destination"],
		"table":table		
	}
	write_to_ride=requests.post(url="http://"+gateway_ip+":8002/api/v1/db/write",json=to_write)
	data=json.loads(write_to_ride.json())
	# print(data)
	if(data == "500"):
		count_calls["failure"]+=1
		return jsonify({}),500

	count_calls["success"]+=1
	return jsonify({}),201


@app.route('/api/v1/rides',methods=["GET"])
def upcomingrides():
	# if request.method!='GET':
	# 	return jsonify({}),405

	l=read_csv()

	#check if source and dest exist
	source=request.args.get('source')
	destination=request.args.get('destination')
	if(source is None or destination is None):
		count_calls["failure"]+=1
		return jsonify({}),400

	#source and dst not in file and int('string') error
	try:
		if(int(source) not in l.keys() or int(destination) not in l.keys()):
			count_calls["failure"]+=1
			return jsonify({}),404	
	except :
		count_calls["failure"]+=1
		return jsonify({}),400

	table="Rides"
	to_pass={
		"table":table,
		"columns":["rideId","username","timestamp"],
		"where":["source={}".format(source),"destination={}".format(destination)]
	}

	read_req=requests.post(url='http://'+gateway_ip+':8002/api/v1/db/read',json=to_pass)
	data=json.loads(read_req.json())

	ret=[]
	if data:
		for i in data:
			if(checkdatetime(i["timestamp"])):
				ret.append(i)
		# return jsonify(ret),200
	if(ret):
		count_calls["success"]+=1
		return jsonify(ret),200

	#if no rides present
	count_calls["success"]+=1
	return jsonify({}),204


@app.route('/api/v1/rides/<rideId>',methods=["GET"])
def listdetailsride(rideId):
	# if request.method!='GET':
	# 	return jsonify({}),405

	#check if rideid exists
	table="Rides"
	to_pass={
		"table":table,
		"columns":["rideId","username","timestamp","source","destination"],
		"where":["rideId={}".format(rideId)]
	}
	read_req=requests.post(url='http://'+gateway_ip+':8002/api/v1/db/read',json=to_pass)
	data=json.loads(read_req.json())

	# print(data)
	#rideid doesn't exist
	if(not data):
		count_calls["failure"]+=1
		return jsonify({}),400
	
	# l=read_csv()
	# # print(l)
	# sr,dt=l[int(data[0]['source'])],l[int(data[0]['destination'])]
	# data[0]['source'],data[0]['destination']=sr,dt


	#username => createdby
	Created_by=data[0]['username']
	data[0].pop('username',None)
	data[0]['Created_by']=Created_by

	#get all users of given ride
	table="JoinRides"
	to_pass_join={
		"table":table,
		"columns":["username"],
		"where":["rideid={}".format(rideId)]
	}
	read_req2=requests.post(url='http://'+gateway_ip+':8002/api/v1/db/read',json=to_pass_join)
	users=json.loads(read_req2.json())

	joinedUsers = []
	for i in users:
		joinedUsers.append(i['username'])

	data[0]['users']=joinedUsers
	count_calls["success"]+=1
	return jsonify(data[0]),200


@app.route('/api/v1/rides/<rideId>',methods=["POST"])
def joinride(rideId):
	# if request.method!='POST':
	# 	return jsonify({}),405
	
	username = request.get_json()["username"]

	#check if username exists
	table='Users'
	
	# read_req=requests.get(url='http://172.17.0.1:80/api/v1/users')
	headers={
		"Origin":"Rides"
	}
	read_req=requests.get(url='http://'+gateway_ip+':8000/api/v1/users',headers=headers)
	print(read_req.request.headers)
	data=read_req.json()
	
    #user not present
	if(username not in data):
		count_calls["failure"]+=1
		return jsonify({}),400

	#check if rideid exists and also if the user is again joining the same ride
	table='Rides'
	to_pass={
		"table":table,
		"columns":["rideid","username"],
		"where":["rideid={}".format(rideId)]
	}
	read_req=requests.post(url='http://'+gateway_ip+':8002/api/v1/db/read',json=to_pass)
	data2=json.loads(read_req.json())
	check_user_in_ridetable={
		"table":table,
		"columns":["rideid","username"],
		"where":["username={}".format(username)]
	}
	read_req2=requests.post(url='http://'+gateway_ip+':8002/api/v1/db/read',json=check_user_in_ridetable)
	data3=json.loads(read_req2.json())
    
    #rideid not present
	if(not data2):
		count_calls["failure"]+=1
		return jsonify({}),400

    #already in ride 
	if(data3):
		count_calls["failure"]+=1
		return jsonify({}),400

	#already in joinrides
	table="JoinRides"
	to_pass={
		"table":table,
		"columns":["username"],
		"where":""
	}
	read_req=requests.post(url='http://'+gateway_ip+':8002/api/v1/db/read',json=to_pass)
	data4=json.loads(read_req.json())
	a=[]
	for i in data4:
		a.append(i["username"])
	if(username in a):
		return jsonify({}),400

	#add user to the specified ride
	table="JoinRides"
	write_data={
		"action":"insert",
		"insert":[rideId,username],
		"column":["rideId","username"],
		"table":table	
	}
	write_req=requests.post(url="http://"+gateway_ip+":8002/api/v1/db/write",json=write_data)
	data=json.loads(write_req.json())
	if(data == "500"):
     
		count_calls["failure"]+=1
		return jsonify({}),500

	count_calls["success"]+=1
	return jsonify({}),200

@app.route('/api/v1/rides/<rideId>',methods=["DELETE"])
def deleteride(rideId):
	# if request.method!='DELETE':
	# 	return jsonify({}),405

	#check if rideid exists
	table='Rides'
	to_pass={
		"table":table,
		"columns":["rideid"],
		"where":["rideid={}".format(rideId)]
	}
	read_req=requests.post(url='http://'+gateway_ip+':8002/api/v1/db/read',json=to_pass)
	data=json.loads(read_req.json())
	
    #rideid not present
	if(not data):
		count_calls["failure"]+=1
		return jsonify({}),400
	
	#Delete a ride from Rides TABLE(it should automatically delete from joinrides table)
	write_data={
		"action":"delete",
		"table" : table,
		"where" : ["rideid={}".format(rideId)]
	}
	
	write_req1=requests.post(url="http://"+gateway_ip+":8002/api/v1/db/write",json=write_data)
	data=json.loads(write_req1.json())
	if(data == "500"):
		count_calls["failure"]+=1
		return jsonify({}),500

	#delete users from joinrides table
	write_data={
		"action":"delete",
		"table" : "JoinRides",
		"where" : ["rideid={}".format(rideId)]
	}
	
	write_req2=requests.post(url="http://"+gateway_ip+":8002/api/v1/db/write",json=write_data)
	data=json.loads(write_req2.json())
	if(data == "500"):
		count_calls["failure"]+=1
		return jsonify({}),500

	count_calls["success"]+=1
	return jsonify({}),200





@app.route('/api/v1/_count',methods=["GET"])
def count():
	if(count_calls["success"]+count_calls["failure"]==0):
		return jsonify(0)
	return jsonify([count_calls["success"]+count_calls["failure"]]) 
  
@app.route('/api/v1/_count',methods=["DELETE"])
def reset_count():
    count_calls["success"]=0
    count_calls["failure"]=0
    return jsonify({})


@app.route('/api/v1/rides/count',methods=["GET"])
def count_rides():
	table="Rides"
	to_pass={
		"table":table,
		"columns":["rideId"],
		"where":""
	}
	read_req=requests.post(url='http://'+gateway_ip+':8002/api/v1/db/read',json=to_pass)
	data=json.loads(read_req.json())
	a=[]
	for i in data:
		a.append(i["rideId"])
	count_calls["success"]+=1
	if(len(a)==0):
		return jsonify(0)
	return jsonify([len(a)])


@app.errorhandler(405)
def for_o_five(e):
    count_calls["failure"]+=1
    return jsonify({}),405	



if(__name__=="__main__"):
    message = os.getenv("MESSAGE", "no message specified")
    # print(message)
    app.run(host="0.0.0.0", port="8001" ,debug=True)


