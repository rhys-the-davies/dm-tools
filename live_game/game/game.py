import re
import yaml

from api.api import Api
from string import digits


class Character(object):
    attributes = [
            'name',
            'hp',
            'tmp_hp',
            'conditions',
    ]

    def __init__(self, argsdict):
        for k, v in argsdict.items():
            setattr(self, k, v)
        for att in Character.attributes:
            if argsdict.get(att, None) is None:
                if att == 'tmp_hp' and argsdict.get('hp', None) is not None:
                    setattr(self, att, argsdict['hp'])
                elif att == 'tmp_hp' and getattr(self, 'hp', None) is not None:
                    setattr(self, att, self.hp)
                elif att in Character.attributes[1:3]:
                    hp = argsdict.get('hp', 1)
                    hp = hp if hp > 0 else 1
                    setattr(self, att, str(hp))
                else:
                    setattr(self, att, '')

    def edit_name(self, newname):
        setattr(self, 'name', newname)


class Game(object):
    red_heart = chr(0x1f493)
    yellow_heart = chr(0x1f49b)
    green_heart = chr(0x1f49a)
    skull = chr(0x1f480)
    hearts = [red_heart, yellow_heart, green_heart, skull]
    bang = chr(0x1f535)

    def __init__(self, **kwargs):
        self.api = Api()
        self.pcs_yaml = kwargs.get('pcs_yaml')

        self.load_pcs()

        #if self.pcs == {}:
        #    raise Exception("No characters found.")

    def add_character(self, name):
        hp = self.api.monster_hp(name)
        character = Character({'name': name, 'hp': hp})
        while name in self.pcs.keys():
            last_digit_string = ''.join(filter(str.isdigit, name))
            if len(last_digit_string) > 0:
                name = name.rstrip(digits)
                last_digit = int(last_digit_string)
                name = name + str(last_digit + 1)
            else:
                name = name + '1'
        
        character.edit_name(name)
        self.pcs[name] = character
        self.conditions[name] = []

        self.pc_names.append(name)
        self.initiative_list.append(f'0 {name}')
        self.initiative[name] = 0
        self.make_pcs_status_list()
        self.write_state()

    def clear_init(self):
        for char in self.pcs.keys():
            self.set_initiative(char, 0)
            self.make_initiative_list()

    def defer_initiative(self):
        if len(self.initiative_list) < 2:
            return

        head_init_value = int(self.initiative_list[0].split()[0])
        next_init_value = int(self.initiative_list[1].split()[0])
        if head_init_value < next_init_value:
            return

        end_of_turn_index = 0
        while head_init_value >= next_init_value:
            end_of_turn_index += 1
            head_init_value = int(self.initiative_list[end_of_turn_index].split()[0])
            if end_of_turn_index+1 < len(self.initiative_list):
                next_init_value = int(self.initiative_list[end_of_turn_index+1].split()[0])
            else:
                next_init_value = 999

        start_next_index = end_of_turn_index + 1
        head_portion = self.initiative_list[1:start_next_index]
        tail_portion = []
        if start_next_index < len(self.initiative_list):
            tail_portion = self.initiative_list[start_next_index:]
        new_list = head_portion + [self.initiative_list[0]] + tail_portion
        self.initiative_list = new_list

    def load_pcs(self):
        self.conditions = {}
        self.initiative = {}
        self.pc_names = []
        self.pcs = {}
        with open(self.pcs_yaml, 'r') as fh:
            raw = yaml.load(fh, Loader=yaml.Loader)

        if raw is None:
            raw = ''

        for item in raw:
            char = item['character']
            char_name = char['name']
            self.initiative[char_name] = '0'
            self.pc_names.append(char_name)
            self.pcs[char_name] = Character(char)
            conds = char['conditions']
            if conds is None:
                conds = "None"
            self.conditions[char_name] = conds if "None" not in conds else []

        self.make_initiative_list()
        self.make_pcs_status_list()

    def make_initiative_list(self):
        if not hasattr(self, 'initiative_list'):
            sorted_pc_names = self.pc_names
        else:
            sorted_pc_names = []
            for item in self.initiative_list:
                name = ' '.join(item.split()[1:])
                if name in self.pc_names:
                    sorted_pc_names.append(name)

        self.initiative_list = [
            '{} {}'.format(self.initiative[name], name) for name in
            sorted_pc_names]

    def make_pcs_status_list(self):
        # type: () -> List[Text]
        ret_list = []

        for name in self.pc_names:
            heart = Game.green_heart

            ch = self.pcs[name]
            hp = getattr(ch, 'hp')
            tmp_hp = getattr(ch, 'tmp_hp')
            frac = float(tmp_hp) / float(hp)
            frac_text = f'{tmp_hp}/{hp}'
            conditions = getattr(ch, 'conditions')

            if frac < 1.0 and frac >= 0.5:
                heart = Game.yellow_heart
            elif frac < 0.5 and frac != 0.0:
                heart = Game.red_heart
            elif frac == 0.0:
                heart = Game.skull

            ret_list.append(f'Name: {name}')
            ret_list.append(f'  {heart} : {frac_text}')
            ret_list.append(f'  {Game.bang}:')
            for cond in conditions:
                ret_list.append(f'    {cond}')

        self.pcs_status_list = ret_list

    def next_initiative(self):
        first = self.initiative_list[0]
        rest = self.initiative_list[1:]
        self.initiative_list = rest + [first]

    def remove_character(self, name):
        if self.pcs.get(name, None) is not None:
            del self.pcs[name]
            del self.initiative[name]
            self.pc_names.remove(name)
            self.make_initiative_list()
            self.make_pcs_status_list()
            self.write_state()

    def set_initiative(self, name_expr, value):
        for name in self.pc_names:
            if re.match(name_expr, name):
                self.initiative[name] = value

        self.make_initiative_list()

    def sort_init_list(self):
        temp = sorted(self.initiative.keys(),
                      key=lambda x: int(self.initiative[x]),
                      reverse=True)
        self.initiative_list = ['{} {}'.format(self.initiative[k], k) for
                                k in temp]

    def update_hp(self, name, change, update_type, write_changes):
        tmp_hp = int(self.pcs[name].tmp_hp)
        if update_type == 'set max':
            change = change.split('.')[0]

        change_int = int(change)

        if update_type is None:
            self.pcs[name].tmp_hp = change
        elif update_type == '+':
            self.pcs[name].tmp_hp = str(tmp_hp + change_int)
        elif update_type == '-':
            self.pcs[name].tmp_hp = str(tmp_hp - change_int)
        elif update_type == 'set max':
            self.pcs[name].hp = str(int(change))
            self.pcs[name].tmp_hp = str(int(change))
        else:
            return

        self.make_pcs_status_list()

        if write_changes:
            self.write_state()

    def write_state(self):
        new = []
        for name in self.pcs.keys():
            entry = {}
            character = {}
            character['name'] = name
            character['hp'] = self.pcs[name].hp
            conds = self.conditions.get(name, None)
            character['conditions'] = conds if conds is not None else 'None'
            entry['character'] = character
            new.append(entry)

        with open(self.pcs_yaml, 'w+') as fh:
            yaml.dump(new, fh)
