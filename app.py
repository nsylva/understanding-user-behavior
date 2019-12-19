from flask import Flask, request, jsonify
from .src.classes.Trade import Trade
from .src.classes.Player import Player
from .src.classes.Inventory import Inventory
from .src.classes.Item import Item
from .src.inventory_generation.generate_inventory import generate_inventory
import hashlib
import redis
import json
from datetime import datetime
from kafka import KafkaProducer
import os
import random


#set up app
app = Flask(__name__)

#set up connection to Redis
redis_host = redis.Redis(host='redis',port='6379')

#set up Kafka producer
kafka_producer = KafkaProducer(bootstrap_servers='kafka:29092')

#set up possible player usernames
dirname = os.path.dirname(__file__)
names_rel_path = 'data/names.txt'
names_file_path = os.path.join(dirname,names_rel_path)
usernames = []
with open(names_file_path) as names_file:
    for line in names_file:
        usernames.append(line.rstrip('\n'))

@app.route('/')
def default():
    return 'Routing to root not supported. Use trade or create_player.'

@app.route('/trade', methods = ['POST'])
def trade():
    trade_time = datetime.now().strftime("%m/%d/%Y, %H:%M:%S.%f")
    trade_data = request.json

    #create a trade object
    working_trade = Trade(trade_data,redis_host)
    #validate trade
    valid_trade, fail_reason = working_trade.valid, working_trade.fail_reason
    #generate trade_id
    trade_id = create_trade_id(working_trade.player_1.username,working_trade.player_1.player_id,working_trade.player_2.username,working_trade.player_2.player_id,trade_time)
    
    if valid_trade:
        #update inventories and gold counts
        working_trade.execute_trade()
        player_1_dict = working_trade.player_1.to_dict()
        player_2_dict = working_trade.player_2.to_dict()
        # push new inventory and gold states for each player to redis cache
        player_1_updated_state = json.dumps(player_1_dict)
        player_2_updated_state = json.dumps(player_2_dict)
        set_player_inventory_state(working_trade.player_1.player_id, player_1_updated_state)
        set_player_inventory_state(working_trade.player_2.player_id, player_2_updated_state)
        
        # send the player states to Kafka
        player_1_state_id = create_state_id(player_1_dict['username'],player_1_dict['player_id'],trade_time)
        player_2_state_id = create_state_id(player_2_dict['username'],player_2_dict['player_id'],trade_time)

        '''state_id,player_id,username,player_class,timestamp,inventory_max_capacity,inventory_current_capacity,item_held, gold'''
        player_1_states = [construct_state_dict(player_1_state_id,
                                                player_1_dict['player_id'],
                                                player_1_dict['username'],
                                                player_1_dict['player_class'],
                                                trade_time,
                                                player_1_dict['inventory']['max_capacity'],
                                                player_1_dict['inventory']['current_capacity'],
                                                i,
                                                player_1_dict['gold']) for i in player_1_dict['inventory']['items']]

        player_2_states = [construct_state_dict(player_2_state_id,
                                                player_2_dict['player_id'],
                                                player_2_dict['username'],
                                                player_2_dict['player_class'],
                                                trade_time,
                                                player_2_dict['inventory']['max_capacity'],
                                                player_2_dict['inventory']['current_capacity'],
                                                i,
                                                player_2_dict['gold']) for i in player_2_dict['inventory']['items']]

        for player_1_state in player_1_states:
            log_to_kafka('events',player_1_state)

        for player_2_state in player_2_states:
            log_to_kafka('events',player_2_state)

        trade = working_trade.to_dict()
        player_1_trades = [construct_trade_dict(trade_id,
                                                trade['player_1']['player_id'],
                                                trade_time,
                                                i,
                                                trade['player_1']['gold_traded'],
                                                valid_trade,
                                                fail_reason) for i in trade['player_1']['items_traded']]
        player_2_trades = [construct_trade_dict(trade_id,
                                                trade['player_2']['player_id'],
                                                trade_time,
                                                i,
                                                trade['player_2']['gold_traded'],
                                                valid_trade,
                                                fail_reason) for i in trade['player_2']['items_traded']]
        
        #log the failed trade to kafka
        for player_1_trade in player_1_trades:
            log_to_kafka('events',player_1_trade)
        for player_2_trade in player_2_trades:
            log_to_kafka('events',player_2_trade)
       
        #return the trade status and updated inventory/gold status for both players
        trade['trade_time'] = trade_time
        return json.dumps(trade)

    else:
        #return cached inventory and gold state for each player along with fail reason
        cached_states = {}
        cached_states['player_1'] = working_trade.player_1_cache_state.to_dict()
        cached_states['player_2'] = working_trade.player_2_cache_state.to_dict()
        cached_states['fail_reason'] = fail_reason
        cached_states['trade_time'] = trade_time
        
        trade = working_trade.to_dict()
        player_1_trades = [construct_trade_dict(trade_id,
                                                trade['player_1']['player_id'],
                                                trade_time,
                                                i,
                                                trade['player_1']['gold_traded'],
                                                valid_trade,
                                                fail_reason) for i in trade['player_1']['items_traded']]
        player_2_trades = [construct_trade_dict(trade_id,
                                                trade['player_2']['player_id'],
                                                trade_time,
                                                i,
                                                trade['player_2']['gold_traded'],
                                                valid_trade,
                                                fail_reason) for i in trade['player_2']['items_traded']]
        
        #log the failed trade to kafka
        for player_1_trade in player_1_trades:
            log_to_kafka('events',player_1_trade)
        for player_2_trade in player_2_trades:
            log_to_kafka('events',player_2_trade)

        return json.dumps(cached_states)

@app.route('/create_player',methods = ['PUT'])
def create_player():
   
    creation_time = datetime.now().strftime("%m/%d/%Y, %H:%M:%S.%f")
    #grab default inventory state from file
    #default_state = json.load('./data/new_player_default_state.json')
    
    # get data from the user that created a new player. Should only contain username and  desired class. Both will be automatically generated if not provided.
    player_data = request.json
    #generate a default inventory based on item randomization or specified character class
    if type(player_data) is  None:
        player_class, player_inventory, player_gold = generate_inventory()
        player_username = pick_username()
    elif type(player_data) == dict:
        player_class, player_inventory, player_gold = generate_inventory(player_data['player_class'])
        if 'username' not in player_data.keys():
            player_username = pick_username()
        else:
            player_username = player_data['username']
    else:
        return """Player creation failed. 'username' and 'player_class' are required
        parameters. Send data as JSON.\n"""
    
    #get the max existing id from the Redis cache
    try:
        all_ids = redis_host.keys()
        numeric_ids = [int(id) for id in all_ids]
        max_existing_id = sorted(numeric_ids,reverse=True)[0]
        new_id = int(max_existing_id) + 1
    except IndexError:
        new_id = 0
    player_data['player_id'] = new_id
    player_data['inventory'] = player_inventory
    player_data['gold'] = player_gold
    player_data['player_class'] = player_class
    player_data['username'] = player_username
    
    # push the new player state to Redis
    set_player_inventory_state(new_id,json.dumps(player_data))
    state_id = create_state_id(player_username,new_id,creation_time)
    player_states = [construct_state_dict(state_id,
                                            new_id,
                                            player_username,
                                            player_class,
                                            creation_time,
                                            player_inventory['max_capacity'],
                                            player_inventory['current_capacity'],
                                            i,
                                            player_gold) for i in player_data['inventory']['items']]

    # log player creation to Kafka
    for player_state in player_states:
        log_to_kafka('events',player_state)
   
    # return a success message
    success_message = 'New %s (player_id = %i) with username = %s created.\n'%(player_class,new_id,player_data['username'])
    print(success_message)
    return success_message

def get_player_inventory_state(player_id):
    '''
    Merely a wrapper for reading from the Redis cache. 
    Returns a dict created from a string parsed as JSON.
    '''
    state = json.loads(redis_host.get(str(player_id)))
    return state
    
def set_player_inventory_state(player_id,inventory_state = {}):
    '''
    Sets a player's inventory to the specified dictionary object converted to JSON.
    Returns the new inventory state.
    '''
    iv_state_json = json.dumps(inventory_state)
    redis_host.mset({str(player_id):iv_state_json})
    return inventory_state

def log_to_kafka(topic,event):
    event.update(request.headers)
    kafka_producer.send(topic,json.dumps(event).encode())

def pick_username():
    n = random.randint(0,len(usernames)-1)
    username = usernames[n]
    return username

def construct_trade_dict(trade_id,player_id,timestamp,item_traded, gold_traded, valid_trade, fail_reason):
    trade_dict = {}
    trade_dict['event_type'] = 'trade'
    trade_dict['trade_id'] = trade_id
    trade_dict['valid_trade'] = str(valid_trade)
    trade_dict['fail_reason'] = fail_reason
    trade_dict['player_id'] = player_id
    trade_dict['trade_time'] = timestamp
    trade_dict['item_traded_item_id'] = item_traded['item_id']
    trade_dict['item_traded_name'] = item_traded['name']
    trade_dict['item_traded_level'] = item_traded['level']
    trade_dict['item_traded_value'] = item_traded['value']
    trade_dict['item_traded_quantity'] = item_traded['quantity']
    trade_dict['gold_traded'] = gold_traded
    return trade_dict

def construct_state_dict(state_id,player_id,username,player_class,timestamp,inventory_max_capacity,inventory_current_capacity,item_held, gold):
    state_dict = {}
    state_dict['event_type'] = 'player_state'
    state_dict['state_id'] = state_id
    state_dict['player_id'] = player_id
    state_dict['username'] = username
    state_dict['player_class'] = player_class
    state_dict['state_time'] = timestamp
    state_dict['inventory_max_capacity'] = inventory_max_capacity
    state_dict['inventory_current_capacity'] = inventory_current_capacity
    state_dict['item_held_item_id'] = item_held['item_id']
    state_dict['item_held_name'] = item_held['name']
    state_dict['item_held_level'] = item_held['level']
    state_dict['item_held_value'] = item_held['value']
    state_dict['item_held_quantity'] = item_held['quantity']
    state_dict['gold'] = gold
    return state_dict

def create_trade_id(p1name,p1id,p2name,p2id,trade_time):
    '''Generates an ID for a trade from each player's username, id, and the time of the trade'''
    trade_id_seed = '%s%s%s%s%s'%(p1name,p1id,p2name,p2id,trade_time)
    trade_id = hashlib.md5(trade_id_seed.encode()).hexdigest()
    return trade_id

def create_state_id(pname,pid,state_time):
    '''Generates an ID for a state player's username, id, and the time of the state change'''
    state_id_seed = '%s%s%s'%(pname,pid,state_time)
    state_id = hashlib.md5(state_id_seed.encode()).hexdigest()
    return state_id

if __name__ == '__main__':
    app.run(debug = True)
