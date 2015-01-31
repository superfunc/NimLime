import sublime
import sublime_plugin
import sys
import re
import subprocess
from threading import Thread
import os
import imp

st_version = 2
if int(sublime.version()) > 3000:
    st_version = 3
    from queue import Queue
else:
    from Queue import Queue

try:  # Python 3
    from NimLime.Project import Utility
except ImportError:  # Python 2:
    from Project import Utility

useService = True

class Idetools:

    # Fields
    service = None
    outThread = None
    stdout_queue = None

    pattern = re.compile(
        '^(?P<cmd>\S+)\s(?P<ast>\S+)\s' +
        '(?P<symbol>\S+)( (?P<instance>\S+))?\s' +
        '(?P<type>[^\t]+)\s(?P<path>[^\t]+)\s' +
        '(?P<line>\d+)\s(?P<col>\d+)\s' +
        '(?P<description>\".+\")?')

    # Methods
    @staticmethod
    def enqueue_output(out, queue):
        for line in iter(out.readline, b''):
            if line != "" and line[0] == '>':
                queue.put(line[2:])

    @staticmethod
    def dump_output():
        Idetools.stdout_queue.queue.clear()

    @staticmethod
    def get_line():
        try:
            return Idetools.stdout_queue.get(True, 4)
        except:
            return ""

    @staticmethod
    def ensure_service(proj=""):
        # If service is running, do nothing
        if Idetools.service is not None and Idetools.service.poll() is None:
            return Idetools.service

        proc = subprocess.Popen(
            "nimsuggest --stdin " + proj,
            bufsize=0,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            shell=True)

        Idetools.stdout_queue = Queue()
        Idetools.service   = proc
        Idetools.outThread = Thread(target=Idetools.enqueue_output,
                                    args=(proc.stdout, Idetools.stdout_queue))
        Idetools.outThread.daemon = True
        Idetools.outThread.start()

        print("nimsuggest running: nimsuggest --stdin " + proj)
        return Idetools.service

    @staticmethod
    def idetool(win, cmd, filename, line, col, dirtyFile="", extra=""):
        trackType = " --track:"
        filePath  = filename
        projFile  = Utility.get_nimproject(win)

        if projFile is None:
            projFile = filename

        workingDir = os.path.dirname(projFile)

        if useService:
            if dirtyFile != "":
                filePath = filePath + '";"' + dirtyFile

            # Ensure IDE Tools service is running
            proc = Idetools.ensure_service(projFile)
            Idetools.dump_output()

            # Call the service
            args = 'def "' + filePath + '":' + str(line) + ":" + str(col)
            print(args)

            # Dump queued info & write to stdin
            proc.stdin.write(args + '\r\n')

            # Read result
            return Idetools.get_line()

        else:
            if dirtyFile != "":
                trackType = " --trackDirty:"
                filePath = dirtyFile + "," + filePath

            compiler = sublime.load_settings("nim.sublime-settings")\
                              .get("nim_compiler_executable")
            if compiler == None or compiler == "": return ""

            args = compiler + " --verbosity:0 idetools " \
                + trackType \
                + '"' + filePath + "," + str(line) + "," + str(col) \
                + '" ' + cmd + ' "' + projFile + '"' + extra
            print(args)

            output = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                cwd=workingDir)

            temp = output.stdout.read()

            # Convert bytes to string
            output.wait()
            return temp.decode('utf-8')

    @staticmethod
    def parse(result):
        m = Idetools.pattern.match(result)

        if m is not None:
            cmd = m.group("cmd")

            if cmd == "def":
                return (m.group("symbol"), m.group("type"),
                        m.group("path"), m.group("line"),
                        m.group("col"), m.group("description"))
        else:
            None

        return None


# Retrieve modules to reload
reload_mods = []
for mod in sys.modules:
    if mod[0:7] == 'NimLime' and sys.modules[mod] != None:
        reload_mods.append(mod)

# Reload modules
mods_load_order = [
    'NimLime',
    'NimLime.Project',
    'NimLime.Nim',
    'NimLime.Lookup',
    'NimLime.Documentation',
    'NimLime.Nimble',
    'NimLime.AutoComplete'
]

mod_load_prefix = ''
if st_version == 3:
    mod_load_prefix = 'NimLime.'
    from imp import reload

for mod in mods_load_order:
    if mod in reload_mods:
        reload(sys.modules[mod])
        print("reloading " + mod)