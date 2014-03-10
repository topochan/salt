# -*- coding: utf-8 -*-
'''
The behaviors to run the salt master via ioflo
'''

# Import python libs
from collections import deque

# Import salt libs
import salt.daemons.masterapi
from salt.transport.road.raet import stacking
from salt.transport.road.raet import yarding

# Import ioflo libs
import ioflo.base.deeding


@ioflo.base.deeding.deedify('master_keys', ioinits={'opts': '.salt.etc.opts', 'keys': '.salt.etc.keys.master'})
def master_keys(self):
    '''
    Return the master keys
    '''
    self.keys.value = salt.daemons.masterapi.master_keys(self.opts.value)


@ioflo.base.deeding.deedify('clean_old_jobs', ioinits={'opts': '.salt.etc.opts'})
def clean_old_jobs(self):
    '''
    Call the clan old jobs routine
    '''
    salt.daemons.masterapi.clean_old_jobs(self.opts.value)


@ioflo.base.deeding.deedify('access_keys', ioinits={'opts': '.salt.etc.opts'})
def access_keys(self):
    '''
    Build the access keys
    '''
    salt.daemons.masterapi.access_keys(self.opts.value)


@ioflo.base.deeding.deedify('fileserver_update', ioinits={'opts': '.salt.etc.opts'})
def fileserver_update(self):
    '''
    Update the fileserver backends
    '''
    salt.daemons.masterapi.fileserver_update(self.opts.value)


class RouterMaster(ioflo.base.deeding.Deed):  # pylint: disable=W0232
    '''
    Routes the communication in and out of uxd connections
    '''
    Ioinits = {'opts': '.salt.opts',
               'event_yards': '.salt.uxd.yards.event',
               'com_yards': '.salt.uxd.yards.com',
               'local_cmd': '.salt.uxd.local_cmd',
               'local_ret': '.salt.uxd.local_ret',
               'events': '.salt.uxd.events',
               'publish': '.salt.net.publish',
               'stack': '.salt.uxd.stack.stack',
               'udp_stack': '.raet.udp.stack.stack'}

    def postinitio(self):
        '''
        Set up required objects
        '''
        self.stack.value = stacking.StackUxd(
                name='router',
                lanename='master',
                yid=0,
                dirpath=self.opts.value['sock_dir'])
        self.event_yards.value = set()
        self.com_yards.value = set()
        self.local_cmd.value = deque()
        self.local_ret.value = deque()
        self.events.value = deque()
        if not self.publish.value:
            self.publish.value = deque()

    def _register_event_yard(self, msg):
        '''
        register an incoming event request with the requesting yard id
        '''
        ev_yard = yarding.Yard(
                yid=msg['load']['yid'],
                prefix='master',
                dirpath=msg['load']['dirpath'])
        self.event_yards.value.add(ev_yard.name)

    def _fire_event(self, event):
        '''
        Fire an event to all subscribed yards
        '''
        for y_name in self.event_yards.value:
            route = {'src': ('router', self.stack.value.yard.name, None),
                     'dst': ('router', y_name, None)}
            msg = {'route': route, 'event': event}
            self.stack.value.transmit(msg, y_name)

    def _process_rxmsg(self, msg):
        '''
        Send the message to the correct location
        '''
        try:
            if msg['route']['dst'][2] == 'local_cmd':
                self.local_cmd.value.append(msg)
            elif msg['route']['dst'][2] == 'event_req':
                # Register the event interface
                self._register_event_yard(msg)
            elif msg['route']['dst'][2] == 'event_fire':
                # Register the event interface
                self.events.value.append(
                        {'tag': msg['tag'],
                         'data': msg['data']})
        except Exception:
            return

    def _publish(self, pub_msg):
        '''
        Publish the message out to the targetted minions
        '''
        import pprint
        pprint.pprint(self.udp_stack.value.eids)
        pprint.pprint(pub_msg)
        for minion in self.udp_stack.value.eids:
            eid = self.udp_stack.value.eids.get(minion)
            if eid:
                route = {'dst': (minion, None, 'fun')}
                msg = {'route': route, 'pub': pub_msg['pub']}
                self.udp_stack.value.message(msg, eid)

    def action(self):
        '''
        Process the messages!
        '''
        self.stack.value.serviceAll()
        # Process inboud communication stack
        while self.stack.value.rxMsgs:
            self._process_rxmsg(self.stack.value.rxMsgs.popleft())
        while self.events.value:
            self._fire_event(self.events.value.popleft())
        while self.local_ret.value:
            msg = self.local_ret.value.popleft()
            self.stack.value.transmit(msg, msg['route']['dst'][1])
        while self.publish.value:
            pub_msg = self.publish.value.popleft()
            self._publish(pub_msg)
        self.stack.value.serviceAll()


class RemoteMaster(ioflo.base.deeding.Deed):  # pylint: disable=W0232
    '''
    Abstract access to the core salt master api
    '''
    Ioinits = {'opts': '.salt.opts',
               'ret_in': '.salt.net.ret_in',
               'ret_out': '.salt.net.ret_out'}

    def postinitio(self):
        '''
        Set up required objects
        '''
        self.remote = salt.daemons.masterapi.RemoteFuncs(self.opts.value)

    def action(self):
        '''
        Perform an action
        '''
        if self.ret_in.value:
            exchange = self.ret_in.value.pop()
            load = exchange.get('load')
            # If the load is invalid, just ignore the request
            if not 'cmd' in load:
                return False
            if load['cmd'].startswith('__'):
                return False
            exchange['ret'] = getattr(self.remote, load['cmd'])(load)
            self.ret_out.value.append(exchange)


class LocalCmd(ioflo.base.deeding.Deed):  # pylint: disable=W0232
    '''
    Abstract access to the core salt master api
    '''
    Ioinits = {'opts': '.salt.opts',
               'local_cmd': '.salt.uxd.local_cmd',
               'local_ret': '.salt.uxd.local_ret',
               'publish': '.salt.net.publish',
               'stack': '.salt.uxd.stack.stack'}

    def postinitio(self):
        '''
        Set up required objects
        '''
        self.access_keys = salt.daemons.masterapi.access_keys(self.opts.value)
        self.local = salt.daemons.masterapi.LocalFuncs(self.opts.value, self.access_keys)
        if not self.publish.value:
            self.publish.value = deque()

    def action(self):
        '''
        Perform an action
        '''
        while self.local_cmd.value:
            cmd = self.local_cmd.value.popleft()
            ret = {}
            load = cmd.get('load')
            # If the load is invalid, just ignore the request
            if not 'cmd' in load:
                return
            if load['cmd'].startswith('__'):
                return
            if hasattr(self.local, load['cmd']):
                ret['return'] = getattr(self.local, load['cmd'])(load)
                ret['route'] = {'src': ('router', self.stack.value.yard.name, None),
                                'dst': cmd['route']['src']}
                if load['cmd'] == 'publish':
                    self.publish.value.append(ret['return'])
            self.local_ret.value.append(ret)
