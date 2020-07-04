import random
import time

from components.host import Host
from components.network import Network
from objects.qubit import Qubit

def AliceProtocol(host, repeater):

    logalice = open("logs/alicelog.txt", "w")

    bit_count = 0
    secret_key = ""

    while bit_count < 4:

        time.sleep(1)

        bitcount = host.get_next_classical(repeater, wait=5)
        if bitcount is None:
            continue
        bitcount = int(bitcount.content)
        if bitcount != bit_count:
            secret_key = secret_key[0:bitcount]
            bit_count = bitcount

        host.send_classical(repeater, "ok")
        host.empty_classical()

        basis = host.get_next_classical(repeater, wait=5)
        if basis is None:
            logalice.write("Alice: Basis for bit %d is void\n"%bit_count)
            continue

        basis = int(basis.content)

        q = host.get_data_qubit(repeater, wait=5)

        if q is not None:
            print("Alice: Alice received EPR %d"%bit_count)
            logalice.write("Alice: Alice received EPR %d\n"%bit_count)
        else:
            print("Alice: Alice did not receive EPR %d"%bit_count)
            logalice.write("Alice: Alice did not receive EPR %d\n"%bit_count)
            continue

        # Entangled qubit received, perform BB84 measurement
        if basis:
            q.H()   # Randomly change basis
        bit = q.measure()
        # Communicate success to repeater
        ack_arrived = host.send_classical(repeater, bit, await_ack = True)

        if not ack_arrived:     # Bit void
            logalice.write("Alice: Measured bit %d void\n"%bit_count)
            continue

        bitcount = host.get_next_classical(repeater, wait=5)
        if bitcount is None:
            print("Alice: Bit count mismatch for %d, rewinding"%bit_count)
            logalice.write("Alice: Bit count mismatch for %d, rewinding\n"%bit_count)
            continue

        bit_count += 1

        # Append bit to keystream
        secret_key += str(bit)

    print("Alice: Secret Key : %s"%str(secret_key))
    logalice.write("Alice: Secret Key : %s"%str(secret_key))

    logalice.close()

def RepeaterProtocol(host, alice, bob):

    logrepeater = open("logs/repeater.txt", "w")

    bit_count = 0

    while bit_count < 4:

        host.empty_classical()
        time.sleep(1)

        # Synchronize with Alice and Bob
        host.send_broadcast(str(bit_count))
        wait = True
        messages = []
        while wait:
            messages = host.classical
            if len(messages) == 2:
                wait = False
                host.empty_classical()
                        
        basis = random.randint(0, 1)
        ack_arrived = host.send_classical(alice, basis, await_ack = True)
        if not ack_arrived:
            logrepeater.write("Repeater: Failed to send basis %d to Alice\n"%bit_count)
            print("Repeater: Failed to send basis %d to Alice"%bit_count)
            continue
        ack_arrived = host.send_classical(bob, basis, await_ack = True)
        if not ack_arrived:
            logrepeater.write("Repeater: Failed to send basis %d to Bob\n"%bit_count)
            print("Repeater: Failed to send basis %d to Bob"%bit_count)
            continue

        # Generate two qubits
        q_alice = Qubit(host)
        q_mem_alice = Qubit(host)

        # Entangle the two qubits to create an entangled pair
        q_alice.H()
        q_alice.cnot(q_mem_alice)

        # Send one of the qubits of the entangled state to Alice
        q_alice_id, ack_arrived = host.send_qubit(alice, q_alice, await_ack=True)

        if not ack_arrived:
            # Alice did not receive qubit
            logrepeater.write("Repeater: Alice did not receive EPR %d\n"%bit_count)
            print("Repeater: Alice did not receive EPR %d"%bit_count)
            #q_alice.measure()
            q_mem_alice.measure()
            continue
        else:
            alice_bit = host.get_next_classical(alice, wait=5)
            if alice_bit is not None:
                logrepeater.write("Repeater: Alice received entangled qubit %d and measured %s\n"%(bit_count, str(alice_bit.content)))
                print("Repeater: Alice received entangled qubit %d and measured %s"%(bit_count, str(alice_bit.content)))
            else:
                continue
        
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
            print("Repeater: Bob did not receive EPR %d"%bit_count)
            #q_bob.measure()
            q_mem_bob.measure()
            q_mem_alice.measure()
            continue
        else:
            bob_bit = host.get_next_classical(bob, wait=5)
            if bob_bit is not None:
                logrepeater.write("Repeater: Bob received entangled qubit %d and measured %s\n"%(bit_count, str(bob_bit.content)))
                print("Repeater: Bob received entangled qubit %d and measured %s"%(bit_count, str(bob_bit.content)))
            else:
                continue

        # Both Alice and Bob have successfully made BB84 measurements
        # Perform Bell state measurement on the two qubits present in the memory

        q_mem_alice.cnot(q_mem_bob)
        q_mem_alice.H()
        alice_bit = q_mem_alice.measure()
        bob_bit = q_mem_bob.measure()

        # Send results of measurement to Bob
        ack_arrived = host.send_classical(bob, "%d:%d"%(alice_bit, bob_bit), await_ack = True)

        if not ack_arrived:
            logrepeater.write("Repeater: Bell State Measurement %d void\n"%bit_count)
            print("Repeater: Bell State Measurement %d void"%bit_count)
            q_mem_alice.release()
            q_mem_bob.release()
            continue
        else:
            # Communicate Bob's success to Alice
            ack_arrived = host.send_classical(alice, str(bit_count), await_ack=True)
            if not ack_arrived:
                print("Repeater: Alice did not acknowledge Bob's success for bit %d"%bit_count)
                logrepeater.write("Repeater: Alice did not acknowledge Bob's success for bit %d\n"%bit_count)
                continue

        bit_count += 1

    logrepeater.close()

def BobProtocol(host, repeater):

    logbob = open("logs/boblog.txt", "w")

    bit_count = 0
    secret_key = ""

    while bit_count < 4:

        time.sleep(1)

        # Synchronize with repeater
        bitcount = host.get_next_classical(repeater, wait=5)
        if bitcount is None:
            continue
        bitcount = int(bitcount.content)
        if bitcount != bit_count:
            secret_key = secret_key[0:bitcount]
            bit_count = bitcount

        host.send_classical(repeater, "ok")
        host.empty_classical()

        basis = host.get_next_classical(repeater, wait=5)
        if basis is None:
            logbob.write("Bob: Basis for bit %d is void\n"%bit_count)
            print("Bob: Basis for bit %d is void"%bit_count)
            continue
        basis = int(basis.content)

        q = host.get_data_qubit(repeater, wait=5)

        if q is not None:
            logbob.write("Bob: Bob received EPR %d\n"%bit_count)
            print("Bob: Bob received EPR %d"%bit_count)
        else:
            logbob.write("Bob: Bob did not receive EPR %d\n"%bit_count)
            print("Bob: Bob did not receive EPR %d"%bit_count)
            continue

        # Entangled qubit received, perform BB84 measurement
        if basis:
            q.H()   # Randomly change basis
        bit = q.measure()
        # Communicate success to repeater
        ack_arrived = host.send_classical(repeater, bit, await_ack = True)

        if not ack_arrived:     # Bit void
            logbob.write("Bob: Measured bit %d void"%bit_count)
            print("Bob: Measured bit %d void"%bit_count)
            continue

        # Receive Bell state measurement results from repeater
        classical_data = host.get_next_classical(repeater, wait=5)
        if classical_data is None:
            logbob.write("Bob: BSM measurements void for bit %d\n"%bit_count)
            print("Bob: BSM measurements void for bit %d"%bit_count)
            continue

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
    repeater.add_connection('Alice', 10, 0.1)
    repeater.add_connection('Bob', 10, 0.1)
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