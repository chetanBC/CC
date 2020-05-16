# from flask import Flask,url_for,redirect, render_template,jsonify,request,abort   
from datetime import datetime
# import requests
import sqlite3
from sqlite3 import Error
import re
import os
import pika
import sys
import json
import time
import docker
from subprocess import PIPE, run
import threading


from datetime import datetime

#database
db='Users_Rides.db'

#connect to the database
conn = sqlite3.connect(db,check_same_thread=False)
if(not conn):
    abort(500)

conn.execute("PRAGMA foreign_keys=ON")

conn.execute('''CREATE TABLE IF NOT EXISTS Users(
           username TEXT PRIMARY KEY NOT NULL,
           password TEXT NOT NULL
            );''')

#Rides table
conn.execute('''CREATE TABLE IF NOT EXISTS Rides(
  rideId INTEGER  PRIMARY KEY,
  username TEXT NOT NULL ,
  "timestamp" DATETIME NOT NULL,
  source INTEGER NOT NULL,
  destination INTEGER NOT NULL
  );''')


#join rides table
conn.execute('''CREATE TABLE IF NOT EXISTS JoinRides(
  rideId INT NOT NULL,
  username TEXT PRIMARY KEY ,
  CONSTRAINT "ride" FOREIGN KEY (rideId) REFERENCES Rides(rideId) ON DELETE CASCADE
  );''')


#pika connections for read and write
connection_read = pika.BlockingConnection(
        pika.ConnectionParameters(host='rmq'))
connection_write = pika.BlockingConnection(
        pika.ConnectionParameters(host='rmq'))


#channels for read, write and sync queues
channelm=connection_write.channel()
channelr=connection_read.channel()
channel2r=connection_read.channel() 










def out(command):
    # print("Command",command)
    try:
        result = run(command, stdout=PIPE, stderr=PIPE, universal_newlines=True, shell=True)
        return result.stdout
    except Exception as e:
        print(e)
        print("EORORORORO")

        return "ERRORRRRRRRR>>>>>>>>>>>>>>>>>>>>>>>"


#to split the query and get the conditions in <condition1> and <condition2> and ....)
def get_with_and(cond):
    c=[]
    for i in cond:
      a=i.split("=")
      b="'{}'".format(a[1])
      c.append(a[0]+" = "+b)
    c=" AND ".join(c)
    return c



#writedb function to process all the write requests
def writedb(d):
    '''
    Input
    {
    "insert" : ["user1","password1"],
    "column" : ["username","password"],
    "table" : "Users"
    }
    '''
    conn = sqlite3.connect(db,check_same_thread=False)
    # print(conn)
    if(not conn):
        return jsonify({}),500

    # d=request.get_json()  
    action = d["action"]

    if(action == "insert"):
        data=d["insert"]
        data=",".join("'{}'".format(i) for i in data)
        column=",".join(d["column"])
        table=d["table"]
        query="INSERT INTO "+table+" (" +column+ ") "+"VALUES ( " + data + " );"

    else:
        table = d["table"]
        cond=d["where"]

        if(cond!=""):
            c=get_with_and(cond)
            query="DELETE FROM "+table+" WHERE "+"( "+c+");"
        
        else:
            for i in table:
                query="DELETE FROM "+i+";"
                conn.execute(query)
                conn.commit()
            conn.close()
            r=json.dumps("{}")
            return r

    try:
        conn.execute(query)
        conn.commit()
        conn.close()
        r=json.dumps("{}")
        return r

    except Error as e:
        # print(e)
        return json.dumps("500")




def on_request_write(ch, method, props, body):
    
    # print(body)
    print("writedb request |||||||||||||||")
    body=json.loads(body)

    # print(body)

    response = writedb(body)

    # print(response)

    response=json.loads(response)
    
    #to fanout the write requests to all the slaves i.e, to sync in all the slaves
    if(response!="500"):
        print("sync request sent to slave ||||||||||||||||||")
    
        ch.exchange_declare(exchange='logs', exchange_type='fanout')
        mess=json.dumps(body)
        ch.basic_publish(exchange='logs', routing_key='', body=mess)
       

    response=json.dumps(response)

    ch.basic_publish(exchange='',
                     routing_key=props.reply_to,
                     properties=pika.BasicProperties(correlation_id = \
                                                         props.correlation_id),
                     body=response)
    ch.basic_ack(delivery_tag=method.delivery_tag)



#master function to access the write queue
def master(channelm):


    print("WRITE CHANNEL")

    channelm.queue_declare(queue='write_q', exclusive=True, durable=True)

    # print("Hi ........ I'm master!!!!!!!!!!!!!!!!!!")


    channelm.basic_qos(prefetch_count=1)
    channelm.basic_consume(queue='write_q', on_message_callback=on_request_write)

    # print(" [x] Awaiting RPC requests")
    try:
        channelm.start_consuming()
    except Exception as e:
        print("Write queue", e)


##################################################################################################



#To process all the readrequests
def readdb(d):

    '''
    {
    "table" : "Users",
    "columns" : ["username","password"],
    "where" : "username=user1"
    }

    '''
    # d=request.get_json()
    # print(d)
    table=d["table"]
    column_to_select=d["columns"]

    cs=column_to_select

    t=len(column_to_select)

    column_to_select= ",".join(column_to_select)

    cond=d["where"]

    if(cond==""):
        query="SELECT "+column_to_select+" FROM "+table+";"
    else:
        c=get_with_and(cond)

        query="SELECT "+column_to_select+" FROM "+table+" WHERE "+"( "+c+");"
    try:
        result=conn.execute(query)
        b=[]
        j=0
        for i in result:
            a=dict()
            for j in range(t):
                a[cs[j]]=i[j]
            b.append(a)
        
        r=json.dumps(b)
        return r
        # return jsonify(b),200

    except Error as e:
        r=json.dumps("500")
        return r
        # return jsonify("500"),500


def on_request_read(ch, method, props, body):
    # print("Environment",os.environ.get('source'))

    print("Readdb request ||||||||||||||||||||")

    body=json.loads(body)
    response = readdb(body)

    response=json.dumps(response)

    ch.basic_publish(exchange='',
                     routing_key=props.reply_to,
                     properties=pika.BasicProperties(correlation_id = \
                                                         props.correlation_id),
                     body=response)
    ch.basic_ack(delivery_tag=method.delivery_tag)




def callback(ch, method, properties, body):
    # print(" [x] %r" % body)
    # sys.exit(0)
    print("sync request from master |||||||||||||||||| ")
    # print(queue_name)

    if(body):
        k=writedb(json.loads(body))
        print(k)



########################### ------------ slave ------------------- ###############


#process the read queue
def slave(channelr,channel2r):

    if(zk.exists("/worker")):
        children=zk.get_children("/worker")
        print(children)




    try:

        channelr = connection_read.channel()
        channel2r = connection_read.channel()

        channelr.basic_qos(prefetch_count=1)
        channelr.queue_declare(queue='read_q')


        channelr.basic_consume(queue='read_q', on_message_callback=on_request_read)

        # channel.start_consuming()

        # print("Environment",os.environ.get('source'))

        # channel2 = connection2.channel()    


        channel2r.exchange_declare(exchange='logs', exchange_type='fanout')

        result = channel2r.queue_declare(queue='', exclusive=True)
        queue_name = result.method.queue
        # print(queue_name)

        channel2r.queue_bind(exchange='logs', queue=queue_name)



        channel2r.basic_consume(
            queue=queue_name, on_message_callback=callback)
        # sys.exit(0)
        try:
            channelr.start_consuming()
            channel2r.start_consuming()
        except Exception as e:
            print("Read queue",e)


    except Exception as e :
        print(e)




########################### KAZOO  ##############3

import logging

from kazoo.client import KazooClient
from kazoo.client import KazooState
from kazoo.protocol.states import EventType
from kazoo.exceptions import NoNodeError


logging.basicConfig()

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


zk = KazooClient(hosts='zoo:2181')
zk.start()


zk.ensure_path("/worker")
zk.ensure_path("/master")

zk.add_listener(my_listener)


# children=[]
if(zk.exists("/worker")):
    children=zk.get_children("/worker")
    print(children)

    

@zk.DataWatch("/master")
def watch_node(data, stat, event):
    # pid=
    # print("data c",data)
    children=zk.get_children("/worker")
    # print(children)

    # print("Status >>>>>>>>>>>>>>>",stat)
    children=[int(i) for i in children]
    children=sorted(children)
    # print("HERE ",children)
    # master()
    # mcid=zk.get("/master")
    # print("BEFORE")
    try:
        data,stat=zk.get("/worker/"+str(children[0]))
        cid=data.decode()[:12]

        cname=os.uname()[1]
        # print("hostname",cname)
    except Exception as e:
        print(e)


    try:
        print(event)
        if(event):
            if event.type=="CREATED":
                print(event.type)
                # print(children)
                if(len(children)>0):
                    zk.delete("/worker/"+str(children[0]))
                else:
                    cid,stat=zk.get("/master")
                    cid=cid.decode()[:12]



            if event.type=="CHANGED" or event.type=="DELETED":
                print(event.type)

                # print("AFTER")   
                # print(cid)
                zk.create("/master", cid.encode(), ephemeral=True)
                

    except Exception as e:
        print(e)




@zk.ChildrenWatch('/worker')
def watch_child(children):
    # print("EVENT",ChildrenWatch)
    try:
        # print("children outside ", children)
        print("master_election")

        children=[int(i) for i in children]
        children=sorted(children)

        print("Children list",children)
        elect_master=str(children[0])

        data,stat=zk.get("/master")

        cid=data.decode()[:12]

        hostname=os.uname()[1]
        # print("hostname",hostname)



        if(hostname==cid):
            try:
                try:
                    channelr.stop_consuming()
                    channel2r.stop_consuming()  
                    connection_read.close()
                    # print("LMKO")
                except Exception as e:
                    print("Read close",e)
            except Exception as e:
                print(e)



            print("Master.................")
            # channelm

            connection_write = pika.BlockingConnection(
                    pika.ConnectionParameters(host='rmq'))

            channelm=connection_write.channel()
            try:
                master(channelm)
            except Exception as e:
                print("new master error",e)
    except Exception as e:
        print("Exception ",e)






#to run the code either as master/slave
mcid=zk.get("/master")[0]
# print(mcid,"MCIDE>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
cname=os.uname()[1]
# print(mcid,cname)
mcid=mcid.decode()[:12]
# print("con_id",mcid)
# print("con_nanan",cname)
if(cname==mcid):
    print("Master ........................")
    try:
        channelr.stop_consuming()
        channel2r.stop_consuming()
        connection_read.close()
    except Exception as e:
        print(e)

    master(channelm)
else:
    # connection_write.close()
    try:
        channelm.stop_consuming()
        connection_write.close()
    except Exception as e:
        print(e)

    print("Slave ........................")
    slave(channelr,channel2r)
