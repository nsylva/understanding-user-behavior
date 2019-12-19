from .Inventory import Inventory

class Player(object):
    def __init__(self,player_data):
        self.from_dict(player_data)
        
    def from_dict(self,player_data):  
        self.player_id = player_data['player_id']
        self.username = player_data['username']
        self.inventory = Inventory(self.player_id,player_data['inventory'],inv_type = 'state')
        self.gold = player_data['gold']
        self.player_class = player_data['player_class']

    def to_dict(self):
        player_dict = {}
        player_dict['player_id'] = self.player_id
        player_dict['username'] = self.username
        player_dict['inventory'] = self.inventory.to_dict()
        player_dict['gold'] = self.gold
        player_dict['player_class'] = self.player_class

        return player_dict
    def add_gold(self,amount):
        print('Increasing gold for player_id = %s from %i by %i.'%(self.player_id,self.gold,amount))
        self.gold += amount

    
    def remove_gold(self,amount):
        if self.gold - amount < 0:
            return 'Player %s (player_id = %s) does not have enough gold.'%(self.username,self.player_id)
        else:
            print('Decreasing gold for player_id = %s from %i by %i.'%(self.player_id,self.gold,amount))
            self.gold -= amount
