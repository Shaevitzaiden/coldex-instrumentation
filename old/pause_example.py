'''
Start app 1.  (The program below)
Start app 2.  (import app_2)
               instead of the ctr & print_numbers(),
               call app_2.function_name() using multiprocessing
App 2 pauses app 1 while it does something.  (in code below)
App 2 closes.  (test for close event instead of time.sleep below)
App 1 resumes.
'''
import multiprocessing
import os
import psutil
import time

def print_numbers(start, stop):
        ctr = start
        for x in range(start, stop):
            ctr +=1
            print(ctr)
            time.sleep(0.5)

if __name__ == "__main__":
     
    pid=os.getpid()
    mp = multiprocessing.Process(target=print_numbers, args=(20, 100))
    mp.start()

    print(pid)
    print(mp.pid)
    print("--")

    p= psutil.Process(mp.pid)
    # p.resume()

    print('pid =', pid, p)
    print("status", p.status())
    time.sleep(2.5)
    print("status", p.status())


    p.suspend()
    print("status", p.status())

    
    time.sleep(2.5)
    print("resume it", mp.is_alive())
    p.resume()

    print("status", p.status())

    time.sleep(2.5)
    if mp.is_alive():
        print("terminate", mp.is_alive())
        p.kill()
        mp.terminate()
        mp.join()
    else:
        print("terminated node")
    print("status", mp.is_alive()) 