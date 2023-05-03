import argparse
from socket import *
import headers
import threading
import sys
import os
import queue

parser = argparse.ArgumentParser(description="TCP connection that can run in server and client mode")

parser.add_argument('-s', '--server', action='store_true')
parser.add_argument('-c', '--client', action='store_true')
parser.add_argument('-b', '--bind', type=str)
parser.add_argument('-p', '--port', type=int)
parser.add_argument('-f', '--file', type=str)

args = parser.parse_args()

header_format = '!IIHH'
buffer = 1460

if args.server and args.client:
    print("Can't run server and client at the same time")
    sys.exit()

if not args.server and not args.client:
    print("You have to start in either client or server mode")
    sys.exit()

if args.server:
    serverSocket = socket(AF_INET, SOCK_DGRAM)
    serverSocket.bind((args.bind, args.port))
    print("ip: ", args.bind, " port: ", args.port)
    data, addr = serverSocket.recvfrom(buffer)
    print("Received file: ", data.strip())
    f = open("test2.jpg", "wb")

    # Receive the file size and send an ACK
    file_size = len(data)
    serverSocket.sendto(b"ACK", addr)
    print("File size received:", file_size)

    # Create a buffer to hold packets that have been received but not yet
    # written to the file
    packets_buffer = []

    # Create a thread to handle ACKs sent by the client
    def ack_handler():

        while True:
            try:
                # Wait for an ACK packet from the client
                ack_packet, addr = serverSocket.recvfrom(1024)
                ack_seq, _, ack_flags, _ = headers.parse_header(ack_packet[:12])

                # If the ACK is for the next packet in the buffer, remove it
                # from the buffer and continue sending the remaining packets
                if ack_seq == packets_buffer[0][0]:
                    print("Received ACK for packet", ack_seq)
                    packets_buffer.pop(0)
            except timeout:
                # If the thread times out waiting for an ACK, retransmit the
                # packets in the buffer
                print("Timeout waiting for ACK, resending packets")
                for packet in packets_buffer:
                    serverSocket.sendto(packet[1], addr)

    # Start the ACK handler thread
    threading.Thread(target=ack_handler, daemon=True).start()

    # Loop to receive packets and write them to the file
    queue = []
    while True:
        packet, addr = serverSocket.recvfrom(1024)
        seq, _, flags, _ = headers.parse_header(packet[:12])

        # Send an ACK for the packet
        ack_packet = headers.create_packet(seq, 0, headers.ACK_FLAG, 0, b'')
        serverSocket.sendto(ack_packet, addr)

        # If the packet is the next one expected, write it to the file and
        # continue sending the remaining packets
        if seq == len(queue) + 1:
            print("Received packet", seq)
            queue.append((seq, packet))
            while queue and queue[0][0] == len(queue):
                f.write(queue.pop(0)[1][12:])
                f.flush()

        # If the packet is not the next one expected, add it to the buffer
        elif seq > len(queue):
            print("Adding packet", seq, "to buffer")
            queue.append((seq, packet))

# Loop to receive packets and write them to the file
queue = []
while True:
    packet, addr = serverSocket.recvfrom(1024)
    seq, _, flags, _ = headers.parse_header(packet[:12])

    # Send an ACK for the packet
    ack_packet = headers.create_packet(seq, 0, headers.ACK_FLAG, 0, b'')
    serverSocket.sendto(ack_packet, addr)

    # If the packet is the next one expected, write it to the file and
    # continue sending the remaining packets
    if seq == len(queue) + 1:
        print("Received packet", seq)
        queue.append((seq, packet))
        while queue and queue[0][0] == len(queue):
            f.write(queue.pop(0)[1][12:])
            f.flush()

    # If the packet is not the next one expected, add it to the buffer
    elif seq > len(queue):
        print("Adding packet", seq, "to buffer")
        queue.append((seq, packet))

        # Check if any packets in the buffer can now be written to the file
        while queue and queue[0][0] == len(queue):
            f.write(queue.pop(0)[1][12:])
            f.flush()

# Close the file and socket
f.close()
serverSocket.close()
