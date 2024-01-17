from datetime import timedelta, datetime as dt
from XXXX import PITags
from XXXX import *

class DrumStates(PITags): 
    def __init__(self, log):
        PITags.__init__(self)
        self.log = log
        self.iso_valves = { 
            self.D1_switch: 'N', 
            self.D2_switch: 'N',
            self.D3_switch: 'N' 
        }

        self._init_states()
    
    def _init_states(self):
        t = dcs_data_pb2.Timer()
        t.type = NO_TIMER

        self.states = []
        for _ in range(6): # [ D1A, D1B, D2A, D2B, D3A, D3B ] 
            self.states.append({'stage': None, 'timer': t})

        t = None

    def _check_iso_valve_timer(self, pos):
        """
        *** Since A & B drums share valves, self.iso_valves is only update 
        after B completes check. If A updated self.iso_valves B's trigger 
        condition would always be missed. Every second dictionary in 
        DRUM_TAGS holds the tags of a B drum, therefore (pos + 1) % 2 == 0 
        is only True for B drums.
        If timer is tiggered for A it can't be triggered for B so it is safe to 
        update self.iso_valves.
        """
        val = str(self.get_tag_value(self.drum_tags[pos]['isotimer']))

        if ( self.iso_valves[self.drum_tags[pos]['isotimer']] == 'MIDPOINT' and 
             val == ISO_TIMER_TRIGGERS[pos]):

            self.iso_valves[self.drum_tags[pos]['isotimer']] = val
            print(f'pos: {pos} val: {val}')
            return True
            
        if (pos + 1) % 2 == 0:      # ***
            self.iso_valves[self.drum_tags[pos]['isotimer']] = val

        return False

    def _clear_timer(self, timer):
        if ( timer.type != NO_TIMER and
             dt.now() - dt.strptime(timer.start, "%Y-%m-%dT%H:%M:%S") >= 
                    timedelta(minutes=timer.duration)):
            timer.type = NO_TIMER

    def _set_timer(self, pos):
        '''Checks if any conditions for stage timers are met and sets drum 
        stage accordingly.

        There can only be one active timer for each drum at any given time.
        Therefore it is important to consider order of checks when adding 
        new timers 

        :parma pos: drum list index 
        '''
        if self._check_iso_valve_timer(pos):
            self.states[pos]['timer'].type = ISO_TIMER
            self.states[pos]['timer'].start = dt.now().strftime("%Y-%m-%dT%H:%M:%S")
            self.states[pos]['timer'].duration = ISO_DURATION
            self.states[pos]['timer'].details = ISO_VAVLE_DETAILS[pos]

        ### Add stage timer checks here ### 

    def _set_stage(self, stage, pos):
        '''Retrieves cut cycle stage of drum from PI SDK.

        :param stage: current drum cut cycle sequence stage from PI 
        :parma pos: drum list index 

        If stage is not in the list of recognized stages the stage of 
        self.stages[pos] is not updated.
        '''
        if stage in ['Charging', 'Switching', 'Steam to Frac', 
            'Vapor Diversion', 'Steam to BD', 'Water Quench', 'Venting',
            'Draining', 'Cutting', 'O2 Freeing', 'Press Test', 'Back Warming']:

            self.states[pos]['stage'] = stage

    def _set_drum_stage(self, stage, state):  
        if stage in ['Charging']:
            state.stage = dcs_data_pb2.State.Stage.ONLINE
        elif stage in ['Switching']:
            state.stage = dcs_data_pb2.State.Stage.SWITCH
        elif stage in ['Steam to Frac', 'Vapor Diversion', 'Steam to BD']:
            state.stage = dcs_data_pb2.State.Stage.STEAM
        elif stage in ['Water Quench']:
            state.stage = dcs_data_pb2.State.Stage.QUENCH
        elif stage in ['Venting']:
            state.stage = dcs_data_pb2.State.Stage.VENT
        elif stage in ['Draining']:
            state.stage = dcs_data_pb2.State.Stage.DRAIN
        elif stage in ['Cutting']:
            state.stage = dcs_data_pb2.State.Stage.CUT
        elif stage in ['O2 Freeing']:
            state.stage = dcs_data_pb2.State.Stage.O2FREE
        elif stage in ['Press Test']:
            state.stage = dcs_data_pb2.State.Stage.PRESTST
        elif stage in ['Back Warming']:
            state.stage = dcs_data_pb2.State.Stage.PREWARM
        else:
            state.stage = dcs_data_pb2.State.Stage.UNSET

    def get_drum_stage(self, drum):
        return self.states[drum]['stage']

    def get_drums_msg(self, msg):
        """Sets valves of Drums message from dcs_data_pb2.
        NOTE: state.timer_start will only be set if there is a active timer
        :param drums: Response message drumss field 
        """
        for pos, state in enumerate(self.states):
            if pos == 0:
                msg.D1A.timer.CopyFrom(state['timer'])
                self._set_drum_stage(state['stage'], msg.D1A)
            elif pos == 1:
                msg.D1B.timer.CopyFrom(state['timer'])
                self._set_drum_stage(state['stage'], msg.D1B)
            elif pos == 2:
                msg.D2A.timer.CopyFrom(state['timer'])
                self._set_drum_stage(state['stage'], msg.D2A)
            elif pos == 3:
                msg.D2B.timer.CopyFrom(state['timer'])
                self._set_drum_stage(state['stage'], msg.D2B)
            elif pos == 4:
                msg.D3A.timer.CopyFrom(state['timer'])
                self._set_drum_stage(state['stage'], msg.D3A)
            elif pos == 5:
                msg.D3B.timer.CopyFrom(state['timer'])
                self._set_drum_stage(state['stage'], msg.D3B)

    def update_state(self, drum, stage):
        try:
            self._clear_timer(self.states[drum]['timer'])
            self._set_timer(drum)
            self._set_stage(stage, drum)

        except Exception as exc:
            self.log.put(f'Error updating drum state - {exc}')