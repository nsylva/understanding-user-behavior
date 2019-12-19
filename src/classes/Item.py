class Item(object):
    def __init__(self,item_id,name,level, value):
        self.item_id = item_id
        self.name = name
        self.level = level
        self.value = value
    
    def to_dict(self):
        item_dict = {}
        item_dict['item_id'] = self.item_id
        item_dict['name'] = self.name
        item_dict['level'] = self.level
        item_dict['value'] = self.value
        return item_dict