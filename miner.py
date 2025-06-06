import json
import requests
import time
from passlib.hash import argon2
import hashlib
from random import choice, randrange
import string
import threading
import re

difficulty = 1
memory_cost = 1500 
cores = 1
account = "0x8e0eF38146634d387A7302d084bDCdC000999999"
print(account,difficulty,memory_cost,cores)
print('------XUNI------')
class Block:
    def __init__(self, index, prev_hash, data, valid_hash, random_data, attempts):
        self.index = index
        self.prev_hash = prev_hash
        self.data = data
        self.valid_hash = valid_hash
        self.random_data = random_data
        self.attempts = attempts
        self.timestamp = time.time()
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        sha256 = hashlib.sha256()
        sha256.update(f"{self.index}{self.prev_hash}{self.data}{self.valid_hash}{self.timestamp}".encode("utf-8"))
        return sha256.hexdigest()

    def to_dict(self):
        return {
            "index": self.index,
            "prev_hash": self.prev_hash,
            "data": self.data,
            "valid_hash": self.valid_hash,
            "random_data": self.random_data,
            "timestamp": self.timestamp,
            "hash": self.hash,
            "attempts": self.attempts
        }

updated_memory_cost = 1500 # just initialize it

def update_memory_cost_periodically():
    global memory_cost
    global updated_memory_cost
    time.sleep(10)  # start checking in 10 seconds after launch 
    while True:
        updated_memory_cost = fetch_difficulty_from_server()
        if updated_memory_cost != memory_cost:
            print(f"Updating difficulty to {updated_memory_cost}")
        time.sleep(60)  # Fetch every 60 seconds

# Function to get difficulty level from the server
def fetch_difficulty_from_server():
    try:
        response = requests.get('http://xenblocks.io/difficulty')
        response_data = response.json()
        return str(response_data['difficulty'])
    except Exception as e:
        print(f"An error occurred while fetching difficulty: {e}")
        return '2000'  # Default value if fetching fails

def generate_random_sha256(max_length=128):
    characters = string.ascii_letters + string.digits + string.punctuation
    random_string = ''.join(choice(characters) for _ in range(randrange(1, max_length + 1)))

    sha256 = hashlib.sha256()
    sha256.update(random_string.encode('utf-8'))
    return sha256.hexdigest()

from tqdm import tqdm
import time

# ANSI escape codes
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RESET = "\033[0m"

def mine_block(stored_targets, prev_hash):
    global memory_cost  # Make it global so that we can update it
    global updated_memory_cost  # Make it global so that we can receive updates
    found_valid_hash = False
    #memory_cost=fetch_difficulty_from_server()
    argon2_hasher = argon2.using(time_cost=difficulty, salt=b"XEN10082022XEN", memory_cost=memory_cost, parallelism=cores, hash_len = 64)
    attempts = 0
    random_data = None
    start_time = time.time()
    
    with tqdm(total=None, dynamic_ncols=True, desc=f"{GREEN}Mining{RESET}", unit=f" {GREEN}Hashes{RESET}") as pbar:
        while True:
            attempts += 1
        
            if attempts % 100 == 0:
                if updated_memory_cost != memory_cost:
                    memory_cost = updated_memory_cost
                    print(f"{BLUE}Continuing to mine blocks with new difficulty{RESET}")
                    return

            random_data = generate_random_sha256()
            hashed_data = argon2_hasher.hash(random_data + prev_hash)

            for target in stored_targets:
                if target in hashed_data[-87:]:
                    print(f"\n{RED}Found valid hash for target {target} after {attempts} attempts{RESET}")
                    capital_count = sum(1 for char in re.sub('[0-9]', '', hashed_data) if char.isupper())

                    if capital_count >= 65:
                        print(f"{RED}Superblock found{RESET}")

                    found_valid_hash = True
                    break

            pbar.update(1)

            if attempts % 10 == 0:
                elapsed_time = time.time() - start_time
                hashes_per_second = attempts / (elapsed_time + 1e-9)
                pbar.set_postfix({"Difficulty": f"{YELLOW}{memory_cost}{RESET}"}, refresh=True)

            if found_valid_hash:
                break


    # Prepare the payload
    payload = {
        "hash_to_verify": hashed_data,
        "key": random_data + prev_hash,
        "account": account,
        "attempts": attempts,
        "hashes_per_second": hashes_per_second
        }

    print (payload)

    max_retries = 2
    retries = 0

    while retries <= max_retries:
        # Make the POST request
        response = requests.post('http://xenminer.mooo.com/verify', json=payload)

        # Print the HTTP status code
        print("HTTP Status Code:", response.status_code)

        if response.status_code != 500:  # If status code is not 500, break the loop
            print("Server Response:", response.json())
            break
        
        retries += 1
        print(f"Retrying... ({retries}/{max_retries})")
        time.sleep(10)  # You can adjust the sleep time


        # Print the server's response
        try:
            print("Server Response:", response.json())
        except Exception as e:
            print("An error occurred:", e)

    return random_data, hashed_data, attempts, hashes_per_second

def verify_block(block):
    argon2_hasher = argon2.using(time_cost=difficulty, memory_cost=memory_cost, parallelism=cores)
    #debug
    print ("Key: ");
    print (block['random_data'] + block['prev_hash'])
    print ("Hash: ");
    print (block['valid_hash'])
    return argon2_hasher.verify(block['random_data'] + block['prev_hash'], block['valid_hash'])

if __name__ == "__main__":
    blockchain = []
    stored_targets = ['XEN11', 'XUNI']
    num_blocks_to_mine = 20000000
    
    #Start difficulty monitoring thread
    difficulty_thread = threading.Thread(target=update_memory_cost_periodically)
    difficulty_thread.daemon = True  # This makes the thread exit when the main program exits
    difficulty_thread.start()

    genesis_block = Block(0, "0", "Genesis Block", "0", "0", "0")
    blockchain.append(genesis_block.to_dict())
    print(f"Genesis Block: {genesis_block.hash}")

    i = 1
    while i <= num_blocks_to_mine:
        print(f"Mining block {i}...")
        result = mine_block(stored_targets, blockchain[-1]['hash'])

        if result is None:
            print(f"{RED}Restarting mining round{RESET}")
                # Skip the increment of `i` and continue the loop
            continue
        else:
            i += 1  

    random_data, new_valid_hash, attempts, hashes_per_second = result
    new_block = Block(i, blockchain[-1]['hash'], f"Block {i} Data", new_valid_hash, random_data, attempts)
    new_block.to_dict()['hashes_per_second'] = hashes_per_second
    blockchain.append(new_block.to_dict())
    print(f"New Block Added: {new_block.hash}")


    # Verification
    for i, block in enumerate(blockchain[1:], 1):
        is_valid = verify_block(block)
        print(f"Verification for Block {i}: {is_valid}")

    # Write blockchain to JSON file
    blockchain_json = json.dumps(blockchain, indent=4)
    with open("blockchain.json", "w") as f:
        f.write(blockchain_json)
