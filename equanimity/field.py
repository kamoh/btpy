import transaction
import persistent
import binary_tactics.stone
from equanimity.wstone import Stone
binary_tactics.stone.Stone = Stone #Monkey Patch
from binary_tactics.helpers import *
from binary_tactics.units import Squad
from binary_tactics.grid import Grid, Loc
from binary_tactics.player import Player
from binary_tactics.hex_battlefield import Battlefield
from equanimity.battle import Game

from equanimity.stronghold import Stronghold, Silo
from equanimity.clock import Clock
from math import ceil

class Field(persistent.Persistent):
    """Player owned field logic."""
    def __init__(self, world_coord, ply_time=240):
        self.world_coord = world_coord
        self.owner = 'World'
        self.grid = Grid()
        self.element = 'Ice' #For testing
        #self.element = get_element(self.grid.comp)
        self.clock = Clock()
        self.stronghold  = Stronghold(self.element, self.clock)
        self.plantings   = persistent.mapping.PersistentMapping()
        self.battlequeue = persistent.list.PersistentList()
        self.game = None
        self.state = 'produce' #Default state
        """
        ply_time: user definable time before a pass is automatically sent for a battle action.
            range between 4 and 360 minutes, default is 4 (in seconds)
        """
        self.ply_time = ply_time

    def setup_battle(self):
        #load the battlefield with players (and squads)
        atkr_name, atksquad = self.battlequeue[0] #TODO change to pop 
        defsquad = self.get_defenders()
        dfndr = Player(self.owner, [defsquad])
        atkr = Player(atkr_name, [atksquad])
        #TODO write a new game object.
        self.game = Game(grid=self.grid, defender=dfndr, attacker=atkr)
        #place units on battlefield
        self.game.put_squads_on_field()
        return transaction.commit()
        
    def set_owner(self, owner):
        self.owner = owner
        return tranaction.commit()
    
    def change_state(self):
        #called everyday by world?
        #should be a proper state machine, too focused to find one.
        if self.battleque:
            if self.state == 'produce':
                self.state = 'battle'
                self.setup_battle()
            else:
                pass
        
        elif self.element == self.clock.get_time('season'):
            self.state = 'harvest'
        else:
            self.state = 'produce'
        return transaction.commit()
    
    def get_defenders(self):
        """gets the defenders of a Field."""
        try:
            return self.stronghold.defenders
        except:
            raise Exception("Stronghold has no defenders.")
    
    def set_stronghold_capacity(self):
        """Uses grid.value to determine stronghold capacity."""
        #squad points. scient = 1 nescient = 2
        #capacity increases at:
        # [61, 125, 189, 253, 317, 381, 445, 509, 573, 637, 701, 765, 829,
        #  893, 957,]
        self.stronghold.capacity = int(ceil((self.grid.value() + 4) / 64.0)) * 8
        self.stronghold._p_changed = 1
        return transaction.commit()
    
    def get_tile_comps(self):
        """returns a list of stones 1/8th the value of the tile comps."""
        stone_list =[]
        for x in xrange(self.grid.x):
            for y in xrange(self.grid.y):
                s = Stone()
                for suit, value in self.grid[x][y].comp.iteritems():
                    stone[suit] += value / 8 #this 8 will need to be tweaked.
                if stone.value() != 0:
                    stone_list += [stone]
        return stone_list
    
    def set_silo_limit(self):
        """Sets the silo limit to 1 year's worth of stones."""
        #this uses get_tile_comps so the / 8 is only maintained in one place.
        limit = {'Earth': 0, 'Fire': 0, 'Ice': 0, 'Wind':0}
        for stone in self.get_tile_comps():
            for element in limit.values():
                limit[element] += stone[element]
        return self.stronghold.silo.set_limit(limit)
    
    def add_planting(self, tileLoc, comp):
        self.planting[tileLoc] = comp, sum(comp.values())
        return transaction.commit()
    
    def plant(self):
        """Plants from self.plantlings"""
        if self.stronghold.farm.produce(self.plantings):
            for tileLoc, comp  in self.plantings.iteritems():
                stone = self.stronghold.silo.get(comp)
                self.grid.imbue_tile(tileLoc, stone)
                self.grid[tileLoc[0]][tileLoc[1]]._p_changed = 1
                self.grid._p_changed = 1
                self.element = get_element(self.grid.comp)
                self._p_changed = 1
                self.set_stronghold_capacity()
                self.set_silo_limit()
                return transaction.commit()
    
    def harvest(self):
        """returns set of stones generated at harvest"""
        #this needs to be more clever and relate to the units in
        #the stronghold somehow.
        #happens once a year.
        return self.stronghold.silo.imbue_list(self.get_tile_comps())


