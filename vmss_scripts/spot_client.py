import socket
from datetime import datetime
import os
import json
from random import randint
import time
from subprocess import call

def read_trace(trace_file):
        trace = []
        with open(trace_file, 'r') as f:
            for line in f:
                # self-defined comment for trace file
                if line.startswith('#'):
                    continue
                trace.append(json.loads(line))
        return trace

def client(ip, port, message):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((ip, port))
        sock.sendall(bytes(message, 'ascii'))

def write_machine_list(machine_list):
    of = open("/home/ubuntu/varuna/examples/Megatron-LM/available_machines.out","w")
    for m in machine_list:
        of.write(m)
        if "\n" not in m:
            of.write("\n")
    of.close()

if __name__ == "__main__":

    server_ip = "172.31.28.108"
    server_port = 4200

    traces = read_trace('trace_mem.txt')
    machines = traces[0][2]['nodes']
    write_machine_list(machines)
    print(machines)

    for i in range(1, len(traces)):
        t = traces[i]
        time.sleep(t[0] - traces[i-1][0])
        if t[1] == 'add':
            machines.extend(t[0][2]['nodes'])
            write_machine_list(machines)
            client(server_ip, server_port, "morph")
        elif t[1] == 'remove':
            [machines.remove(n) for n in t[0][2]['nodes']]
            write_machine_list(machines)
            client(server_ip, server_port, "preempt")

    call("../examples/Megatron-LM/pretrain_gpt2_varuna.sh", shell=True)