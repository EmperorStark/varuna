# to be run in manager
import socket
import threading
import socketserver
import time
from datetime import datetime
import os

handle_request = True
checkpointed = 0
is_morphing = False
num_running_nodes = 0

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):

    triggermorph = threading.Lock()
    trackcheckpoints = threading.Lock()
    is_morphing=False

    def handle(self):
        global handle_request, checkpointed, is_morphing, num_running_nodes
        data = str(self.request.recv(1024), 'ascii')
        cur_thread = threading.current_thread()
        print("{} got something from {}: {}".format(datetime.now(), self.client_address, data), flush=True)
        if 'morph' in data:
            self.triggermorph.acquire()
            if handle_request:
                # set False to ignore signals from other VMs, set True after checkpointing succeeds
                handle_request = False 
                is_morphing = True  
                #get number of machines
                num_running_nodes = int(open("/home/varuna/t-nisar/Megatron-LM/nservers").read())       
                print('Trigger morph! {}'.format(num_running_nodes), flush=True)
                os.system("bash /home/varuna/t-nisar/Megatron-LM/send_signal.sh")       # trigger checkpointing in all node
            else:
                print('Morph already triggered!',flush=True)
            self.triggermorph.release()
        elif 'preempt' in data:
            self.triggermorph.acquire()
            if handle_request:
                # set False to ignore signals from other VMs, set True after checkpointing succeeds
                handle_request = False 
                is_morphing = True  
                notbefore = data.split(" ")[-1]
                notbefore = datetime.strptime(notbefore,"%a,_%d_%b_%Y_%H:%M:%S_%Z")
                sleep_time = (notbefore - datetime.now()).seconds - 30
                if sleep_time > 0:
                    time.sleep(sleep_time)
                #get number of machines
                num_running_nodes = int(open("/home/varuna/t-nisar/Megatron-LM/nservers").read())       
                print('Trigger morph! {}'.format(num_running_nodes), flush=True)
                os.system("bash /home/varuna/t-nisar/Megatron-LM/send_signal.sh")       # trigger checkpointing in all node                
            else:
                print('Morph already triggered!',flush=True)
            self.triggermorph.release()
        elif 'checkpoint done' in data:
            self.trackcheckpoints.acquire()
            if is_morphing:
                checkpointed += 1
                if checkpointed == 1:
                    last_iter = int(str(data).split(" ")[-1])
                    print('Checkpoint successful {}'.format(last_iter), flush=True)
                    handle_request = True
                    is_morphing = False
                    checkpointed = 0
                    # wait for scheduled event to occur                    
                    time.sleep(120)
                    # double checking that all pretraining processes are killed 
                    # - not clean and should be removed ideally
                    os.system("bash /home/varuna/t-nisar/Megatron-LM/kill_all.sh")
                    # get available machines
                    os.system("bash /home/varuna/t-nisar/Megatron-LM/get_available_machines.sh > /home/varuna/t-nisar/Megatron-LM/available_machines.out")
                    # resume model in available machines
                    os.system("bash /home/varuna/t-nisar/Megatron-LM/start_remote.sh {}".format(last_iter))
            self.trackcheckpoints.release()
        elif 'checkpoint failed' in data:
            print('checkpoint failed in ', self.client_address[0])
        print("handle done", flush=True)
            

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

if __name__ == "__main__":
    HOST, PORT = "172.16.5.4", 4200

    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    
    with server:
        server.serve_forever()