import argparse
import struct
import threading
import sys
import os
import time
from socket import *
import headers

parser = argparse.ArgumentParser(description="TCP connection that can run in server and client mode")

parser.add_argument('-s', '--server', action='store_true')
parser.add_argument('-c', '--client', action='store_true')
parser.add_argument('-b', '--bind', type=str)
parser.add_argument('-p', '--port', type=int)
parser.add_argument('-f', '--file', type=str)
parser.add_argument('-t', '--test_case', type=str, choices=["none","loss","skip_ack"], default="none")

args = parser.parse_args()

header_format = '!IIIHH'
buffer = 1472
buffer1 = 1484

def calculate_checksum(packet):
    """
    Calculate the checksum of the packet.
    """
    checksum = 0
    for i in range(0, len(packet), 2):
        if i == 10:
            continue
        checksum += (packet[i] << 8) + packet[i+1]
    checksum = (checksum >> 16) + (checksum & 0xffff)
    checksum = ~checksum & 0xffff
    return checksum

def repeat_send(conn, addr, data):
    """
    Resend the packet if it is not acknowledged within a timeout period.
    """
    print("Packet failed to send... Resending...")
    while True:
        try:
            conn.sendto(data, addr)
            conn.settimeout(2)
            conn.recv(1024)
            print("Received ack")
            break
        except timeout:
            continue

if args.server and args.client:
    print("Can't run server and client at the same time")
    sys.exit()

if not args.server and not args.client:
    print("You have to start in either client or server mode")
    sys.exit()

if args.server:
    seq = 0
    ack = 0
    addr = (args.bind, args.port)
    serverSocket = socket(AF_INET, SOCK_DGRAM)
    serverSocket.bind((args.bind, args.port))
    f = open(args.file, "wb")
    expected_seq = 0
    window_size = 5
    buffer = [None] * window_size
    ack_pack = struct.pack(header_format, 0, 0, 4, 0, 0)

    while True:
        # Receive a packet
        data, addr = serverSocket.recvfrom(buffer1)
        header_msg = data[:12]
        seq, ack, flags, win, checksum = struct.unpack(header_format, header_msg)
        syn, ack, fin = headers.parse_flags(flags)

        # Check if the packet is corrupted
        if checksum != calculate_checksum(data):
            print("Received corrupted packet")
            continue

        # Send an acknowledgement
        ack_pack = struct.pack(header_format, 0, seq+1, 4, 0, 0)
        serverSocket.sendto(ack_pack, addr)

        # Handle the packet based on its sequence number
        # Write any out-of-order packets in the buffer to the file
        i = 0
        while buffer[i] is not None:
            seq, message_body = buffer[i]
            if seq == expected_seq:
                f.write(message_body)
                expected_seq += 1
                # Slide the window
                buffer[i] = None
                i += 1
            else:
                break

        # Check if the received packet is the last one
        if fin == 1:
            break

    else:
        # Put the packet in the buffer
        i = (seq - expected_seq) % window_size
        buffer[i] = (seq, message_body)

        # Send an acknowledgement
    ack_pack = struct.pack(header_format, 0, expected_seq, 4, 0, 0)
    serverSocket.sendto(ack_pack, addr)

close_socket(serverSocket, f)

if args.client:
 seq = 0
ack = 0
clientSocket = socket(AF_INET, SOCK_DGRAM)
serverAddress = (args.bind, args.port)
f = open(args.file, "rb")
message = f.read(buffer)
expected_ack = 0
window_size = 5
buffer = [None] * window_siz
# Send the first packet with SYN flag set
syn_pack = struct.pack(header_format, seq, ack, headers.make_flags(1, 0, 0), window_size, 0)
clientSocket.sendto(syn_pack, serverAddress)

while True:
    try:
        # Receive an acknowledgement
        clientSocket.settimeout(2)
        ack_pack, serverAddress = clientSocket.recvfrom(buffer)
        header_msg = ack_pack[:12]
        seq, ack, flags, win, checksum = struct.unpack(header_format, header_msg)
        syn, ack, fin = headers.parse_flags(flags)

        # Check if the acknowledgement is corrupted
        if checksum != calculate_checksum(ack_pack):
            print("Received corrupted acknowledgement")
            continue

        # Handle the acknowledgement based on its sequence number
        if ack == expected_ack:
            # Read the next packet from the file
            message = f.read(buffer)
            seq += 1

            # Check if the packet is the last one
            if not message:
                fin = 1

            # Send the packet
            pack = struct.pack(header_format, seq, expected_ack+1, headers.make_flags(0, 1, fin), window_size, 0)
            pack += message
            clientSocket.sendto(pack, serverAddress)

            # Write any out-of-order packets in the buffer to the file
            i = 0
            while buffer[i] is not None:
                seq, message_body = buffer[i]
                if seq == expected_ack + 1:
                    f.write(message_body)
                    expected_ack += 1
                    # Slide the window
                    buffer[i] = None
                    i += 1
                else:
                    break

            # Slide the window
            expected_ack += 1

        else:
            # Put the acknowledgement in the buffer
            i = (ack - expected_ack) % window_size
            buffer[i] = (ack, None)

        # Check if the last packet has been acknowledged
        if fin == 1 and ack == seq+1:
            break

    except timeout:
        # Resend the packet
        repeat_send(clientSocket, server)
        # Send an acknowledgement
        ack_pack = struct.pack(header_format, 0, seq + 1, 4, 0, 0)
        clientSocket.sendto(ack_pack, serverAddr)

        # Handle the packet based on its sequence number
        if seq == expected_seq:
        # Write the packet data to the file
            message_body = data[12:]
        f.write(message_body)
        expected_seq += 1

        # Write any out-of-order packets in the buffer to the file
        i = 0
        while buffer[i] is not None:
            seq, message_body = buffer[i]
            if seq == expected_seq:
                f.write(message_body)
                expected_seq += 1
                buffer[i] = None
            i = (i + 1) % window_size

            # Slide the window
        buffer[(seq - expected_seq) % window_size] = (seq, message_body)
        expected_ack = expected_seq + 1
        for i in range(window_size):
            if buffer[i] is not None and buffer[i][0] == expected_ack:
                message = buffer[i][1]
                f.write(message)
                buffer[i] = None
                expected_ack += 1
        ack_pack = struct.pack(header_format, 0, expected_ack, 4, 0, 0)
        clientSocket.sendto(ack_pack, serverAddr)

    else:
        # Packet was out of order, buffer it
        buffer[(seq - expected_seq) % window_size] = (seq, message_body)
        ack_pack = struct.pack(header_format, 0, expected_ack, 4, 0, 0)
        clientSocket.sendto(ack_pack, serverAddr)

    # Close the client socket and the file
    clientSocket.close()
    f.close()
    print("File transfer complete")
    clientSocket.close()
    sys.exit()



