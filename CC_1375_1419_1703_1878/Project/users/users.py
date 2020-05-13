from flask import Flask,url_for,redirect, render_template,jsonify,request,abort	
from datetime import datetime
import requests
import sqlite3
from sqlite3 import Error
import re
import os
import json

flag=0

count_calls={
	"success":0,
	"failure":0
}
# count_calls["success"]+=1
# count_calls["failure"]+=1

def checkdatetime(todb):
	nowtime=datetime.now()
	try:
		todb=datetime.strptime(todb,"%d-%m-%Y:%S-%M-%H")
		if(nowtime<todb):
			return 1
		return 0
	except:
		return 0
    

app=Flask(__name__)

def password_sha1_check(pwd):
	matches=re.findall("^[A-Fa-f0-9]{40}$",pwd)
	if(len(matches)==1):
		return 1
	return 0


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



@app.route('/api/v1/users',methods=["PUT"])
def adduser():
	'''
	Input
	{
	"username":"user5",
	"password":"password1"
	}
	'''
	# if request.method!='PUT':
	# 	return jsonify({}),405

	global flag
	flag=1

	d=request.get_json()
	username=d["username"]
	password=d["password"]

	#check for null username
	if(not username):
		count_calls["failure"]+=1
		return jsonify({}),400

	table="Users"

	read_req=requests.get(url='http://ec2-52-23-183-153.compute-1.amazonaws.com/api/v1/users')
	data=read_req.json()


	print(data)
	#username already exists
	if(username in data):
		count_calls["failure"]+=1
		return jsonify({}),400

	if(not password_sha1_check(password)):
		count_calls["failure"]+=1
		return jsonify({}),400

	write_data={
		"action": "insert",
		"insert" : [username,password],
		"column" : ["username","password"],
		"table" : table
	}
	write_req=requests.post(url="http://ec2-54-159-120-199.compute-1.amazonaws.com/api/v1/db/write",json=write_data)
	data=json.loads(write_req.json())

	if(data == "500"):
		count_calls["failure"]+=1
		return jsonify({}),500

	count_calls["success"]+=1
	return jsonify({}),201


@app.route('/api/v1/users/<user_name>',methods=["DELETE"])
def removeuser(user_name):
    	# if request.method!='DELETE':
	# 	return jsonify({}),405

	# if(user_name==None):
	#     return jsonify({}),400

	table='Users'

	global flag
	flag=1

	read_req=requests.get(url='ec2-52-23-183-153.compute-1.amazonaws.com/api/v1/users')
	data=read_req.json()

	#username not present
	if(user_name not in data):
		count_calls["failure"]+=1
		return jsonify({}),400

	#delete user
	write_data={
		"action":"delete",
		"table" : table,
		"where" : ["username={}".format(user_name)]
	}

	write_req1=requests.post(url="http://ec2-54-159-120-199.compute-1.amazonaws.com/api/v1/db/write",json=write_data)
	data=json.loads(write_req1.json())
	if(data == "500"):
		count_calls["failure"]+=1
		return jsonify({}),500

	'''
	#get rideid of user from rides table in order to delete entire ride from joinrides table
	to_pass={
		"table":"Rides",
		"columns":["rideid"],
		"where":["username={}".format(user_name)]
	}
	read_req2=requests.post(url='http://172.17.0.1:80/api/v1/db/read',json=to_pass)
	data1=read_req2.json()

	#delete from rides table
	write_data={
		"action":"delete",
		"table" : "Rides",
		"where" : ["username={}".format(user_name)]
	}

	write_req2=requests.post(url="http://172.17.0.1:80/api/v1/db/write",json=write_data)
	data=write_req2.json()
	if(data == "500"):
		return jsonify({}),500


	write_data={
		"action":"delete",
		"table" : "JoinRides",
		"where" : ["username={}".format(user_name)]
	}

	write_req3=requests.post(url="http://172.17.0.1:80/api/v1/db/write",json=write_data)
	data=write_req3.json()
	if(data == "500"):
		return jsonify({}),500

	#delete from joinrides table
	if(data1):
		rideid = data1[0]['rideid']
		write_data={
			"action":"delete",
			"table" : "JoinRides",
			"where" : ["rideid={}".format(rideid)]
		}

		write_req3=requests.post(url="http://172.17.0.1:80/api/v1/db/write",json=write_data)
		data=write_req3.json()
		if(data == "500"):
			return jsonify({}),500
   	'''
	count_calls["success"]+=1
	return jsonify({}),200


@app.route('/api/v1/users',methods=["GET"])
def list_all_users():
	table="Users"
	to_pass={
		"table":table,
		"columns":["username"],
		"where":""
	}
	read_req=requests.post(url='http://ec2-54-159-120-199.compute-1.amazonaws.com/api/v1/db/read',json=to_pass)
	data=read_req
	data=json.loads(data.json())
	a=[]
	print(data)
	for i in data:
		a.append(i["username"])
	global flag
	if(flag==0):
		count_calls["success"]+=1
	flag=0
	return jsonify(a)
	# # print(data.json()) 
	# return jsonify(data)
	# # return jsonify(data),200

#########################clear db##########################

#@app.route('/api/v1/db/clear',methods=["POST"])	
#def clear_db():
#	db="Users"
	# db="Rides"
	# db="JoinRides"


#	write_data={
#		"action":"delete",
#		"table" : [db],
#		"where" : ""
#	}

#	write_req1=requests.post(url="http://ec2-54-159-120-199.compute-1.amazonaws.com/api/v1/db/write",json=write_data)
#	data=json.loads(write_req1.json())

#	if(data == "500"):
#		count_calls["failure"]+=1
#		return jsonify({}),500

#	return jsonify({}),200

	# query="DELETE FROM "+db+";"
	# try:
	# 	result=conn.execute(query)
	# 	conn.commit()
	# 	#count_calls["success"]+=1
	# 	return jsonify({}),200
	# except Error as e:
	# 	#count_calls["failure"]+=1
	# 	return jsonify("500"),500

#############################################################

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

@app.errorhandler(405)
def for_o_five(e):
    count_calls["failure"]+=1
    return jsonify({}),405


# @app.route('/api/v1/db/read',methods=["POST"])
# def read():

# 	'''
# 	{
# 	"table" : "Users",
# 	"columns" : ["username","password"],
# 	"where" : "username=user1"
# 	}

# 	'''
# 	d=request.get_json()
# 	table=d["table"]
# 	column_to_select=d["columns"]

# 	cs=column_to_select

# 	t=len(column_to_select)

# 	column_to_select= ",".join(column_to_select)

# 	cond=d["where"]

# 	if(cond==""):
# 		query="SELECT "+column_to_select+" FROM "+table+";"
# 	else:
# 		c=get_with_and(cond)

# 		query="SELECT "+column_to_select+" FROM "+table+" WHERE "+"( "+c+");"
# 	try:
# 		result=conn.execute(query)
# 		b=[]
# 		j=0
# 		for i in result:
# 			a=dict()
# 			for j in range(t):
# 				a[cs[j]]=i[j]
# 			b.append(a)
		
# 		return jsonify(b),200

# 	except Error as e:
# 		return jsonify("500"),500

# @app.route('/api/v1/db/write',methods=["POST"])
# def write():
# 	'''
# 	Input
# 	{
# 	"insert" : ["user1","password1"],
# 	"column" : ["username","password"],
# 	"table" : "Users"
# 	}
# 	'''
# 	conn = sqlite3.connect('Users.db',check_same_thread=False)
# 	if(not conn):
# 		return jsonify({}),500

# 	d=request.get_json()
# 	action = d["action"]

# 	if(action == "insert"):
# 		data=d["insert"]
# 		data=",".join("'{}'".format(i) for i in data)
# 		column=",".join(d["column"])
# 		table=d["table"]
# 		query="INSERT INTO "+table+" (" +column+ ") "+"VALUES ( " + data + " );"

# 	else:
# 		table = d["table"]
# 		cond=d["where"]
# 		c=get_with_and(cond)
# 		query="DELETE FROM "+table+" WHERE "+"( "+c+");"

# 	try:
# 		conn.execute(query)
# 		conn.commit()
# 		conn.close()
# 		return jsonify({}),200

# 	except Error as e:
# 		print(e)
# 		return jsonify("500"),500


if(__name__=="__main__"):
    message = os.getenv("MESSAGE", "no message specified")
    print(message)
    app.run(host="0.0.0.0",port="8000", debug=True)


