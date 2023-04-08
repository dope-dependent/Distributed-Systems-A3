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

class Broker:
    def __init__(self, hostname, httpPort, raftPort, otherBrokers):
        hostAddress = socket.gethostbyname(hostname)
        # print(hostAddress)
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
        
        for ob in otherBrokers:
            if ob != self.__brokername:
                hostAddress = socket.gethostbyname(ob)
                # print(hostAddress)
                self.otherNodes[ob] = TCPNode(hostAddress+":"+self.__raftPort)  #add id to recognise
                node = self.otherNodes[ob]
                self.__connections[node] = self.__createConnection(node)
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

        for c in list(self.__connections.keys()):
            self.__connections[c].send({'__heartbeat__':monotonicTime()})
        
        for partition in list(self.partitions.keys()):
            if self.__brokername == 'b2' and int(monotonicTime() * 100) % 50 == 0:
                self.partitions['chaljaabhai'].enqueue()
            
            if int(monotonicTime() * 100) % 100 == 0:
                print(self.partitions['chaljaabhai'].counter, self.partitions['chaljaabhai']._getLeader())

            self.partitions[partition].onTick(0.05)
            # print(partition, self.partitions[partition]._getLeader())
        self.__poller.poll(0.05)

    
    def __createConnection(self, node): # Initiate connection with other brokers
        if node in self.__connections and self.__connections[node].state == CONNECTION_STATE.CONNECTED:
            return self.__connections[node]
        
        conn = TcpConnection(self.__brokername, 
                             self.__poller)  # TODO onNewConnectionCallback
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
        if self.partitions[partitionuid].counter<10:
            print(message)
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
            if self.partitions[name].counter<10:
                print(raftMessage)
            self.partitions[name].onMessageReceived(node, raftMessage)
        except:
            pass

    def createNewPartition(self, name, otherBrokerNodes):
        #check if transport ready then only create partition
        # otherBrokerNodes = [self.otherNodes[nodeName] for nodeName in otherBrokers]
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
        
        if(self.__brokername == 'b1'):
            while self.partitions[name]._getLeader() is None:
                pass
            # print("LEADER" + self.partitions[name]._getLeader())
            self.partitions[name].enqueue()
        

        
        # if(db):
        #     #enter in the all_partitions table
        #     pass
        
    def enqueue(self, name, message):
        pass

    def dequeue(self, name, index):
        pass

    def hearbeat():
        pass

    def getName(self):
        return self.__brokername


class Partition(SyncObj):
    def __init__(self, uid, selfbroker, otherbrokers, sendFunc):
        super().__init__(uid, selfbroker, otherbrokers, sendFunc)
        self.counter = 0

    @replicated   
    def enqueue(self):
        self.counter += 1
        time.sleep(0.5)
    
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
    an = ['b1', 'b2', 'b3']
    al = []
    for n in an:
        if b.getName() != n:
            al.append(n)

    b.createNewPartition('chaljaabhai', al)
    
        



