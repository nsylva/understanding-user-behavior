from .Player import Player
from .Inventory import Inventory
from .Item import Item
import json
import redis

class Trade(object):
    def __init__(self, trade_data, redis_cache_connection):
        #read data in from a dictionary
        self.from_dict(trade_data)
        
        #specify a Redis cache connection that has existing player states
        self.redis_cache_connection = redis_cache_connection
        
        #connect to Redis cache and get the states
        self.get_cached_states()
        
        #validate this trade
        self.valid, self.fail_reason = self.validate()
        
    def from_dict(self,trade_data):
        
        #separate input data into two dicts, one for each player
        player_1 = trade_data['player_1']
        player_2 = trade_data['player_2']

        #generate Player class instances for each player
        self.player_1 = Player(player_1)
        self.player_2 = Player(player_2)

        #extract items to be traded and generate Inventory class instances for each set
        self.player_1_items_traded = Inventory(self.player_1.player_id, player_1['items_traded'], inv_type='trade')
        self.player_2_items_traded = Inventory(self.player_2.player_id, player_2['items_traded'], inv_type='trade')

        #extract gold trade amounts
        self.player_1_gold_traded = player_1['gold_traded']
        self.player_2_gold_traded = player_2['gold_traded']

    def to_dict(self):
        trade_dict = {}
        player_1_dict = self.player_1.to_dict()
        player_2_dict = self.player_2.to_dict()
        trade_dict['player_1'] = player_1_dict
        trade_dict['player_2'] = player_2_dict
        trade_dict['player_1']['items_traded'] = self.player_1_items_traded.to_dict()['items']
        trade_dict['player_2']['items_traded'] = self.player_2_items_traded.to_dict()['items']
        trade_dict['player_1']['gold_traded'] = self.player_1_gold_traded
        trade_dict['player_2']['gold_traded'] = self.player_2_gold_traded
        trade_dict['is_valid'] = self.valid
        trade_dict['fail_reason'] = self.fail_reason

        return trade_dict


    def get_cached_states(self):
        #print('p1 cache state pre-parsed: %s'%type(self.redis_cache_connection.get(str(self.player_1.player_id))))
        #print('p2 cache state pre-parsed: %s'%type(self.redis_cache_connection.get(str(self.player_2.player_id))))
        decoder = json.JSONDecoder()
        #load raw cache states from Redis and parse as dict
        player_1_cache_state_raw = decoder.raw_decode(self.redis_cache_connection.get(str(self.player_1.player_id)))
        player_2_cache_state_raw = decoder.raw_decode(self.redis_cache_connection.get(str(self.player_2.player_id)))
        
        player_1_cache_state_dict = json.loads(player_1_cache_state_raw[0])
        player_2_cache_state_dict = json.loads(player_2_cache_state_raw[0])
        
        #instantiate Player class instances for the cache states
        self.player_1_cache_state = Player(player_1_cache_state_dict)
        self.player_2_cache_state = Player(player_2_cache_state_dict)
    
    def validate(self):

        #get total trade item counts for each player and calc net item gains
        num_items_player_1_receiving = self.player_2_items_traded.total_items
        num_items_player_2_receiving = self.player_1_items_traded.total_items
        player_1_net_item_gain = num_items_player_1_receiving - num_items_player_2_receiving
        player_2_net_item_gain = num_items_player_2_receiving - num_items_player_1_receiving
        
        #make sure that the players have the items to trade away
        player_1_inv_state = True
        for iq in self.player_1_items_traded.iqs():
            i = iq[0]
            q = iq[1]
            if i.item_id not in self.player_1.inventory.ids():
                print('p1 inv state failed no id')
                player_1_inv_state = False
                break
            elif q > self.player_1.inventory._items[i.item_id][1]:
                print('p1 inv state failed on quantity')
                player_1_inv_state = False
                break

        player_2_inv_state = True
        for iq in self.player_2_items_traded.iqs():
            i = iq[0]
            q = iq[1]
            if i.item_id not in self.player_2.inventory.ids():
                print('p2 inv state failed no id')
                player_2_inv_state = False
                break
            elif q > self.player_2.inventory._items[i.item_id][1]:
                print('p2 inv state failed on quantity')
                player_2_inv_state = False
                break

        # Compare cached inventory state to inventory in trade_data. Ensure request
        # does not contain spoofed inventory data.
        if self.player_1.inventory != self.player_1_cache_state.inventory:
            valid = False
            fail_reason = 'Player 1 (player_id = %i) inventory does not match cached inventory.\n'%self.player_1.player_id
        elif self.player_2.inventory != self.player_2_cache_state.inventory:
            valid = False
            fail_reason = 'Player 2 (player_id = %i) inventory does not match cached inventory.\n'%self.player_2.player_id
            print(self.player_2.inventory, self.player_2_cache_state.inventory)
        
        # also check that the gold amount in the trade request is equal to the cached amount
        elif self.player_1.gold != self.player_1_cache_state.gold:
            valid = False
            fail_reason = 'Player 1 (player_id = %i) gold count (%i) does not match cached gold count (%i).\n'%(self.player_1.player_id,self.player_1.gold ,self.player_1_cache_state.gold)
        elif self.player_2.gold != self.player_2_cache_state.gold:
            valid = False
            fail_reason = 'Player 2 (player_id = %i) gold count (%i) does not match cached gold count (%i).\n'%(self.player_2.player_id,self.player_2.gold,self.player_2_cache_state.gold)
    
        # Also ensure that, if gold is being traded, the players have enough gold to execute the trade.
        elif self.player_1.gold < self.player_1_cache_state.gold:
            valid = False
            fail_reason = 'Player 1 (player_id = %i) does not have enough gold.\n'%self.player_1.player_id
        elif self.player_2.gold < self.player_2_cache_state.gold:
            valid = False
            fail_reason = 'Player 2 (player_id = %i) does not have enough gold.\n'%self.player_2.player_id
        
        # Check inventory capacity and ensure that both players have enough
        # capacity in their inventory to execute the trade.
        elif self.player_1.inventory.current_capacity < player_1_net_item_gain:
            valid = False
            fail_reason = 'Player 1 (player_id = %i) does not have enough inventory space for this trade.\n'%self.player_1.player_id
        elif self.player_2.inventory.current_capacity < player_2_net_item_gain:
            fail_reason = 'Player 2 (player_id = %i) does not have enough inventory space for this trade.\n'%self.player_2.player_id
        #ensure each player has the items to trade
        elif not player_1_inv_state:
            valid = False
            fail_reason = 'Player 1 (player_id = %i) does not have the items proposed to trade in the inventory.\n'%self.player_1.player_id
        elif not player_2_inv_state:
            valid = False
            fail_reason = 'Player 2 (player_id = %i) does not have the items proposed to trade in the inventory.\n'%self.player_2.player_id
        else:
            valid = True
            fail_reason = 'N/A'
        
        return valid, fail_reason

    def execute_trade(self):
        #for both players, update their inventory by removing items they are getting rid of
        # and adding items they are getting.
        for iq in self.player_1_items_traded.iqs():
            item = iq[0]
            quantity = iq[1]

            self.player_2.inventory.add_item(item,quantity)                
            self.player_1.inventory.remove_item(item,quantity)

        for iq in self.player_2_items_traded.iqs():
            item = iq[0]
            quantity = iq[1]
            
            self.player_1.inventory.add_item(item,quantity)
            self.player_2.inventory.remove_item(item,quantity)

        #add and remove gold for both players.
        self.player_1.remove_gold(self.player_1_gold_traded)
        self.player_1.add_gold(self.player_2_gold_traded)

        self.player_2.remove_gold(self.player_2_gold_traded)
        self.player_2.add_gold(self.player_1_gold_traded)
