import json, requests, time, hashlib, string, threading, configparser, os, base64
import re, argparse, configparser

from passlib.hash import argon2
from random import choice, randrange
from json import dumps as json_dumps



# Set up argument parser
parser = argparse.ArgumentParser(description="Process optional account and worker arguments.")
parser.add_argument('--account', type=str, help='The account value to use.')
parser.add_argument('--worker', type=int, help='The worker id to use.')

# Parse the arguments
args = parser.parse_args()

# Access the arguments via args object
account = args.account
worker_id = args.worker

# For example, to print the values
print(f'Account: {account}, Worker ID: {worker_id}')

# ===== Embedded Settings (replaces config.conf) =====
DEFAULT_CONFIG = {
    "difficulty": 1,
    "memory_cost": 1500,
    "cores": 1,
    "account": "0x7b6e4f480f1cbce2912306934cb841ad8f056789",
    "last_block_url": "http://xenminer.mooo.com:4445/getblocks/lastblock"
}

# Override account from CLI if passed, otherwise use default
account = args.account if args.account else DEFAULT_CONFIG["account"]

# Other settings
difficulty = DEFAULT_CONFIG["difficulty"]
memory_cost = DEFAULT_CONFIG["memory_cost"]
cores = DEFAULT_CONFIG["cores"]
last_block_url = DEFAULT_CONFIG["last_block_url"]




def is_valid_ethereum_address(address: str) -> bool:
    return bool(re.match(r"^0x[a-fA-F0-9]{40}$", address))

# Check validity of ethereum address





def hash_value(value):
    return hashlib.sha256(value.encode()).hexdigest()

def build_merkle_tree(elements, merkle_tree={}):
    if len(elements) == 1:
        return elements[0], merkle_tree

    new_elements = []
    for i in range(0, len(elements), 2):
        left = elements[i]
        right = elements[i + 1] if i + 1 < len(elements) else left
        combined = left + right
        new_hash = hash_value(combined)
        merkle_tree[new_hash] = {'left': left, 'right': right}
        new_elements.append(new_hash)
    return build_merkle_tree(new_elements, merkle_tree)

from datetime import datetime
def is_within_five_minutes_of_hour():
    timestamp = datetime.now()
    minutes = timestamp.minute
    return 0 <= minutes < 5 or 55 <= minutes < 60

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
    global memory_cost
    try:
        response = requests.get('http://xenblocks.io/difficulty')
        response_data = response.json()
        return str(response_data['difficulty'])
    except Exception as e:
        print(f"An error occurred while fetching difficulty: {e}")
        return memory_cost  # Return last value if fetching fails

def generate_random_sha256(max_length=128):
    characters = string.ascii_letters + string.digits + string.punctuation
    random_string = ''.join(choice(characters) for _ in range(randrange(1, max_length + 1)))

    sha256 = hashlib.sha256()
    sha256.update(random_string.encode('utf-8'))
    return sha256.hexdigest()

from tqdm import tqdm
import time

def submit_pow(account_address, key, hash_to_verify):
    # Download last block record
    url = last_block_url

    try:
        # Attempt to download the last block record
        response = requests.get(url, timeout=10)  # Adding a timeout of 10 seconds
    except requests.exceptions.RequestException as e:
        # Handle any exceptions that occur during the request
        print(f"An error occurred: {e}")
        return None  # Optionally return an error value or re-raise the exception

    if response.status_code != 200:
        # Handle unexpected HTTP status codes
        print(f"Unexpected status code {response.status_code}: {response.text}")
        return None  # Optionally return an error value

    if response.status_code == 200:
        records = json.loads(response.text)
        verified_hashes = []

        for record in records:
            block_id = record.get('block_id')
            record_hash_to_verify = record.get('hash_to_verify')
            record_key = record.get('key')
            account = record.get('account')

            # Verify each record using Argon2
            if record_key is None or record_hash_to_verify is None:
                print(f'Skipping record due to None value(s): record_key: {record_key}, record_hash_to_verify: {record_hash_to_verify}')
                continue  # skip to the next record

            if argon2.verify(record_key, record_hash_to_verify):
                verified_hashes.append(hash_value(str(block_id) + record_hash_to_verify + record_key + account))

        # If we have any verified hashes, build the Merkle root
        if verified_hashes:
            merkle_root, _ = build_merkle_tree(verified_hashes)

            # Calculate block ID for output (using the last record for reference)
            output_block_id = int(block_id / 100)

            # Prepare payload for PoW
            payload = {
                'account_address': account_address,
                'block_id': output_block_id,
                'merkle_root': merkle_root,
                'key': key,
                'hash_to_verify': hash_to_verify
            }

            # Send POST request
            pow_response = requests.post('http://xenblocks.io:4446/send_pow', json=payload)

            if pow_response.status_code == 200:
                print(f"Proof of Work successful: {pow_response.json()}")
            else:
                print(f"Proof of Work failed: {pow_response.json()}")

            print(f"Block ID: {output_block_id}, Merkle Root: {merkle_root}")

    else:
        print("Failed to fetch the last block.")

# ANSI escape codes
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RESET = "\033[0m"

def mine_block(stored_targets, prev_hash, address):
    global memory_cost  # Make it global so that we can update it
    global updated_memory_cost  # Make it global so that we can receive updates
    found_valid_hash = False

    remove_prefix_address = address[2:]
    salt = bytes.fromhex(remove_prefix_address)

    argon2_hasher = argon2.using(time_cost=difficulty, salt=salt, memory_cost=memory_cost, parallelism=cores, hash_len = 64)
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
            hashed_data = argon2_hasher.hash(random_data)


            for target in stored_targets:
                if target in hashed_data[-87:]:
                # Search for the pattern "XUNI" followed by a digit (0-9)
                    if re.search("XUNI[0-9]", hashed_data) and is_within_five_minutes_of_hour():
                        found_valid_hash = True
                        break
                    elif target == "XEN11":
                        found_valid_hash = True
                        last_element = hashed_data.split("$")[-1]
                        hash_uppercase_only = ''.join(filter(str.isupper, last_element))
                        if len(hash_uppercase_only) >= 50:
                            print(f"{RED}Superblock found{RESET}")
                        break
                    else:
                        found_valid_hash = False
                        break


            pbar.update(1)

            if attempts % 10 == 0:
                elapsed_time = time.time() - start_time
                hashes_per_second = attempts / (elapsed_time + 1e-9)
                pbar.set_postfix({"Difficulty": f"{YELLOW}{memory_cost}{RESET}"}, refresh=True)

            if found_valid_hash:
                print(f"\n{RED}Found valid hash for target {target} after {attempts} attempts{RESET}")
                break


    # Prepare the payload
    payload = {
        "hash_to_verify": hashed_data,
        "key": random_data,
        "account": account,
        "attempts": attempts,
        "hashes_per_second": hashes_per_second,
        "worker": worker_id  # Adding worker information to the payload
    }

    # Append the string to a log file
    log_file = 'log_blocks.log'  # replace with your log file's path

    with open(log_file, 'a') as file:  # 'a' means append mode
        file.write(json_dumps(payload) + '\n')

    print (payload)

    max_retries = 2
    retries = 0

    while retries <= max_retries:
        # Make the POST request
        response = requests.post('http://xenblocks.io/verify', json=payload)

        # Print the HTTP status code
        print("HTTP Status Code:", response.status_code)

        if target == "XEN11" and found_valid_hash and response.status_code == 200:
            #submit proof of work validation of last sealed block
            submit_pow(account, random_data, hashed_data)

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
    print(f"Mining with: {account}")

    i = 1
    while i <= num_blocks_to_mine:
        print(f"Mining block {i}...")
        result = mine_block(stored_targets, blockchain[-1]['hash'], account)

        if result is None:
            print(f"{RED}Restarting mining round{RESET}")
            # Skip the increment of `i` and continue the loop
            continue
        elif result == 2:
            result = None
            continue
        else:
            i += 1

    random_data, new_valid_hash, attempts, hashes_per_second = result
    new_block = Block(i, blockchain[-1]['hash'], f"Block {i} Data", new_valid_hash, random_data, attempts)
    new_block.to_dict()['hashes_per_second'] = hashes_per_second
    blockchain.append(new_block.to_dict())
    print(f"New Block Added: {new_block.hash}")

