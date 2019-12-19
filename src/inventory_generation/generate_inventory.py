import random
import json
import os

def generate_inventory(player_class = 'random'):
    
    #define path and load default inventories.
    script_dir = os.path.dirname(__file__)
    rel_path = 'class_default_inventories.json'
    file_path = os.path.join(script_dir,rel_path)
    
    with open(file_path, 'r') as json_file:
        class_inventories = json.load(json_file)

    if player_class == 'random':
        # list of classes with extra entries for more likely classes
        classes = ['blacksmith', 'blacksmith',\
                   'alchemist', 'alchemist',\
                   'farmer', 'farmer', 'farmer', 'farmer',\
                   'hunter', 'hunter', 'hunter', 'hunter',\
                   'tailor', 'tailor',\
                   'trader',\
                   'aristocrat',\
                   'leatherworker','leatherworker',
                   'banker',\
                   'warrior']

        #generate a random number in (0, 1]
        n = random.randint(0,19)
        
        # set player_class based on the random number
        player_class = classes[n]
    
    player_inventory = class_inventories[player_class]['inventory']
    player_gold = class_inventories[player_class]['gold']

    return player_class, player_inventory, player_gold

