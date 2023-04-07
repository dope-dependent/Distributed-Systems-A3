from __future__ import print_function

from pysyncobj import SyncObj, replicated, replicated_sync

class ATM(SyncObj):
    OK = -3
    BAD_ID = -1
    NO_FUNDS = -2

    def __init__(self, selfNodeAddr, otherNodeAddrs):
        super(ATM, self).__init__(selfNodeAddr, otherNodeAddrs)
        self.__accounts = dict()

    
    @replicated_sync 
    def deposit(self, id, amount:int):
        if id in self.__accounts:
            self.__accounts[id] += amount
            return self.OK
        else:
            return self.BAD_ID
            
        
    @replicated_sync
    def withdraw(self, id, amount:int):
        if id in self.__accounts:
            if self.__accounts[id] >= amount:
                self.__accounts[id] -= amount
                return self.OK
            else:
                return self.NO_FUNDS
        else:
            return self.BAD_ID

    
    def balance(self, id):
        if id in self.__accounts:
            return self.__accounts[id]
        else:
            return self.BAD_ID

    
    @replicated_sync
    def transfer(self, id1, id2, amount:int):
        if id1 in self.__accounts and id2 in self.__accounts:
            if self.withdraw(id1, amount) == self.OK:
                self.deposit(id2, amount)
                return self.OK
            else:
                return self.NO_FUNDS
        else:   
            return self.BAD_ID
    
    def printer(self, resp):
        if resp == self.OK:
            print('Success') 
        elif resp == self.NO_FUNDS:
            print('Failure: No Funds')
        elif resp == self.BAD_ID:
            print('Failure: Invalid Account ID')
        else:
            print(f'Balance: {resp}')

    @replicated_sync
    def add(self, id):
        if id in self.__accounts:
            return self.BAD_ID
        else:
            self.__accounts[id] = 0
            return self.OK
    

    