from flask import Flask,url_for,redirect, render_template,jsonify,request,abort 
from datetime import datetime
import requests
import sqlite3
from sqlite3 import Error
import re
import os
import pika
import sys
import time
import json
import docker
import threading
from subprocess import PIPE, run
import subprocess
app=Flask(__name__)


#!/usr/bin/env python
import pika
import uuid

count=0
prev_count=0

slave_count=1

send_flg=0


req_list=[]


#Get the gateway ip of the docker 
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

################################# ------ Kazoooo __-----------------------####################
import logging

from kazoo.client import KazooClient
from kazoo.client import KazooState


logging.basicConfig()



def ms(name):
    client=docker.DockerClient(base_url='unix:///var/run/docker.sock')
    l=client.containers.list(filters={"name":name})
    k=l[0].top()['Processes'][0][1]
    id=l[0].id
    return int(k),id



zk = KazooClient(hosts='zoo:2181')
zk.start()

def my_listener(state):
    print("HERR",state)
    if state == KazooState.LOST:
        # Register somewhere that the session was lost
        print("LOST")
    elif state == KazooState.SUSPENDED:
        # Handle being disconnected from Zookeeper
        print("SUSPENDED")
    else:
        print("HI")
        # Handle being connected/reconnected to Zookeeper






zk.delete("/worker", recursive=True)
zk.delete("/master", recursive=True)

zk.ensure_path("/worker")


zk.add_listener(my_listener)


#get the pid and the container id of the master and slave
mid,cmid=ms("master")
sid,csid=ms("slave")



#create a znode for the containers (master and slave ) at the start of the orchestrator
if(zk.exists("/worker/"+str(mid)) or zk.exists("/master"+str(sid))) :
    print("Node already exists")
else:
    print("Creating...")
        
    zk.create("/worker/"+str(sid), csid.encode(), ephemeral=True)
    zk.create("/master", cmid.encode(), ephemeral=True)


#############################################_____END_____####################################



#this is rpc code for read queue
class RpcClient(object):

    def __init__(self):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='rmq'))

        self.channel = self.connection.channel()

        result = self.channel.queue_declare(queue='response_q', auto_delete=True)
        # self.callback_queue = result.method.queue
        self.callback_queue = result.method.queue

        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True)

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def call(self, n):
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key='read_q',
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
                  delivery_mode=2,
            ),
            body=str(n))
        while self.response is None:
            self.connection.process_data_events()
        return json.loads(self.response)



#Set interval to call the function at regular intervals
class setInterval :
    def __init__(self,interval,action) :
        self.interval=interval
        self.action=action
        self.stopEvent=threading.Event()
        thread=threading.Thread(target=self.__setInterval)
        thread.start()

    def __setInterval(self) :
        nextTime=time.time()+self.interval
        while not self.stopEvent.wait(nextTime-time.time()) :
            nextTime+=self.interval
            self.action()

    def cancel(self) :
        self.stopEvent.set()


def on_response(ch, method, props, body):
    print("for new slave   ",body)
    # body=json.dumps(body)
    global send_flg
    if(send_flg==0):
        print("sending ...............")
        ch.exchange_declare(exchange='logs', exchange_type='fanout')
        # mess=json.dumps(body)
        # print(body)
        ch.basic_publish(exchange='logs', routing_key='', body=body)
        send_flg=0


#create slave function to create the slave on scale up and associate a node to it
def create_slave(i):
    client=docker.DockerClient(base_url='unix:///var/run/docker.sock')
    
    slave_name='slave'+str(i)
    container=client.containers.run(image="worker:latest",name=slave_name,links={'rmq':'rmq'}, network_mode='project_default', detach=True)

    l=client.containers.list()

    for ik in l:
        print(ik.name,ik.id)


    ############# fanout


    time.sleep(3)

    #send the previous write requests to the newly created slave so it syncs with the data that is present in other slave containers
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='rmq'))

    ch = connection.channel()

    ch.exchange_declare(exchange='logs', exchange_type='fanout')
    for i in req_list:
        print(i)
        mess=json.dumps(i)
        ch.basic_publish(exchange='logs', routing_key='', body=mess)

    connection.close()


    pd,cd=ms(slave_name)

    zk.create("/worker/"+str(pd), cd.encode(), ephemeral=True)

    
    #################################


#check for the condition whether to scale up/down with the number requests received and reset that counter at regular interval
def creat_cond2():
    global count
    c=count
    # c=c-10
    import math
    k=int(math.ceil(c/20.0))
    # print(k)
    if(k==0):
        k=1

    child=len(zk.get_children("/worker"))
    num=k-child
    n1=num

    # print(n1)

    #create n1 number of slaves
    while(num>0 and n1>0):
        n1-=1
        global slave_count
        slave_count+=1
        create_slave(slave_count)

    #delete n1 number of slaves
    while(num<0 and n1<0):
        n1+=1
        req=requests.post(url="http://"+gateway_ip+":8002/api/v1/crash/slave")
        rep=req.json()
        print(rep)

    count=0

    

@app.route('/api/v1/db/read',methods=["POST"])
def read():
        
    global count
    count+=1

    # StartTime=time.time()
    global send_flg

    if(send_flg==0):
        send_flg=1
        print("Started..............")

        #set interval of 120 secs(2 min)
        inter=setInterval(120,creat_cond2)
        t=threading.Timer(10000,inter.cancel)
        t.start()


    d=request.get_json()

    print("count",count)

    
    rpc = RpcClient()

    response = rpc.call(json.dumps(d))

    return jsonify(response)



#RPC code for the write queue
class RpcClient2(object):

    def __init__(self):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='rmq'))

        self.channel = self.connection.channel()

        result = self.channel.queue_declare(queue='',durable=True)
        # self.callback_queue = result.method.queue
        self.callback_queue = result.method.queue

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True)

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def call(self, n):
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key='write_q',
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=str(n))
        while self.response is None:
            self.connection.process_data_events()
        return json.loads(self.response)



    

@app.route('/api/v1/db/write',methods=["POST"])
def write():
        
    d=request.get_json()

    print("Write")

    rpc = RpcClient2()

    response = rpc.call(json.dumps(d))

    if(response!="500"):
        req_list.append(d)

    return jsonify(response)


#clear db api
@app.route('/api/v1/db/clear',methods=["POST"]) 
def clear_db():
    db=["Users","Rides","JoinRides"]
    # db="Rides"
    # db="JoinRides"


    write_data={
        "action":"delete",
        "table" : db,
        "where" : ""
    }

    write_req1=requests.post(url="http://"+gateway_ip+":8002/api/v1/db/write",json=write_data)
    data=json.loads(write_req1.json())

    if(data == "500"):
        return jsonify({}),500

    return jsonify({}),200




#crash slave api
@app.route('/api/v1/crash/slave',methods=["POST"])
def crash_slave():
    client=docker.DockerClient(base_url='unix:///var/run/docker.sock')


    children=zk.get_children("/worker")
    children=[int(i) for i in children]
    children=sorted(children)

    pid_to_kill=children[-1]
    data,stat=zk.get("/worker/"+str(pid_to_kill))
    data=data.decode()

    # print(data,pid_to_kill,children)

    k=client.containers.get(data)

    if len(children)>0:
        k.kill()
        k.remove()
        zk.delete("/worker/"+str(pid_to_kill))
        global slave_count
        slave_count+=1
        create_slave(slave_count)
        sid,csid=ms("slave"+str(slave_count))
        try:
            zk.create("/worker/"+str(sid), csid.encode(), ephemeral=True)
        except Exception as e:
            print(e)
        return jsonify([pid_to_kill])

    else:
        return jsonify({}),400



@app.route('/api/v1/crash/master',methods=["POST"])
def crash_master():

    client=docker.DockerClient(base_url='unix:///var/run/docker.sock')
    data,stat=zk.get("/master")
    data=data.decode()
    # print(data)


    container=client.containers.get(data)
    # print("old master container",data)


    pid=container.top()['Processes'][0][1]


    # print(pid)

    children=zk.get_children("/worker")
    children=[int(i) for i in children]
    children=sorted(children)

    print(children)

    datac,statc=zk.get("/worker/"+str(children[0]))
    # print(children[0], datac)

    if(len(children)>0):
        container.kill()
        container.remove()
        # time.sleep(3)
        zk.delete("/master")
        global slave_count
        slave_count+=1
        create_slave(slave_count)
        sid,csid=ms("slave"+str(slave_count))
        try:
            zk.create("/worker/"+str(sid), csid.encode(), ephemeral=True)
        except Exception as e:
            print(e)
        # zk.set("/master",datac)
        return jsonify([int(pid)])
    else:
        return jsonify({}),400



#list worker api
@app.route('/api/v1/worker/list')
def list_pid():


    # lo=[]
    master,stat=zk.get("/master")
    master=master.decode()

    client=docker.DockerClient(base_url='unix:///var/run/docker.sock')

    mast_cont=client.containers.get(master).top()['Processes'][0][1]

    # print(mast_cont)

    # lo.append(mast_cont)

    worker=zk.get_children("/worker")

    worker.append(mast_cont)    

    worker=sorted([int(i) for i in worker])

    print(worker)

    return jsonify(worker)



if(__name__=="__main__"):
    message = os.getenv("MESSAGE", "no message specified")
    print(message)
    app.run(host="0.0.0.0",port="8002", debug=True)
