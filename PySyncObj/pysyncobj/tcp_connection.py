import time
import socket
from sys import platform
import zlib
import struct

import pysyncobj.pickle as pickle
import pysyncobj.win_inet_pton

from .poller import POLL_EVENT_TYPE
from .monotonic import monotonic as monotonicTime


class CONNECTION_STATE:
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2

def _getAddrType(addr):
    try:
        socket.inet_aton(addr)
        return socket.AF_INET
    except socket.error:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, addr)
        return socket.AF_INET6
    except socket.error:
        pass
    raise Exception('unknown address type')

import socket

def set_keepalive_linux(sock, after_idle_sec=1, interval_sec=3, max_fails=5):
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, after_idle_sec)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, interval_sec)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, max_fails)

def set_keepalive_osx(sock, after_idle_sec=1, interval_sec=3, max_fails=5):
    TCP_KEEPALIVE = 0x10
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    sock.setsockopt(socket.IPPROTO_TCP, TCP_KEEPALIVE, interval_sec)

def set_keepalive_windows(sock, after_idle_sec=1, interval_sec=3, max_fails=5):
    sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, after_idle_sec * 1000, interval_sec * 1000))

def set_keepalive(sock, after_idle_sec=1, interval_sec=3, max_fails=5):
    if platform == "linux" or platform == "linux2":
        set_keepalive_linux(sock, after_idle_sec, interval_sec, max_fails)
    elif platform == "darwin":
        set_keepalive_osx(sock, after_idle_sec, interval_sec, max_fails)
    elif platform == "win32":
        set_keepalive_windows(sock, after_idle_sec, interval_sec, max_fails)


class TcpConnection(object):

    def __init__(self, brokername, poller, onNewConnectionCallback = None, 
                 onMessageReceived = None, 
                 onConnected = None, 
                 onDisconnected = None,
                 socket=None, timeout=10.0, sendBufferSize = 2 ** 13, recvBufferSize = 2 ** 13,
                 keepalive=None):
        self.__brokername = brokername
        self.sendRandKey = None
        self.recvRandKey = None
        self.recvLastTimestamp = 0
        self.encryptor = None
        self.__onNewConnectionCallback = onNewConnectionCallback
        self.__socket = socket
        self.__readBuffer = bytes()
        self.__writeBuffer = bytes()
        self.__lastReadTime = monotonicTime()
        self.__timeout = timeout
        self.__poller = poller
        self.__keepalive = keepalive
        if socket is not None:
            self.__socket = socket
            self.__fileno = socket.fileno()
            self.__state = CONNECTION_STATE.CONNECTED
            self.setSockoptKeepalive()
            self.__poller.subscribe(self.__fileno,
                                     self.__processConnection,  # Callback whenever a message comes
                                     POLL_EVENT_TYPE.READ | POLL_EVENT_TYPE.WRITE | POLL_EVENT_TYPE.ERROR)
        else:
            self.__state = CONNECTION_STATE.DISCONNECTED
            self.__fileno = None
            self.__socket = None
        

        self.onConnected = onConnected                       # Changed to public
        self.onDisconnected = onDisconnected                 # Changed to public
        self.__sendBufferSize = sendBufferSize
        self.__recvBufferSize = recvBufferSize
        self.onMessageReceived = onMessageReceived           # Changed to public

    def setSockoptKeepalive(self):
        if self.__socket is None:
            return
        if self.__keepalive is None:
            return
        set_keepalive(
            self.__socket,
            self.__keepalive[0],
            self.__keepalive[1],
            self.__keepalive[2],
        )

    def setOnConnectedCallback(self, onConnected):
        self.onConnected = onConnected

    def setOnMessageReceivedCallback(self, onMessageReceived):
        self.onMessageReceived = onMessageReceived

    def setOnDisconnectedCallback(self, onDisconnected):
        self.onDisconnected = onDisconnected

    def connect(self, host, port):
        if host is None:
            return False
        self.__state = CONNECTION_STATE.DISCONNECTED
        self.__fileno = None
        self.__socket = socket.socket(_getAddrType(host), socket.SOCK_STREAM)
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.__sendBufferSize)
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.__recvBufferSize)
        self.__socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.setSockoptKeepalive()
        self.__socket.setblocking(0)
        self.__readBuffer = bytes()
        self.__writeBuffer = bytes()
        self.__lastReadTime = monotonicTime()

        try:
            self.__socket.connect((host, port))
            
        except socket.error as e:
            # print(e)
            if e.errno not in (socket.errno.EINPROGRESS, socket.errno.EWOULDBLOCK):
                return False
        self.__fileno = self.__socket.fileno()
        self.__state = CONNECTION_STATE.CONNECTING
        self.__poller.subscribe(self.__fileno,
                                 self.__processConnection,
                                 POLL_EVENT_TYPE.READ | POLL_EVENT_TYPE.WRITE | POLL_EVENT_TYPE.ERROR)
        return True

    def send(self, message):
        # print("connection ka send calling", message)
        if self.sendRandKey:
            message = (self.sendRandKey, message)
        data = zlib.compress(pickle.dumps(message), 3)
        if self.encryptor:
            data = self.encryptor.encrypt_at_time(data, int(monotonicTime()))
        data = struct.pack('i', len(data)) + data
        self.__writeBuffer += data
        # print("send try kar rha hu bro")
        self.__trySendBuffer()
        # print("send ho gaya bro")

    def fileno(self):
        return self.__fileno

    def disconnect(self):
        needCallDisconnect = False
        if self.onDisconnected is not None and self.__state != CONNECTION_STATE.DISCONNECTED:
            needCallDisconnect = True
        self.sendRandKey = None
        self.recvRandKey = None
        self.recvLastTimestamp = 0
        if self.__socket is not None:
            self.__socket.close()
            self.__socket = None
        if self.__fileno is not None:
            self.__poller.unsubscribe(self.__fileno)
            self.__fileno = None
        self.__writeBuffer = bytes()
        self.__readBuffer = bytes()
        self.__state = CONNECTION_STATE.DISCONNECTED
        if needCallDisconnect:
            self.onDisconnected()

    def getSendBufferSize(self):
        return len(self.__writeBuffer)

    def __processConnection(self, descr, eventType):
        # print("yeh ho rha hai", eventType)
        # print(POLL_EVENT_TYPE.ERROR)
        # print(POLL_EVENT_TYPE.WRITE)
        # print(POLL_EVENT_TYPE.READ)

        
        poller = self.__poller
        if descr != self.__fileno:
            # print('socket 1')
            poller.unsubscribe(descr)
            return
            
        if eventType & POLL_EVENT_TYPE.ERROR:
            # print('socket 2')
            self.disconnect()
            return

        self.__processConnectionTimeout()
        
        if self.state == CONNECTION_STATE.DISCONNECTED:
            # print('socket 3')
            return

        if eventType & POLL_EVENT_TYPE.READ or eventType & POLL_EVENT_TYPE.WRITE:
            if self.__socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR):
                # print('socket 4')
                self.disconnect()
                return

            if self.__state == CONNECTION_STATE.CONNECTING:
                # print('socket 5')
                if self.onConnected is not None:
                    self.onConnected()
                if self.__state == CONNECTION_STATE.DISCONNECTED:
                    return
                self.__state = CONNECTION_STATE.CONNECTED
                self.__lastReadTime = monotonicTime()
                return

        if eventType & POLL_EVENT_TYPE.WRITE:
            # print('socket 6')
            self.__trySendBuffer()
            if self.__state == CONNECTION_STATE.DISCONNECTED:
                return
            event = POLL_EVENT_TYPE.READ | POLL_EVENT_TYPE.ERROR
            if len(self.__writeBuffer) > 0:
                event |= POLL_EVENT_TYPE.WRITE
            poller.subscribe(descr, self.__processConnection, event)

        if eventType & POLL_EVENT_TYPE.READ:
            # print('socket 7')
            # print("being called", self.__state)
            self.__tryReadBuffer()
            # print("tried reading buffer")
            if self.__state == CONNECTION_STATE.DISCONNECTED:
                return
            while True:
                message = self.__processParseMessage()
                if message is None:
                    break
                
                if '__query__' in message:
                    if message['__query__'] == 'hostname':
                        self.send({'__hostname__': self.__brokername})  
                    
                if '__hostname__' in message:
                    # print('Got __hostname__ !!')
                    self.__onNewConnectionCallback(message['__hostname__'], self)
               
                if '__raftmessage__' in message:
                    # print('Got __raftmessage__ !!')
                    # print(message)
                    self.onMessageReceived(message['__partitionuid__'], message['__raftmessage__'])
                
                if self.__state == CONNECTION_STATE.DISCONNECTED:
                    return

    def __processConnectionTimeout(self):
        # print(monotonicTime())
        # print(self.__lastReadTime)
        # print(self.__timeout)
        if monotonicTime() - self.__lastReadTime > self.__timeout:
            # print('process connection timeout disconnect')
            self.disconnect()
            return

    def __trySendBuffer(self):
        self.__processConnectionTimeout()
        if self.state == CONNECTION_STATE.DISCONNECTED:
            return
        while self.__processSend():
            # print("in while __trySendBuffer")
            pass
        # print("out of while loop __trySendBuffer")

    def __processSend(self):
        if not self.__writeBuffer:
            return False
        try:
            # print("self.__socket.send kar rha hu")
            res = self.__socket.send(self.__writeBuffer)
            if res < 0:
                # print('procesSend returns error disconnect')
                self.disconnect()
                return False
            if res == 0:
                return False
            self.__writeBuffer = self.__writeBuffer[res:]
            return True
        except socket.error as e:
            # print('procesSend returns error disconnect', e)
            if e.errno not in (socket.errno.EAGAIN, socket.errno.EWOULDBLOCK):
                self.disconnect()
            return False

    def __tryReadBuffer(self):
        while self.__processRead():
            pass
        self.__lastReadTime = monotonicTime()
        # print("tr read buffer")

    def __processRead(self):
        try:
            incoming = self.__socket.recv(self.__recvBufferSize)
        except socket.error as e:
            # print(e)
            if e.errno not in (socket.errno.EAGAIN, socket.errno.EWOULDBLOCK):
                # print('processRead returns error disconnect', e)
                self.disconnect()
            return False
        # print("out of the blovking call")
        if self.__socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR):
            # print('processRead bad socket')
            self.disconnect()
            return False
        if not incoming:
            # print('processRead not incoming')
            self.disconnect()
            return False
        self.__readBuffer += incoming
        # print("returning true")
        return True

    def __processParseMessage(self):
        if len(self.__readBuffer) < 4:
            return None
        l = struct.unpack('i', self.__readBuffer[:4])[0]
        if len(self.__readBuffer) - 4 < l:
            return None
        data = self.__readBuffer[4:4 + l]
        try:
            if self.encryptor:
                dataTimestamp = self.encryptor.extract_timestamp(data)
                assert dataTimestamp >= self.recvLastTimestamp
                self.recvLastTimestamp = dataTimestamp
                # Unfortunately we can't get a timestamp and data in one go
                data = self.encryptor.decrypt(data)
            message = pickle.loads(zlib.decompress(data))
            if self.recvRandKey:
                randKey, message = message
                assert randKey == self.recvRandKey
        except:
            # Why no logging of security errors?
            self.disconnect()
            return None
        self.__readBuffer = self.__readBuffer[4 + l:]
        return message

    @property
    def state(self):
        return self.__state
