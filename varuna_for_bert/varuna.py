from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Tuple, Union, cast
import torch
from torch import Tensor, nn
import torch.distributed as dist
from torch.multiprocessing import Process
from queue import Queue
from threading import Thread

import os
import sys
import time
from apex import amp

Module = nn.Module

print('Varuna imported!!')
import datetime
def init_processes(rank, size, fn, backend='gloo'):
    """ Initialize the distributed environment. """
    os.environ['MASTER_ADDR'] = '10.4.0.9'
    os.environ['MASTER_PORT'] = '29500'
    connect_timeout = datetime.timedelta(minutes=2)
    dist.init_process_group(backend, rank=rank, world_size=size, timeout=connect_timeout)
    fn(rank, size)

class Varuna(Module):
    """
    model = nn.Sequential(a,b,c,d)      # any standard pytorch model
    model = Varuna(model, microbatches/minibatch, list_of_devices)
    for iteration in epoch:
        model(input)   # execute Varuna's pipeline (forward and backward pass)
        optimizer.step()
        optimizer.zero_grad()
    """
    def __init__(self,
                model,
                partitions,
                optimizer,
                fp16,
                chunks: int=1):
        super().__init__()
        # todo: distributed process initialization
        # move init_processes() here
        # p = Process(target=init_processes, args=(1,2,main))
        # p.start()

        self.model = model
        self.chunks = chunks
        self.partitions = partitions
        self.optimizer = optimizer
        self.fp16 = fp16
        self.rank = dist.get_rank()

        self.acts_handle_thread = None
        self.grads_handle_thead = None

        self.schedule = self.generate_schedule()

    def forward(self, inputs):
        # Divide a mini-batch into micro-batches.
        batches = scatter(inputs, self.chunks)
        
        # need not pass the first argument if rank!=0
        # avoid dataloader compute in machines other than the first
        # ask the model writer to pass the input batch generating dataloader function to Varuna::__init__
        # and Varuna can take care of input dataloader explicitly
        pipeline = Pipeline(batches, self.partitions, self.model, self.schedule, self.optimizer, self.fp16)
        pipeline.run()
    
    def eval(self):
        self.model.eval()
    
    def train(self):
        self.model.train()
    
    def zero_grad(self):
        self.model.zero_grad()
    
    def generate_schedule(self):
        c_schedule = os.popen('./genschedule '+str(self.partitions)+' '+str(self.chunks)+' '+str(self.rank)).read()
        schedule = list()

        steps = c_schedule.split(';')
        steps = steps[:-1]
        for step in steps:
            task = step.split(',')
            schedule.append((int(task[0]), int(task[1])))
        
        return schedule
                

def save_rng_states():
    """capture current CPU, GPU random number generator states to reuse while recomputing activations
    in order to ensure Referential Transparency
    """
    cpu_rng_state = torch.get_rng_state()

    gpu_rng_states: Optional[ByteTensor]
    gpu_rng_states = torch.cuda.get_rng_state_all() 
    return (cpu_rng_state, gpu_rng_states)

def restore_rng_states(rng_states):
    cpu_rng_state, gpu_rng_states = rng_states
    torch.set_rng_state(cpu_rng_state)
    torch.cuda.set_rng_state_all(gpu_rng_states)        # todo: verify correctness;   batchNorm, dropouts, convlayers?


def get_size():        # todo
    acts_size = (30, 512, 1024)
    return acts_size

def acts_handle_wait(rank, acts_handle):
    while (True):
        output_acts = acts_handle.get()
        handle = dist.isend(output_acts.cpu(), dst=rank+1)
        handle.wait()

def grads_handle_wait(rank, grads_handle):
    while (True):
        input_grads = grads_handle.get()
        handle = dist.isend(input_grads.cpu(), dst=rank-1)
        handle.wait()


class Pipeline:
    """ Pipeline parallelism for Varuna """

    def __init__(self, batches, partitions, model, schedule, optimizer, fp16):
        self.batches = batches
        self.partitions = partitions
        self.model = model
        self.rank=dist.get_rank()
        self.world_size = partitions
        self.schedule = schedule
        self.optimizer = optimizer
        self.fp16 = fp16

        self.grads_handle = Queue()
        self.acts_handle = Queue()

        self.spawn_send_workers()

        self.acts_queue = Queue()       # activation at the boundary, rename as input_acts
        self.grads_queue = Queue()
        self.recompute_queue = Queue()

        self.acts_reciever_thread = None
        self.grads_reciever_thread = None

        # stores output of recompute(/forward) pass to be used by backward()
        self.loss = None
        # stores input activations to recompute(/forward) - in order to access its grads and send it to  (rank-1)th device
        self.input_acts = None

        if (self.rank==0):
            for batch in batches:
                self.acts_queue.put(batch['input_ids'])
    
    
    def spawn_send_workers(self):
        self.acts_handle_thread = Thread(target=acts_handle_wait, args=(self.rank, self.acts_handle))
        self.acts_handle_thread.daemon=True
        self.acts_handle_thread.start()

        self.grads_handle_thead = Thread(target=grads_handle_wait, args=(self.rank, self.grads_handle))
        self.grads_handle_thead.daemon=True
        self.grads_handle_thead.start()


    
    def acts_reciever(self):
        count=0
        if (self.rank!=0):
            for task,index in self.schedule:
                if (task==0):
                    count+=1
            while (count>0):
                acts_tensor = torch.ones(get_size(), dtype=torch.float32)     # myedits
                req = dist.irecv(acts_tensor, src=self.rank-1)        # myedits
                req.wait()
                count-=1
                self.acts_queue.put(acts_tensor.cuda())
    
    def grads_reciever(self):
        world_size=self.world_size
        count=0
        if (self.rank!=world_size-1):
            for task,index in self.schedule:
                if (task==2):
                    count+=1
            while (count>0):
                grads_tensor = torch.ones(get_size(), dtype=torch.float32)      # myedits
                req = dist.irecv(grads_tensor, src=self.rank+1)       # myedits
                req.wait()
                count-=1
                self.grads_queue.put(grads_tensor.cuda())



    # def worker(task, acts_queue, recompute_queue, grads_queue, model, rank, std_in_for_bert):
    def worker(self, task, grad_mode, std_in_for_bert):
        """ Main body of worker loop """
        world_size=self.world_size
        if (task==0):        # forward
            torch.set_grad_enabled(grad_mode)       # computation graph not needed if recomputing later
            acts = self.acts_queue.get()
            std_in_for_bert['input_ids']=acts
            output = self.model(**std_in_for_bert)                

            if (self.rank!=world_size-1):
                self.acts_handle.put(output[0])
            
            if (grad_mode==False):          # if these acts are going to be recomputed
                # save random number states
                rng_states = save_rng_states()
                ctx = (rng_states, acts)
                self.recompute_queue.put(ctx)

            else:
                # save loss and input activations for the backward pass to use
                self.loss = output[0]
                self.input_acts = acts
        
        elif (task==1):     # recompute
            torch.set_grad_enabled(True)
            ctx, acts = self.recompute_queue.get()
            restore_rng_states(ctx)
            std_in_for_bert['input_ids']=acts
            output = self.model(**std_in_for_bert)
            self.input_acts = acts
            self.loss = output[0]

        
        else:           # backward
            if (self.rank!=world_size-1):
                grads = self.grads_queue.get()

                if (self.fp16==1):
                    with amp.scale_loss(self.loss, self.optimizer) as scaled_loss:
                        scaled_loss.backward(grads)
                else:
                    self.loss.backward(grads)

            else:
                chunks = len(self.batches)
                self.loss = self.loss/chunks

                if (self.fp16==1):
                    with amp.scale_loss(self.loss, self.optimizer) as scaled_loss:
                        scaled_loss.backward()    # accumulate
                else:
                    self.loss.backward()    # accumulate

            if (self.rank!=0):
                self.grads_handle.put(self.input_acts.grad.data)


    def spawn_workers(self):
        self.acts_reciever_thread = Thread(target=self.acts_reciever, args=())
        self.acts_reciever_thread.daemon=True
        self.acts_reciever_thread.start()

        self.grads_reciever_thread = Thread(target=self.grads_reciever, args=())
        self.grads_reciever_thread.daemon=True
        self.grads_reciever_thread.start()
        pass

        
    def run(self):
        self.spawn_workers()        # recieve workers

        for index, task in enumerate(self.schedule):
            grad_mode = False
            if (task[0]==0):
                if (self.schedule[index+1][0]==2):      # if next task in schedule is backward  -- no recomputation
                    grad_mode=True
            
            self.worker(task[0], grad_mode, self.batches[task[1]])
            # todo: return loss at (rank-1)th device
        
        # dynamic schedule - run forward if gradients for backward are not ready yet
        '''
        schedule = [s for s in enumerate(self.schedule)]
        i=0
        count_fwd = 0
        while (i<len(schedule)):
            grad_mode = False
            index, task = schedule[i]
            if (task[0]==1 and count_fwd<len(self.batches) and self.grads_queue.empty()):
                # find the next forward, insert it at ith position, remove from original position, update index and task
                j=i
                while (j<len(schedule)):
                    if (schedule[j][1][0]==0):
                        index, task = schedule[j]
                        schedule.insert(i, schedule[j])
                        del schedule[j+1]
                        break
                    j+=1
            if (task[0]==0):
                count_fwd+=1
                if (self.schedule[index+1][0]==2):      # if next task in schedule is backward;     assuming generate_schedule() is correct, and forward task will never be the last task in schedule
                    grad_mode=True
            
            self.worker(task[0], grad_mode, self.batches[task[1]])
            i+=1
        '''

        
        self.acts_reciever_thread.join()
        self.grads_reciever_thread.join()

def scatter(input, chunks):
    """Split for Bert
    Accepts input dictionary and splits into microbatches
    """
    microbatches = [dict() for _ in range(chunks)]
    for k,v in input.items():
        chunked_values = v.chunk(chunks)
        for i,value in enumerate(chunked_values):
            microbatches[i][k]=value
    
    return microbatches