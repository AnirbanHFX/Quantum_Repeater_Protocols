import random
import time

from components.host import Host
from components.network import Network
from objects.qubit import Qubit

def AliceProtocol(host, repeater):

    logalice = open("logs/alicelog.txt", "w")

    bit_count = 0
    secret_key = ""

    while bit_count < 16:

        basis = host.get_next_classical(repeater)
        basis = int(basis.content)

        q = host.get_data_qubit(repeater, wait=10)

        if q is not None:
            #print("Alice: Alice received EPR")
            logalice.write("Alice: Alice received EPR %d\n"%bit_count)
        else:
            #print("Alice: Alice did not receive EPR")
            logalice.write("Alice: Alice did not receive EPR %d\n"%bit_count)
            logalice.close()
            return

        # Entangled qubit received, perform BB84 measurement
        if basis:
            q.H()   # Randomly change basis
        bit = q.measure()
        # Communicate success to repeater
        host.send_classical(repeater, bit)

        bit_count += 1

        # Append bit to keystream
        secret_key += str(bit)

    print("Alice: Secret Key : %s"%str(secret_key))
    logalice.write("Alice: Secret Key : %s"%str(secret_key))

    logalice.close()

def RepeaterProtocol(host, alice, bob):

    logrepeater = open("logs/repeater.txt", "w")

    bit_count = 0

    while bit_count < 16:

        # Generate two qubits
        q_alice = Qubit(host)
        q_mem_alice = Qubit(host)

        # Entangle the two qubits to create an entangled pair
        q_alice.H()
        q_alice.cnot(q_mem_alice)

        basis = random.randint(0, 1)
        host.send_classical(alice, basis)
        host.send_classical(bob, basis)

        # Send one of the qubits of the entangled state to Alice
        q_alice_id, ack_arrived = host.send_qubit(alice, q_alice, await_ack=True)

        if not ack_arrived:
            # Alice did not receive qubit
            #print("Repeater: Alice did not receive EPR")
            logrepeater.write("Repeater: Alice did not receive EPR %d\n"%bit_count)
        else:
            alice_bit = host.get_next_classical(alice)
            #print("Repeater: Alice received entangled qubit and measured %s"%str(alice_bit.content))
            logrepeater.write("Repeater: Alice received entangled qubit %d and measured %s\n"%(bit_count, str(alice_bit.content)))
        
        # Generate two qubits
        q_bob = Qubit(host)
        q_mem_bob = Qubit(host)

        # Entangle the two qubits to create an entangled pair
        q_bob.H()
        q_bob.cnot(q_mem_bob)

        q_bob_id, ack_arrived = host.send_qubit(bob, q_bob, await_ack=True)

        if not ack_arrived:
            # Bob did not receive qubit
            #print("Repeater: Bob did not receive EPR")
            logrepeater.write("Repeater: Bob did not receive EPR %d\n"%bit_count)
        else:
            bob_bit = host.get_next_classical(bob)
            #print("Repeater: Bob received entangled qubit and measured %s"%str(bob_bit.content))
            logrepeater.write("Repeater: Bob received entangled qubit %d and measured %s\n"%(bit_count, str(bob_bit.content)))

        # Both Alice and Bob have successfully made BB84 measurements
        # Perform Bell state measurement on the two qubits present in the memory

        q_mem_alice.cnot(q_mem_bob)
        q_mem_alice.H()
        alice_bit = q_mem_alice.measure()
        bob_bit = q_mem_bob.measure()

        # Send results of measurement to Bob
        host.send_classical(bob, "%d:%d"%(alice_bit, bob_bit))

        bit_count += 1

    logrepeater.close()

def BobProtocol(host, repeater):

    logbob = open("logs/boblog.txt", "w")

    bit_count = 0
    secret_key = ""

    while bit_count < 16:

        basis = host.get_next_classical(repeater)
        basis = int(basis.content)

        q = host.get_data_qubit(repeater, wait=10)

        if q is not None:
            #print("Bob: Bob received EPR")
            logbob.write("Bob: Bob received EPR %d\n"%bit_count)
        else:
            #print("Bob: Bob did not receive EPR")
            logbob.write("Bob: Bob did not receive EPR %d\n"%bit_count)
            logbob.close()
            return

        # Entangled qubit received, perform BB84 measurement
        if basis:
            q.H()   # Randomly change basis
        bit = q.measure()
        # Communicate success to repeater
        host.send_classical(repeater, bit)

        # Receive Bell state measurement results from repeater
        classical_data = host.get_next_classical(repeater)
        classical_data = classical_data.content.split(':')

        # Flip bit according to BSM result and basis of measurement
        if not basis:
            if int(classical_data[1]) == 1:
                bit = not bit
        else:
            if int(classical_data[0]) == 1:
                bit = not bit

        # Append bit to keystream
        secret_key += str(int(bit))

        bit_count += 1

    print("Bob:   Secret Key : %s"%str(secret_key))
    logbob.write("Bob: Secret Key : %s\n"%str(secret_key))

    logbob.close()

def main() :

    network = Network.get_instance()
    nodes = ['Alice', 'R', 'Bob']
    network.use_ent_swap = True
    network.start(nodes)

    alice = Host('Alice')
    alice.add_connection('R')
    alice.max_ack_wait = 5
    alice.start()

    repeater = Host('R')
    repeater.add_connection('Alice')
    repeater.add_connection('Bob')
    repeater.max_ack_wait = 5
    repeater.start()

    bob = Host('Bob')
    bob.add_connection('R')
    bob.max_ack_wait = 5
    bob.start()

    network.add_host(alice)
    network.add_host(repeater)
    network.add_host(bob)

    alice.run_protocol(AliceProtocol, (repeater.host_id,))
    repeater.run_protocol(RepeaterProtocol, (alice.host_id, bob.host_id))
    bob.run_protocol(BobProtocol, (repeater.host_id,))

if __name__ == '__main__':
    main()