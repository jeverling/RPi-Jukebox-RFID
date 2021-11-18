# MIT License
#
# Copyright (c) 2021 Micz Flor
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Contributing author(s):
# - Christian Banz
# - arne123
#
"""
A GPIO Simulator GUI using a TK for development purposes

attention, running two tk toplevel processes in one python environment causes trouble, also here.
Due to the fakt that these gui's (this one and the rfid reader) are quit simple it is somehow running.
Refer to the following thread, which gives some explanation.

https://stackoverflow.com/questions/48045401/why-are-multiple-instances-of-tk-discouraged

It is important that this gui start after the rfid reader gui.

so far just inputs are handled

"""  # noqa: E501


import logging
import threading
import time
import jukebox.plugs as plugs
import jukebox.cfghandler
import jukebox.utils as utils
# import jukebox.publishing as publishing
import tkinter as tk
import os
import signal

cfg_gpio = jukebox.cfghandler.get_handler('gpio')
cfg_main = jukebox.cfghandler.get_handler('jukebox')

gpio = None


class GpioSimulatorClass(threading.Thread):
    def __init__(self, cfg_gpio):
        self._logger = logging.getLogger('jb.gpio')
        super().__init__(name="GPIO Thread", daemon=True)

        self._cancel = threading.Event()
        self.devices = cfg_gpio['devices']

    def gen_ui(self):
        self._window = tk.Tk(baseName="GPIO")
        self._window.title('GPIO Simulator')
        self._window.protocol("WM_DELETE_WINDOW", self.gui_close)

        self.device_map = {'Button': self.Button,
                           'RotaryEncoder': self.RotaryEncoder,
                           'RockerButton': self.RockerButton,
                           'PortOut': self.PortOut}
        self.portlist = {}

        # iterate over all GPIO devices
        for dev in self.devices.keys():
            self.generate_device(self.devices[dev], dev)

    def generate_device(self, device_config, name):
        device_type = device_config['Type']

        device = self.device_map.get(device_type)

        if (device is not None):
            return (device(self._window, name, device_config))
        else:
            self._logger.error(f"Device Type \"{device_type}\" not supported in Device: {name} at {device_config.lc}")
            return None

    def gui_close(self):
        self._logger.info("GPIO GUI close requested")
        # We will just raise a Ctrl-C Interrupt with the main thread for now
        # There is now "close-down" by remote-thread call implemented at the moment
        os.kill(os.getpid(), signal.SIGINT)

    def button_cb(self, cmd):
        utils.decode_and_call_rpc_command(cmd, self._logger)

    def Button(self, top, name, config):
        B = tk.Button(top, text=name, command=lambda: self.button_cb(config['Function']))
        B.pack(side=tk.TOP, fill='x', expand=True)
        return(B)

    def RockerButton(self, top, name, config):
        frame = tk.Frame(top)
        frame.pack(side=tk.TOP, fill='x', expand=True)
        label = tk.Label(frame, text=name)
        label.pack(side=tk.LEFT)
        inc = tk.Button(frame, text="→", command=lambda: self.button_cb(config['FunctionRight']))
        inc.pack(side=tk.RIGHT)
        both = tk.Button(frame, text="⇄", command=lambda: self.button_cb(config['FunctionBoth']))
        both.pack(side=tk.RIGHT)
        dec = tk.Button(frame, text="←", command=lambda: self.button_cb(config['FunctionLeft']))
        dec.pack(side=tk.RIGHT)
        return(frame)

    def RotaryEncoder(self, top, name, config):
        frame = tk.Frame(top)
        frame.pack(side=tk.TOP, fill='x', expand=True)
        label = tk.Label(frame, text=name)
        label.pack(side=tk.LEFT)
        R = tk.Button(frame, text="⟳", command=lambda: self.button_cb(config['FunctionRight']))
        R.pack(side=tk.RIGHT)
        L = tk.Button(frame, text="⟲", command=lambda: self.button_cb(config['FunctionLeft']))
        L.pack(side=tk.RIGHT)
        return(frame)

    def PortOut(self, top, name, config):
        frame = tk.Frame(top)
        frame.pack(side=tk.TOP, fill='x', expand=True)
        label = tk.Label(frame, text=name)
        label.pack(side=tk.LEFT)

        states = config['States']
        pins = config['Pins']
        n = len(pins)

        cwidth = 32 * n + 2
        canvas = tk.Canvas(frame, height=22, width=cwidth)
        canvas.pack(side=tk.RIGHT)

        x = 0
        ind = []
        for pin in pins:
            ind.append(canvas.create_oval(2 + x, 2, 20 + x, 20, fill="red"))
            canvas.create_text(11 + x, 11, text=pin)
            x += 32

        self.portlist[name] = {'ind': ind, 'canvas': canvas, 'states': states}

    @plugs.tag
    def SetPortState(self, name, state):
        port = self.portlist[name]
        state = port['states'].get(state)

        for i, ind in enumerate(port['ind']):
            if state[i] == 1:
                fill = 'red'
            else:
                fill = 'grey'

            port['canvas'].itemconfig(ind, fill=fill)

        return 0

    @plugs.tag
    def StartPortSequence(self, name, seq):
        for step in seq:
            time.sleep(step['delay'] / 1000)
            self.SetPort(name, step['state'])
            self._window.update()

        # {1: {'delay',100,'pin':'xxx','state':1},
        # 2: {'delay',100,'pin':'xxx','state':0}}

        # {1: {'delay',100,'pin':'xxx','state':1},
        #  2: {'repeat',100,'pin':'xxx','state':0}}

        return (0)

    @plugs.tag
    def StopPortSequence(self, name):
        return (0)

    def stop(self):
        self._cancel.set()

    def run(self):
        self._logger.debug("Start GPIO Simulator GUI")

        time.sleep(0.5)  # wait until rfid fake-reader gui has been started
        self.gen_ui()

        while not self._cancel.is_set():
            self._window.update()
            self._cancel.wait(timeout=0.1)


@plugs.finalize
def finalize():
    global gpio
    jukebox.cfghandler.load_yaml(cfg_gpio, cfg_main.getn('gpio', 'gpio_rpi_config'))
    gpio = GpioSimulatorClass(cfg_gpio)
    plugs.register(gpio, name='gpio')
    gpio.start()


@plugs.atexit
def atexit(**ignored_kwargs):
    global gpio
    gpio.stop()
    return None
