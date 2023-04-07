from ATM import ATM
import sys

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: %s self_port partner1_port partner2_port ...' % sys.argv[0])
        sys.exit(-1)

    port = int(sys.argv[1])
    partners = ['localhost:%d' % int(p) for p in sys.argv[2:]]
    o = ATM('localhost:%d' % port, partners)
    n = 0
    old_value = -1
    while True:
        if o._getLeader() is not None:
            print('Leader node - ', o._getLeader())
            print('Press [1] for Withdrawal')
            print('Press [2] for Deposit')
            print('Press [3] for Balance Enquiry')
            print('Press [4] for Money Transfer')
            print('Press [5] to Add New Account')

            inp = input('Enter your choice: ')
            inp = int(inp)
            if inp == 1:
                inp = input('Enter Account ID: ')
                inp2 = input('Enter Amount: ')
                resp = o.withdraw(inp, int(inp2))
            
            elif inp == 2:
                inp = input('Enter Account ID: ')
                inp2 = input('Enter Amount: ')
                resp = o.deposit(inp, int(inp2))
            
            elif inp == 3:
                inp = input('Enter Account ID: ')
                resp = o.balance(inp)
            
            elif inp == 4:
                inp = input('Enter Sender Account ID: ')
                inp2 = input('Enter Receiver Account ID: ')
                inp3 = input('Enter Amount: ')
                resp = o.transfer(inp, inp2, int(inp3))
            
            elif inp == 5:
                inp = input('Enter Account ID: ')
                resp = o.add(inp)
            
            o.printer(resp)
        



        

