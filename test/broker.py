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
from pysyncobj.tcp_connection import TcpConnection
from pysyncobj.transport import TCPTransport
from pysyncobj.node import TCPNode
import functools

class Broker:
    def __init__(self, hostname,httpPort, raftPort, otherBrokers):
        self.__selfNode = TCPNode(socket.gethostbyname(hostname)+":"+raftPort)
        self.otherNodes = {}
        self.__connections = {}      # (brokername, conn)          
        self.__partitions = {}
        self.__poller = createPoller('auto') # poller to create server
        self.__brokername = hostname
        self.__raftPort = raftPort      # Same for all brokers
        self.__httpPort = httpPort
        self.__server = TcpServer(         
                            self.__brokername,           # tcp server inside the broker
                            self.__poller, 
                            socket.gethostbyname(self.__brokername), 
                            self.__raftPort, 
                            onNewConnection = self.__onNewConnectionCallback,
                            sendBufferSize = 2 ** 13,
                            recvBufferSize = 2 ** 13,
                            connectionTimeout = 3.5,
                            keepalive = None,
                        )
        self.__server.bind()
        
        for ob in otherBrokers:
            self.otherNodes[ob] = TCPNode(socket.gethostbyname(ob)+":"+raftPort)  #add id to recognise
            node = self.otherNodes[ob]
            self.__connections[node] = self.__createConnection(node)
            print("connected with " + ob)

        self.__thread = threading.Thread(target=self.autoTick)
        self.__thread.start()
        # print(self.__otherNodes)
    def autoTick(self):
        while True:
            # print(self.__otherNodes)
            self.onTick()

    def onTick(self):
        for partition in list(self.__partitions.keys()):
            self.__partitions[partition]._onTick(0.05)
        self.__poller.poll(0.05)

    
    def __createConnection(self, node): # Initiate connection with other brokers
        conn = TcpConnection(self.__brokername,self.__poller)
        conn.__onMessageReceived = functools.partial(self.passToRaftObject,node=node)
        conn.connect(node.host, node.port)

        return conn
        
    def __onNewConnectionCallback(self, name, conn):
        if name not in self.otherNodes:
            node = TCPNode(socket.gethostbyname(name)+":"+self.__raftPort)
            self.otherNodes[name] = node
        conn.__onMessageReceived = functools.partial(self.passToRaftObject, node=node)
        conn.__onDisconnected = functools.partial(self.disconnectedCallback, node=node)
        conn.__onConnected = functools.partial(self.connectedCallback, node=node)
        self.__connections[node] = conn

        print(self.otherNodes)

    def send(self,partitionuid,node, message):
        print(" broker ka send calling ", message)
        message = {
                     '__parititionuid__':partitionuid,
                    '__raftmessage__':message
                    }
        self.__connections[node].send(message)

    def disconnectedCallback(self, node):
        for partition in node.__partitions:
            partition.__onNodeDisconnected(node)


    def connectedCallback(self, node):
        for partition in node.__partitions:
            partition.__onNodeConnected(node)
    


    #call from processconnections
    def passToRaftObject(self, node, name, raftMessage):
        self.__partitions[name].__onMessageReceived(node, raftMessage)

    def createNewPartition(self, name, otherBrokerNodes, db):
        #check if transport ready then only create partition
        # otherBrokerNodes = [self.otherNodes[nodeName] for nodeName in otherBrokers]
        
        self.__partitions[name] = Partition(name, self.__selfNode, otherBrokerNodes, self.send)

        if(self.__brokername == 'b1'):
            while self.__partitions[name]._getLeader() is None:
                pass
            print(self.__partitions[name]._getLeader())
            # self.__partitions[name].enqueue()
        

        
        if(db):
            #enter in the all_partitions table
            pass
        
    def enqueue(self, name, message):
        pass

    def dequeue(self, name, index):
        pass

    def hearbeat():
        pass


class Partition(SyncObj):
    def __init__(self, uid, selfbroker, otherbrokers, sendFunc):
        super().__init__(uid, selfbroker, otherbrokers, sendFunc)



    @replicated   
    def enqueue(self):
        print("hahahahahaha")
    
    def dequeue(self):
        pass

def on_new_client(clientsocket,addr):

    while True:
        msg = clientsocket.recv(1024)
        #do some checks and if msg == someWeirdSignal: break:
        print (addr, ' >> ', msg)
        
    clientsocket.close()

# class F:
#     def __init__(self,othernodes):
#         self.othernodes = othernodes

if __name__ == "__main__":
    # pass
    hostname = str(sys.argv[1])
    httpPort = str(sys.argv[2])
    raftPort = str(sys.argv[3])
    try:
        otherBrokers = [str(x) for x in sys.argv[4:]]
    except:
        otherBrokers = []

    print(socket.gethostbyname(hostname))

    b = Broker(hostname, httpPort, raftPort, otherBrokers)
    # print(b.otherNodes)
    
    if len(otherBrokers)==1:
        time.sleep(15)
        b.createNewPartition('chaljaabhai',[b.otherNodes['b1'], b.otherNodes['b3']], False)

    elif len(otherBrokers)==2:
       
        b.createNewPartition('chaljaabhai',[b.otherNodes['b1'], b.otherNodes['b2']], False)
    else:
        time.sleep(30)
        b.createNewPartition('chaljaabhai',[b.otherNodes['b2'],b.otherNodes['b3'] ], False)
        



