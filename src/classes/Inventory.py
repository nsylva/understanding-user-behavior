from .Item import Item

class Inventory(object):
    def __init__(self,id,inventory, inv_type):
        self.id = id
        self.inv_type = inv_type
        if self.inv_type == 'state':
            self._items = self.build_items(inventory['items'])
            self.max_capacity = inventory['max_capacity']
        else:
            self._items = self.build_items(inventory)
            self.max_capacity = 999
            self.current_capacity = 999
        self.total_items = sum([i[1] for i in self.iqs()])
        self.current_capacity = self.max_capacity-self.total_items
        
    def build_items(self,items):
        contained_items = {}
        for item in items:
            new_item, quantity = Item(item['item_id'],item['name'],item['level'],item['value']), item['quantity']
            contained_items[new_item.item_id] = (new_item, quantity)
        return contained_items

    def add_item(self,item,quantity):
        new_item = Item(item.item_id,item.name,item.level,item.value)
        if new_item.item_id in self._items.keys():
            current_quantity = self._items[new_item.item_id][1]
            self._items[item.item_id] = (new_item, current_quantity + quantity)
            print('Added %i of item %s (id=%i) to inventory for player_id = %s. New Quantity: %i'%(quantity,new_item.name, new_item.item_id,self.id,self._items[new_item.item_id][1]))
        else:
            self._items[new_item.item_id] = (new_item, quantity)
            print('Added %i of item %s (id=%i) to inventory for player_id = %s as a new item.'%(quantity,new_item.name,new_item.item_id,self.id))
        self.current_capacity -= quantity

    def remove_item(self, item, quantity):
        if self._items[item.item_id][1] - quantity == 0:
            #remove the item completely
            print('Removed item %s (id=%i) from inventory for player_id = %s completely'%(item.name,item.item_id,self.id))
            del self._items[item.item_id]
            self.current_capacity += quantity
        else:
            current_quantity = self._items[item.item_id][1]
            self._items[item.item_id] = (item, current_quantity - quantity)
            self.current_capacity += quantity
            print('Removed item %s (id=%i) from inventory for player_id = %s. New Quantity: %i'%(item.name,item.item_id,self.id,self._items[item.item_id][1]))

    def check_capacity(self,amount, inverse = False):
        if inverse and self.current_capacity - amount >= 0:
            return True
        elif self.current_capacity + amount <= self.max_capacity:
            return True
        else:
            return False

    def to_dict(self):
        inventory = {'max_capacity' : self.max_capacity,\
                     'current_capacity' : self.current_capacity,\
                     'items' : []\
                    }
        for item in self._items.values():
            item_dict = item[0].to_dict()
            item_dict['quantity'] = item[1]
            inventory['items'].append(item_dict)
        return inventory


    def __eq__(self,other):
        
        #check if the inventories have the same current capacity
        if self.current_capacity != other.current_capacity:
            print('capacities are not equal.')
            return False
        #check if this object and other object have the same item keys
        elif sorted(self.ids()) != sorted(other.ids()):
            print('keys are not the same')
            return False
        else:
            #iterate over the items, if any of them do not match in quantity
            for item in self.iqs():
                this_item_quantity = item[1]
                other_item_quantity = other._items[item[0].item_id][1]
                if this_item_quantity != other_item_quantity:
                    print('item counts not equal')
                    return False
        print('inventories equal')
        return True

    def __ne__(self,other):
         #iterate over the items, if any of them do not match in quantity
        item_quants_equal = True
        for item in self.iqs():
            this_item_quantity = item[1]
            other_item_quantity = other._items[item[0].item_id][1]
            if this_item_quantity != other_item_quantity:
                print('item counts not equal')
                item_quants_equal = False

        if item_quants_equal and sorted(self.ids()) == sorted(other.ids()):
            return False

        return True
    '''
    def __lt__(self,other):
        if self.current_capacity > other.current_capacity:
            print('inventory is lt')
            return True
        return False

    def __gt__(self,other):
        if self.current_capacity < other.current_capacity:
            print('inventory is gt')
            return True
        return False 
    '''

    def __getitem__(self, id):
        return self._items[id]

    def __iter__(self):
        return iter(self._items)

    def ids(self):
        return self._items.keys()

    def items(self):
        return self._items.items()

    def iqs(self):
        return self._items.values()
