import argparse
import os
import random
import select
import socket
import struct
import sys
import threading
import time

# Constants
HEADER_LENGTH = 12
MAX_PACKET_SIZE = 1472
MAX_WINDOW_SIZE = 64
TIMEOUT = 1

# Flags
SYN_FLAG = 0b1000
ACK_FLAG = 0b0100
FIN_FLAG = 0b0010
RST_FLAG = 0b0001


def create_packet(seq_num, ack_num, flags, window_size, data):
    header = struct.pack('!IIHH', seq_num, ack_num, flags, window_size)
    packet = header + data
    return packet


def parse_header(packet):
    header = packet[:HEADER_LENGTH]
    seq_num, ack_num, flags, window_size = struct.unpack('!IIHH', header)
    return seq_num, ack_num, flags, window_size


def DRPTClient(ip, port, file, reliable, test_case):
    pass


class Receiver:
    def __init__(self, ip_address, port, file_name, reliable_method):
        self.ip_address = ip_address
        self.port = port
        self.file_name = file_name
        self.reliable_method = reliable_method
        self.file = None
        self.next_seq_num = 1
        self.expected_ack_num = 1
        self.recv_buffer = []
        self.recv_buffer_lock = threading.Lock()
        self.recv_window = MAX_WINDOW_SIZE
        self.sender_address = None
        self.sender_window_size = 0
        self.sender_address_lock = threading.Lock()
        self.timer = None
        self.timer_lock = threading.Lock()

        # Create UDP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((ip_address, port))

    def receive(self):
        while True:
            packet, address = self.socket.recvfrom(MAX_PACKET_SIZE)

            # Parse header and data from packet
            seq_num, ack_num, flags, window_size = parse_header(packet)
            data = packet[HEADER_LENGTH:]

            if flags & RST_FLAG:
                print('Connection reset by peer')
                self.close()
                break

            if flags & SYN_FLAG:
                # New connection request
                print('Received SYN from', address)
                self.sender_address = address
                self.sender_window_size = window_size
                ack_packet = create_packet(0, seq_num + 1, SYN_FLAG | ACK_FLAG, MAX_WINDOW_SIZE, b'')
                self.socket.sendto(ack_packet, address)
                print('Sent SYN-ACK to', address)
            elif flags & ACK_FLAG:
                # Handle ACK packet
                print('Received ACK', ack_num, 'from', address)
                if ack_num > self.next_seq_num:
                    print('Unexpected ACK number')
                    continue

                if ack_num == self.next_seq_num:
                    # Stop timer
                    with self.timer_lock:
                        if self.timer is not None:
                            self.timer.cancel()
                            self.timer = None

                    # Update receive buffer and expected ACK number
                    with self.recv_buffer_lock:
                        self.recv_buffer.append((seq_num, data))
                        self.recv_buffer.sort(key=lambda x: x[0])
                        while self.recv_buffer and self.recv_buffer[0][0] == self.expected_ack_num:
                            self.file.write(self.recv_buffer.pop(0)[1])
                            self.expected_ack_num += 1
                            self.recv_window += 1

                            # Send ACK for received packet
                            ack_packet = create_packet(0, ack_num, ACK_FLAG, self.recv_window, b'')
                            self.socket.sendto(ack_packet, address)
                            print('Sent ACK for packet', seq_num)

                            # If received packet is the expected packet
                            if seq_num == self.expected_seq:
                                self.expected_seq += 1
                                self.buffer.append(packet[12:])

                                # Write all packets in the buffer that are in order
                                while self.buffer and self.buffer[0]:
                                    self.file.write(self.buffer.pop(0))
                                    self.bytes_received += 1460

                            # If received packet is not the expected packet
                            else:
                                self.buffer[seq_num - self.expected_seq - 1] = packet[12:]

                            # If all packets have been received, close the connection and file
                            if self.bytes_received == self.file_size:
                                print('Received file successfully')
                                self.file.close()
                                self.socket.close()
                                sys.exit()

                             # If packet is not valid, discard it
                               #  excep  InvalidPacketError:
                                     #  pass

                def run(self):
                    # Start the receiving loop in a separate thread
                    thread = threading.Thread(target=self.receive_loop)
                    thread.start()

                    # Wait for the thread to finish
                    thread.join()

            if __name__ == '__main__':
                # Parse command line arguments
                parser = argparse.ArgumentParser(description='DRTP file transfer client')
                parser.add_argument('-i', '--ip', type=str, required=True, help='server IP address')
                parser.add_argument('-p', '--port', type=int, required=True, help='server port number')
                parser.add_argument('-f', '--file', type=str, required=True, help='file to transfer')
                parser.add_argument('-r', '--reliable', type=str, choices=['gbn', 'sr'], default='gbn',
                                    help='reliable transmission protocol (default: GBN)')
                parser.add_argument('-t', '--test-case', type=str, default=None,
                                    help='test case to simulate packet loss (options: loss)')
                args = parser.parse_args()

                # Create a DRTP client and start the transfer
                client = DRPTClient(args.ip, args.port, args.file, args.reliable, args.test_case)
                client.run()
