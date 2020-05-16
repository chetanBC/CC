from flask import Flask,url_for,redirect, render_template,jsonify,request,abort	
from datetime import datetime
import requests
import sqlite3
from sqlite3 import Error
import re
import os
import json
import docker

flag=0

count_calls={
	"success":0,
	"failure":0
}
# count_calls["success"]+=1
# count_calls["failure"]+=1

def get_gateway():
	client=docker.DockerClient(base_url='unix:///var/run/docker.sock')
	print(client)
	k=client.networks.list("bridge")
	# print(k.name)
	try:
		return k[0].attrs['IPAM']['Config'][0]['Gateway']
	except Exception as e:
		print(e)

gateway_ip=get_gateway()
print(gateway_ip)

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

	read_req=requests.get(url='http://'+gateway_ip+':8000/api/v1/users')
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
	write_req=requests.post(url="http://"+gateway_ip+":8002/api/v1/db/write",json=write_data)
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

	read_req=requests.get(url='http://'+gateway_ip+':8000/api/v1/users')
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

	write_req1=requests.post(url="http://"+gateway_ip+":8002/api/v1/db/write",json=write_data)
	data=json.loads(write_req1.json())
	if(data == "500"):
		count_calls["failure"]+=1
		return jsonify({}),500

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
	read_req=requests.post(url='http://'+gateway_ip+':8002/api/v1/db/read',json=to_pass)
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



if(__name__=="__main__"):
    message = os.getenv("MESSAGE", "no message specified")
    print(message)
    app.run(host="0.0.0.0",port="8000", debug=True)


