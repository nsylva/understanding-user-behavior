from classes.Trade import Trade
from classes.Player import Player
from classes.Inventory import Inventory
from classes.Item import Item
import json
import random
import redis
import requests

#specify the Redis cache connection
redis_host = redis.Redis(host='redis',port='6379')

def choose_players():
    '''Randomly select two players and return their data in the form of a Player class instance.'''
    #get existing player ids
    player_ids = redis_host.keys()
    max_index = len(player_ids) - 1
    # choose two random players
    i = random.randint(0,max_index)
    j = random.randint(0,max_index)

    decoder = json.JSONDecoder()
    # get the data for the two chosen random players
    player_1_data_raw = decoder.raw_decode(redis_host.get(str(player_ids[i])))
    player_2_data_raw = decoder.raw_decode(redis_host.get(str(player_ids[j])))

    player_1_data = json.loads(player_1_data_raw[0])
    player_2_data = json.loads(player_2_data_raw[0])

    # create data structures for the players for easy access.
    player_1 = Player(player_1_data)
    player_2 = Player(player_2_data)

    return player_1, player_2


def choose_item(player):
    '''Picts a random item from a player's inventory'''
    random_index = random.randint(0,len(player.inventory.ids())-1)
    item = player.inventory.iqs()[random_index][0].to_dict()
    item['quantity'] = 1
    return item

def build_trade_data(player_1,player_2,player_1_items_traded,player_2_items_traded,player_1_gold_traded,player_2_gold_traded):
    '''Constructs a dictionary of data for the trade.'''
    trade = {'player_1': player_1.to_dict(), 'player_2' : player_2.to_dict()}
    trade['player_1']['items_traded'] = player_1_items_traded
    trade['player_2']['items_traded'] = player_2_items_traded
    trade['player_1']['gold_traded'] = player_1_gold_traded
    trade['player_2']['gold_traded'] = player_2_gold_traded

    return trade


def formulate_trade(player_1,player_2):
    '''
    Formulate a simple one-one item trade if both players have items.
    If one player is out of items, make the other player buy an item.
    Returns None if one or both players are out of items and gold or cannot afford to trade.
    Otherwise returns a dictionary of trade data.
    '''
    # check to see if both players have items and pick items to trade
    if player_1.inventory.current_capacity != player_1.inventory.max_capacity and player_2.inventory.current_capacity != player_2.inventory.max_capacity:
        #randomly choose items for each player
        player_1_item = choose_item(player_1)
        player_2_item = choose_item(player_2)
        return build_trade_data(player_1,player_2,[player_1_item],[player_2_item],0,0)
    #player 1 has items but player 2 does not
    elif player_1.inventory.current_capacity != player_1.inventory.max_capacity and player_2.inventory.current_capacity == player_2.inventory.max_capacity:
        player_1_item = choose_item(player_1)
        item_value = player_1_item['value']
        #check if player 2 can pay for an item. build the trade if so
        if player_2.gold >= item_value:
            return build_trade_data(player_1,player_2,[player_1_item],[],0,item_value)
        else:
            return None
    #player 2 has items but player 1 does not
    elif player_1.inventory.current_capacity == player_1.inventory.max_capacity and player_2.inventory.current_capacity != player_2.inventory.max_capacity:
        item_value = player_2_item['value']
        #check if player 1 can pay for an item. build the trade if so
        if player_1.gold >= item_value:
            return build_trade_data(player_1,player_2,[],[player_2_item],item_value,0)
        else:
            return None
    #neither players have any items and trading money for money is pointless so do nothing.
    else:
        return None

def send_trade(trade_data):
    '''Execute the trade if it works'''
    if trade_data is not None:
        r = requests.post('http://localhost:5000/trade',json=trade_data)
        if r.status_code == 200:
            print('Trade sent successfully.')
        else:
            print('Trade resulted in status code of: %i'%r.status_code)
    else:
        print('Trade failed because one or both players were out of gold and money.')

#choose the number of trades to simulate
number_of_trades = 10000

#simulate the specified number of trades.
for i in range(number_of_trades):
    player_1, player_2 = choose_players()
    trade_data = formulate_trade(player_1,player_2)
    send_trade(trade_data)




