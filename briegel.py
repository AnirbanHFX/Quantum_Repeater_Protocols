import string
import time

from operator import attrgetter

from components.host import Host
from components.network import Network
from objects.qubit import Qubit

def AliceProtocol(host, receiver, Y, M):

    logalice = open("logs/alicelog.txt", "w")

    epr_list = []
    
    for _ in range(Y*M):

        success = False
        while success == False:

            print('Alice: Sending EPR pair %d'%_)
            logalice.write('Alice: Sending EPR pair %d\n'%_)
            epr_id, ack_arrived = host.send_epr(receiver, await_ack=True, fidelity=host.fidelity)
            if ack_arrived:
                q = host.get_epr(receiver, q_id=epr_id)
                if q is not None:
                    host.send_ack(receiver, _)
                    ack_arrived = host.await_ack(_, receiver)
                    if ack_arrived:
                        print('Alice: EPR pair %d shared'%_)
                        logalice.write('Alice: EPR pair %d shared\n'%_)
                        time.sleep(5)
                        success = True
                        #print('Alice: fidelity = %f'%q.fidelity)
                        epr_list.append(q.id)
                    else:
                        print('Alice: EPR pair %d failed, trying again'%_)
                        logalice.write('Alice: EPR pair %d failed, trying again\n'%_)
                else:
                    print('Alice: EPR pair %d failed, trying again'%_)
                    logalice.write('Alice: EPR pair %d failed, trying again\n'%_)
            else:
                print('Alice: EPR pair %d failed, trying again'%_)
                logalice.write('Alice: EPR pair %d failed, trying again\n'%_)

    print('Alice: Over and Out')
    logalice.close()
    return

def BobProtocol(host, sender, Y, M):

    logbob = open("logs/boblog.txt", "w")

    epr_list = []

    for _ in range(Y*M):

        success = False
        while success == False:

            q = host.get_epr(sender, wait=10)
            if q is not None:
                ack_arrived = host.await_ack(_, sender)
                if ack_arrived:
                    host.send_ack(sender, _)
                    print('Bob: Received EPR pair %d'%_)
                    logbob.write('Bob: Received EPR pair %d\n'%_)
                    epr_list.append(q.id)
                    success = True
                else:
                    print('Bob: EPR pair %d not received, trying again'%_)
                    logbob.write('Bob: EPR pair %d not received, trying again\n'%_)
            else:
                print('Bob: EPR pair %d not received, trying again'%_)
                logbob.write('Bob: EPR pair %d not received, trying again\n'%_)

    print('Bob: Over and Out')
    logbob.close()
    return

def checksuccess(messages, text):
    if len(messages) > 0:
        for message in messages:
            temp = message.content
            if str(temp).strip() != str(text).strip():
                print('Message = %s'%temp)
                return 0
    return 1

def RepeaterProtocol(host, sender, receiver, self_id, repeaterexp, Y, M):

    logname = str('logs/')+str('repeater')+str(self_id)+str('.txt')
    logrep = open(logname, 'w')

    def receive_epr(host, sender, seq, self_id, logrep):

        q_left = host.get_epr(sender, wait = 5)
        if q_left is not None:
            ack_arrived = host.await_ack(seq, sender)
            if ack_arrived:
                print('Repeater %d: Received EPR pair %d'%(self_id, seq))
                logrep.write('Repeater %d: Received EPR pair %d\n'%(self_id, seq))
                host.send_ack(sender, seq)
                host.send_broadcast(str('epr'))
                return q_left
            else:
                print('Repeater %d: EPR pair %d not received, trying again'%(self_id, seq))
                logrep.write('Repeater %d: EPR pair %d not received, trying again\n'%(self_id, seq))
                return None
        else:
            print('Repeater %d: EPR pair %d not received, trying again'%(self_id, seq))
            logrep.write('Repeater %d: EPR pair %d not received, trying again\n'%(self_id, seq))
            return None

    def send_epr(host, receiver, seq, self_id, epr_list, logrep):

        assert epr_list is not list

        print('Repeater %d: Sending EPR pair %d'%(self_id, seq))
        epr_id, ack_arrived = host.send_epr(receiver, await_ack=True, fidelity=host.fidelity)

        if ack_arrived:
            q_right = host.get_epr(receiver, q_id = epr_id)
            if q_right is not None:
                host.send_ack(receiver, seq)
                ack_arrived = host.await_ack(seq, receiver)
                if ack_arrived:
                    print('Repeater %d: EPR pair %d shared'%(self_id, seq))
                    logrep.write('Repeater %d: EPR pair %d shared\n'%(self_id, seq))
                    epr_list.append(epr_id)
                    return q_right
                else:
                    print('Repeater %d: EPR pair %d failed, trying again'%(self_id, seq))
                    logrep.write('Repeater %d: EPR pair %d failed, trying again\n'%(self_id, seq))
                    return None
            else:
                print('Repeater %d: EPR pair %d failed, trying again'%(self_id, seq))
                logrep.write('Repeater %d: EPR pair %d failed, trying again\n'%(self_id, seq))
                return None
        else:
            print('Repeater %d: EPR pair %d failed, trying again'%(self_id, seq))
            logrep.write('Repeater %d: EPR pair %d failed, trying again\n'%(self_id, seq))
            return None

    def send_teleport(host, receiver, q, self_id, logrep):
        tele_ack_arrived = host.send_teleport(receiver, q, await_ack = True)
        if tele_ack_arrived:
            print('Repeater %d: Teleportation successful'%self_id)
            logrep.write('Repeater %d: Teleportation successful\n'%self_id)
            host.send_broadcast(str('tel'))
            return True
        else:
            print('Repeater %d: Teleportation failed, trying again'%self_id)
            logrep.write('Repeater %d: Teleportation failed, trying again\n'%self_id)
            return False

    def distill(left_list, right_list, epr_list, Y, M):

        assert left_list is not list
        assert right_list is not list
        assert epr_list is not list

        new_left_list = []
        new_right_list = []
        new_epr_list = []

        for i in range(Y):
            q_left_max = max(left_list[i*M:(i+1)*M+1], key=attrgetter('fidelity'))
            q_right_max = max(right_list[i*M:(i+1)*M+1], key=attrgetter('fidelity'))
            new_left_list.append(q_left_max)
            new_right_list.append(q_right_max)
            if q_right_max.id in epr_list:
                new_epr_list.append(q_right_max.id)
            else:
                raise Exception('EPR id mismatch')

        left_list[:] = new_left_list
        right_list[:] = new_right_list
        epr_list[:] = new_epr_list

        M = 2
        Y = int(Y/M)
        if Y == 0:
            M = 1
            Y = 1
        return Y, M

    
    num_repeaters = 2**repeaterexp-1
    repeaterlist = list(range(num_repeaters))
    messages = []
    q_left_list = []
    q_right_list = []
    epr_list = []

    for _ in range(Y*M):

        q_left = None
        q_right = None

        while q_left is None or q_right is None:
            if self_id%2:
                if q_left is None:
                    q_left = receive_epr(host, sender, _, self_id, logrep)
                if q_right is None:
                    q_right = send_epr(host, receiver, _, self_id, epr_list, logrep)
            else:
                if q_right is None:
                    q_right = send_epr(host, receiver, _, self_id, epr_list, logrep)
                if q_left is None:
                    q_left = receive_epr(host, sender, _, self_id, logrep)

        while(len(messages)<num_repeaters-1):
            messages = host.classical
            if checksuccess(messages, 'epr') == 0:
                print('Repeater %d: Some repeaters failed to establish EPR, exiting'%self_id)
                logrep.write('Repeater %d: Some repeaters failed to establish EPR, exiting\n'%self_id)
                return

        print('Repeater %d: All repeaters have successfully established EPR pair %d'%(self_id, _))
        logrep.write('Repeater %d: All repeaters have successfully established EPR pair %d\n'%(self_id, _))

        host.empty_classical()

        q_left_list.append(q_left)
        q_right_list.append(q_right)

    # if self_id == 0:
    #     for q in q_left_list:
    #         print('Repeater 0: fidelity = %f'%q.fidelity)

    # Y, M = distill(q_left_list, q_right_list, epr_list, Y, M)
    # if self_id == 0 or self_id == 1:
    #     logrep.write('Q_Lefts - \n')
    #     for q in q_left_list:
    #         logrep.write('%s\n'%q.id)
    #     logrep.write('Q_Rights - \n')
    #     for q in q_right_list:
    #         logrep.write('%s\n'%q.id)
    #     logrep.write('EPRs - \n')
    #     for epr in epr_list:
    #         logrep.write('%s\n'%epr)

    while(num_repeaters > 0):
        Y, M = distill(q_left_list, q_right_list, epr_list, Y, M)
        for i in range(0, num_repeaters, 2):
            for _ in range(Y*M):
                success = False
                host.empty_classical()
                if i < len(repeaterlist) and self_id == repeaterlist[i]:
                    q_left_list[_].fidelity = (1-2*q_left_list[_].fidelity+4*q_left_list[_].fidelity*q_left_list[_].fidelity)/3
                    while success == False:
                        try:
                            success = send_teleport(host, receiver, q_left_list[_], self_id, logrep)
                        except:
                            print("Qubit lost, transmission failed")
                            logrep.write("Qubit lost, transmission failed")
                            logrep.close
                            return
                    #host.send_classical(sender, str(q_left_list[_].id+'\n'+str(q_left_list[_].fidelity)))
        removal = []
        for i in range(0, num_repeaters, 2):
            removal.append(repeaterlist[i])
        for removablerepeater in removal:
            repeaterlist.remove(removablerepeater)
        num_repeaters = int(num_repeaters/2)

    logrep.close()

    outputlog = open("logs/output.txt", "a+")
    outputlog.write("%f\n"%host.get_network_time)
    print("Completion at time = %f"%host.get_network_time)
    outputlog.close()

    print('Repeater %d: Success, Over and Out'%self_id)
    return

def main():

    Y = 2
    M = 2

    network = Network.get_instance()
    nodes = ['Alice','C0','Bob']
    network.use_ent_swap = True
    network.start(nodes)
#0.01549
    alice = Host('Alice')
    alice.add_connection('C0', 100)
    alice.coherence_time = 1
    alice.max_ack_wait = 5
    alice.start()

    repeater0 = Host('C0')
    repeater0.add_connection('Alice', 100)
    repeater0.add_connection('Bob', 100)
    repeater0.coherence_time = 1
    repeater0.max_ack_wait = 5
    repeater0.start()

    # repeater1 = Host('C1')
    # repeater1.add_connection('C0')
    # repeater1.add_connection('C2')
    # repeater1.max_ack_wait = 5
    # repeater1.start()

    # repeater2 = Host('C2')
    # repeater2.add_connection('C1')
    # repeater2.add_connection('Bob')
    # repeater2.max_ack_wait = 5
    # repeater2.start()

    bob = Host('Bob')
    bob.add_connection('C0', 100)
    bob.coherence_time = 1
    bob.max_ack_wait = 5
    bob.start()

    network.add_host(alice)
    network.add_host(repeater0)
    #network.add_host(repeater1)
    #network.add_host(repeater2)
    network.add_host(bob)
    
    t1 = alice.run_protocol(AliceProtocol, (repeater0.host_id, Y, M))
    t2 = repeater0.run_protocol(RepeaterProtocol, (alice.host_id, bob.host_id, 0, 1, Y, M))
    #repeater1.run_protocol(RepeaterProtocol, (repeater0.host_id, repeater2.host_id, 1, 2, Y, M))
    #repeater2.run_protocol(RepeaterProtocol, (repeater1.host_id, bob.host_id, 2, 2, Y, M))
    t3 = bob.run_protocol(BobProtocol, (repeater0.host_id, Y, M))

    t1.join()
    t2.join()
    t3.join()

    network.stop(True)

if __name__ == '__main__':

    main()