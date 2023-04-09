import threading
from flask import Flask, request
import json
import psycopg2
from psycopg2 import sql
import sys
import requests
from urllib import response
import time
from responses import GoodResponse, ServerErrorResponse



import sys
from ast import Pass
import socket               # Import socket module
import threading
import time
# from turtle import ontimer
from pysyncobj import SyncObj, replicated, replicated_sync
from pysyncobj.poller import createPoller
from pysyncobj.tcp_server import TcpServer
from pysyncobj.transport import TCPTransport
from pysyncobj.tcp_connection import TcpConnection, CONNECTION_STATE
from pysyncobj.transport import TCPTransport
from pysyncobj.node import TCPNode
from pysyncobj.monotonic import monotonic as monotonicTime
import functools

app = Flask(__name__)


global sem
sem = threading.Semaphore() # Semaphore for parallel executions

global MAX_TOPICS
MAX_TOPICS = 100000 # Power of 10 only (CAREFUL!!!)

global SLEEP_TIME
SLEEP_TIME = 1

global BROKER_ID
global _conn
global BROKER
global BROKER_MANAGER


class Broker:
    def __init__(self, hostname, httpPort, raftPort, otherBrokers):
        hostAddress = socket.gethostbyname(hostname)
        # print("broker starting",hostAddress)
        self.__selfNode = TCPNode(hostAddress+":"+raftPort)
        self.otherNodes = dict()
        self.__connections = dict()      # (brokername, conn)          
        self.partitions = dict()
        self.__poller = createPoller('auto') # poller to create server
        self.__brokername = hostname
        self.__raftPort = raftPort      # Same for all brokers
        self.__httpPort = httpPort
        self.__server = TcpServer(         
                            self.__brokername,           # tcp server inside the broker
                            self.__poller, 
                            socket.gethostbyname(self.__brokername), 
                            self.__raftPort, 
                            onNewConnection = self.onNewConnectionCallback,
                            sendBufferSize = 2 ** 13,
                            recvBufferSize = 2 ** 13,
                            connectionTimeout = 3.5,
                            keepalive = None,
                        )
        self.__server.bind()
        self.__prevbeat = monotonicTime()
        
        for ob in otherBrokers:
            if ob != self.__brokername:
                hostAddress = socket.gethostbyname(ob)
                # print(hostAddress)
                self.otherNodes[ob] = TCPNode(hostAddress+":"+self.__raftPort)  #add id to recognise
                node = self.otherNodes[ob]
                self.__connections[node] = self.__createConnection(node)
                # print(f'broker.onNewConnectionCallback: List of connections : {list(self.__connections.keys())}')
                # print("broker.__init__: connected with " + ob)

        self.__thread = threading.Thread(target=self.autoTick)
        self.__thread.start()
        # print(self.__otherNodes)
    def autoTick(self):
        while True:
            # print(self.__otherNodes)
            self.onTick()

    def onTick(self):
        # print("broker.onTick: ", self.partitions)
        if monotonicTime() - self.__prevbeat > 0.1:
            self.__prevbeat = monotonicTime()
            for c in list(self.__connections.keys()):
                self.__connections[c].send({'__heartbeat__':monotonicTime()})
        
        for partition in list(self.partitions.keys()):
            self.partitions[partition].onTick(0.05)
            # print(partition, self.partitions[partition]._getLeader())
        self.__poller.poll(0.05)

    
    def __createConnection(self, node): # Initiate connection with other brokers
        if node in self.__connections and self.__connections[node].state == CONNECTION_STATE.CONNECTED:
            return self.__connections[node]
        
        conn = TcpConnection(self.__brokername, 
                             self.__poller,
                             onNewConnectionCallback = self.onNewConnectionCallback)  # TODO onNewConnectionCallback
        conn.connect(node.host, node.port)

        conn.setOnMessageReceivedCallback(functools.partial(self.passToRaftObject, node))
        conn.setOnDisconnectedCallback(functools.partial(self.disconnectedCallback, node))
        conn.setOnConnectedCallback(functools.partial(self.connectedCallback, node))
        return conn
        
    def onNewConnectionCallback(self, name, conn):
        # print(f'broker.onNewConnectionCallback: called by {self.__brokername} with args {name}')
        # if name not in self.otherNodes:
        hostAddress = socket.gethostbyname(name)
        # print(hostAddress)
        node = TCPNode(hostAddress+":"+self.__raftPort)
        self.otherNodes[name] = node
    
        conn.setOnMessageReceivedCallback(functools.partial(self.passToRaftObject, node))
        conn.setOnDisconnectedCallback(functools.partial(self.disconnectedCallback, node))
        conn.setOnConnectedCallback(functools.partial(self.connectedCallback, node))
    
        self.__connections[node] = conn
        for partition in list(self.partitions.keys()):
            if node in self.partitions[partition].getOtherNodes():
                self.partitions[partition].onNodeConnected(node)

        # print(f'broker.onNewConnectionCallback: List of connections : {list(self.__connections.keys())}')


    def send(self,partitionuid,node, message):
        # print("broker.send calling ", message)
        # if self.partitions[partitionuid].counter<10:
        #     print(message)
        message = {
                    '__partitionuid__':partitionuid,
                    '__raftmessage__':message
                    }
        self.__connections[node].send(message)

    def disconnectedCallback(self, node):
        # print(node)
        for p in self.partitions:
            self.partitions[p].onNodeDisconnected(node)
            
    def connectedCallback(self, node):
        # print(f'broker.connectedCallback called with {node}')
        for p in self.partitions:
            self.partitions[p].onNodeConnected(node)   


    #call from processconnections
    def passToRaftObject(self, node, name, raftMessage):
        # print(self.partitions)
        try:
            # if self.partitions[name].counter<10:
            #     print(raftMessage)
            self.partitions[name].onMessageReceived(node, raftMessage)
        except:
            pass

    def createNewPartition(self, name, otherBrokerNodes):
        #check if transport ready then only create partition
        # otherBrokerNodes = [self.otherNodes[nodeName] for nodeName in otherBrokers]
        try:
            cursor = _conn.cursor()
            otherBrokerNodesJson = {'otherbrokers':otherBrokerNodes}
            col_names = sql.SQL(',').join(sql.Identifier(n) for n in ['partition', 'otherbrokers'])
            col_values = sql.SQL(',').join(sql.Literal(n) for n in [name, json.dumps(otherBrokerNodesJson) ])
            query = sql.SQL("""INSERT INTO all_partitions ({col_names})
                        VALUES ({col_values})""").format(col_names=col_names, col_values=col_values)
            cursor.execute(query)
            for ob in otherBrokerNodes:
                if ob not in self.otherNodes and ob != self.__brokername:
                    hostAddress = socket.gethostbyname(ob)
                    # print(hostAddress)
                    self.otherNodes[ob] = TCPNode(hostAddress+":"+self.__raftPort)  #add id to recognise
                    node = self.otherNodes[ob]
                    self.__connections[node] = self.__createConnection(node)

            self.partitions[name] = Partition(name, self.__selfNode, [self.otherNodes[ob] for ob in otherBrokerNodes], self.send)
            
            for ob in otherBrokerNodes:
                self.partitions[name].onNodeConnected(self.otherNodes[ob])
        except Exception as e:
            print(e)
            raise Exception('Error in creating partition')
        
        
        
        
    def createBrokerDatabase(self):
        result = []
        DB_NAME = 'dist_queue'
        _conn = psycopg2.connect(
                host=DB_HOST,
                user="postgres",
                password="admin",
            )

        cursor = _conn.cursor()
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",(DB_NAME,))
        exists = cursor.fetchall()
        cursor.close()
        _conn.close()
        
        if exists:
            _conn = psycopg2.connect(
                host=DB_HOST,
                user="postgres",
                password="admin",
                dbname = DB_NAME
            )

            cursor = _conn.cursor()
            cursor.execute("SELECT * FROM all_partitions") 
            result = cursor.fetchall()

            _conn.close()
            _conn = psycopg2.connect(
                host=DB_HOST,
                user="postgres",
                password="admin"
                )
            
            isolation = _conn.isolation_level
            _conn.set_isolation_level(0)
            cursor = _conn.cursor()
            cursor.execute(sql.SQL("DROP DATABASE {db_name}")
                    .format(db_name = sql.Identifier(DB_NAME)))
            
            _conn.set_isolation_level(isolation)

            _conn.commit()
            cursor.close()
            _conn.close()

        _conn = psycopg2.connect(
            host=DB_HOST,
            user="postgres",
            password="admin"
        )
        
        _conn.autocommit = True
        cursor = _conn.cursor()
        cursor.execute(sql.SQL("CREATE DATABASE {db_name}")
                    .format(db_name = sql.Identifier(DB_NAME)))
        cursor.close()
        _conn.close()

        _conn = psycopg2.connect(
                host=DB_HOST,
                user="postgres",
                password="admin",
                dbname = DB_NAME
            )

        cursor = _conn.cursor()
        cursor.execute("""CREATE TABLE all_partitions (
                partition VARCHAR(255) PRIMARY KEY,
                otherbrokers JSONB
                )""")

        _conn.commit()
        cursor.close()
        _conn.close()

        return result
    
    def getName(self):
        return self.__brokername
        
    def enqueue(self, name, message):
        try:
            self.partitions[name].enqueue(message)
        except Exception as e:
            raise e

    def dequeue(self, name, index):
        try:
            message = self.partitions[name].dequeue(index)
            return message
        except Exception as e:
            raise e

    def hearbeat(self):
        pass

    


class Partition(SyncObj):
    def __init__(self, uid, selfbroker, otherbrokers, sendFunc):
        super().__init__(uid, selfbroker, otherbrokers, sendFunc)
        self.counter = 0
        self._uid = uid
        cursor = _conn.cursor()
        cursor.execute(sql.SQL("""CREATE TABLE {table_name} (
                messageid BIGSERIAL PRIMARY KEY, 
                message TEXT
                )""").format(table_name = sql.Identifier(uid)))
        _conn.commit()
        cursor.close()

    @replicated   
    def enqueue(self, message):
        try:
            cursor = _conn.cursor()
            col_names = sql.SQL(',').join(sql.Identifier(n) for n in ['message'])
            col_values = sql.SQL(',').join(sql.Literal(n) for n in [message])
            query = sql.SQL("""INSERT INTO {table_name} ({col_names}) VALUES ({col_values})""").format(table_name = sql.Identifier(self._uid),
                            col_names=col_names, 
                            col_values=col_values)
            cursor.execute(query)
            _conn.commit()
            cursor.close()
        
        except:
            raise Exception('Failed to insert message into partition')
    
    def dequeue(self, offset):
        try:
            cursor = _conn.cursor()
            cursor.execute(sql.SQL("""SELECT * FROM {table_name} WHERE messageid = {off}""").format(table_name = sql.Identifier(self._uid), 
                                                                                                    off = sql.Literal(offset)))
            message = cursor.fetchall()[0][1]
            # print(message)
            cursor.close()
            return message
        except Exception as e:
            print(e)
            raise Exception('No new message in the queue')
    


@app.route("/partitions", methods = ["POST"])
def RegisterNewPartition():
    data = request.json
    partition = data['partition']
    otherbrokers = data['otherbrokers']
    # print(partition)s
    if partition in BROKER.partitions:
        print('Already present')
        response = ServerErrorResponse('Partition already present')

    else:
        sem.acquire()
        try:
            BROKER.createNewPartition(partition, otherbrokers)
            response = GoodResponse({
                        "status": "success", 
                        "message": f'Partition {partition} created successfully'
                    })
            print(response)
        except Exception as e:
            print(e)
            response = ServerErrorResponse(str(e))
        finally:
            sem.release()
    
    
    # print(response)
    return response   

# Heartbeat done by another thread
def Heartbeat():
    while True:
        url = 'http://' + BROKER_MANAGER + ':5000/heartbeat'
        response = requests.post(url, 
                json = {'broker_id': BROKER_ID}, 
                headers = {'Content-Type': 'application/json'})
        time.sleep(SLEEP_TIME)



@app.route("/enqueue", methods = ["POST"])
def EnqueueMessage():
    data = request.json
    partition = data["partition"]
    message = data["message"]
    try:
        BROKER.enqueue(partition, message)
        response = GoodResponse({"status": "success"}) 
    except:
        response = ServerErrorResponse('error in adding message to the queue')
    return response

@app.route("/dequeue", methods = ['GET'])
def DequeueMessage():
    # return ServerErrorResponse(str("not really an error just like that"))
    data = request.json
    partition = data['partition']
    offset = data['offset']
    try:
        message = BROKER.dequeue(partition, offset)
        # print(message)
        response = GoodResponse({"status": "success", "message": str(message)})
    except Exception as e:
        response = ServerErrorResponse(str(e))
    return response

@app.route("/")
def home():
    return "Hello, World from Broker!"


if __name__ == "__main__":
    print('BROKER STARTED')
    BROKER_ID = str(sys.argv[1])
    httpPort = str(sys.argv[2])
    raftPort = str(sys.argv[3])
    DB_HOST  = str(sys.argv[4])
    BROKER_MANAGER = str(sys.argv[5])

    url = 'http://' + BROKER_MANAGER + ':5000/broker/register' 
    resp = requests.post(url, 
                json = {'broker_id': BROKER_ID}, 
                headers = {'Content-Type': 'application/json'})
    
    if resp.status_code != 200:
        print('Unable to get list')
        exit()
    


    BROKER = Broker(BROKER_ID, httpPort, raftPort, resp.json()['brokers'])
    result = BROKER.createBrokerDatabase()
    DB_NAME = 'dist_queue'
    _conn = psycopg2.connect(
            host=DB_HOST,
            user="postgres",
            password="admin",
            dbname = DB_NAME
        )
    


    heartbeat_thread = threading.Thread(target = Heartbeat)
    # heartbeat_thread.start()
    for r in result:
        BROKER.createNewPartition(r[0], r[1]['otherbrokers'])
    app.run(debug=True, host = '0.0.0.0', use_reloader=False)

    