#!/usr/bin/env python3
"""
test_pipeline.py
Verification script for data pipeline (continuous STEER and UDP buttons).
"""

import socket
import time
import sys

def test_udp_commands():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_addr = ('localhost', 6006)

    print("Testing UDP packet transmission to server...")
    test_packets = [
        "STEER:0.0",
        "STEER:0.2500",
        "STEER:0.7500",
        "STEER:1.0000",
        "STEER:-0.5000",
        "STEER:-1.0000",
        "STEER:0.0",
        "P_ACCELERATE",
        "R_ACCELERATE",
        "P_BRAKE",
        "R_BRAKE",
        "FIRE",
        "NITRO",
        "SELECT",
        "UP",
        "DOWN",
    ]

    for pkt in test_packets:
        sock.sendto(pkt.encode('utf8'), server_addr)
        print(f"  [OK] Sent: {pkt}")
        time.sleep(0.02)

    sock.close()
    print("Transmission completed successfully!")

if __name__ == '__main__':
    test_udp_commands()
