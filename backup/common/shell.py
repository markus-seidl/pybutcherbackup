import os
import platform
import shlex
import subprocess

import codecs

import sys
import locale
import threading


class Shell:

    class ResultDTO:
        def __init__(self):
            self.stderr = None
            self.data = None
            self.retval = None

    def __init__(self):
        encoding = locale.getpreferredencoding()
        if encoding is None:  # This happens on Jython!
            encoding = sys.stdin.encoding
        self._encoding = encoding.lower().replace('-', '_')

    def run_cmd(self, cmd: list):
        # cmd = list()
        # cmd.append(self.gpg_location)
        # cmd.append("--batch")
        # cmd.append("--yes")  # needed because in tests the output file already exists
        # cmd.append("--output %s" % out_filename)
        # cmd.append("-d")
        # cmd.append("--passphrase")
        # cmd.append("'%s'" % self.key)
        # cmd.append(in_filename)

        process = self._open_subprocess(cmd)

        result = Shell.ResultDTO()

        self._collect_output(process, result)
        result.retval = process.wait()

        assert result.retval == 0, "The called command aborted with an error."

        return result

    def _open_subprocess(self, args=None, environment=None):
        # see http://docs.python.org/2/library/subprocess.html#converting-an-argument-sequence-to-a-string-on-windows
        cmd = shlex.split(' '.join(args))
        # log.debug("Sending command to script:%s%s" % (os.linesep, cmd))

        if platform.system() == "Windows":
            # TODO figure out what the hell is going on there.
            expand_shell = True
        else:
            expand_shell = False

        # environment = {
        #     'LANGUAGE': os.environ.get('LANGUAGE') or 'en',
        #     'GPG_TTY': os.environ.get('GPG_TTY') or '',
        #     'DISPLAY': os.environ.get('DISPLAY') or '',
        #     'GPG_AGENT_INFO': os.environ.get('GPG_AGENT_INFO') or '',
        #     'GPG_TTY': os.environ.get('GPG_TTY') or '',
        #     'GPG_PINENTRY_PATH': os.environ.get('GPG_PINENTRY_PATH') or '',
        # }

        return subprocess.Popen(cmd, shell=expand_shell,
                                # stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env=environment)

    def _read_data(self, stream, result):
        """Incrementally read from ``stream`` and store read data.
        All data gathered from calling ``stream.read()`` will be concatenated and written to result.data.

        :param stream: An open file-like object to read() from.
        """
        chunks = []
        # log.debug("Reading data from stream %r..." % stream.__repr__())

        while True:
            data = stream.read(1024)
            if len(data) == 0:
                break
            chunks.append(data)
            # log.debug("Read %4d bytes" % len(data))

        # Join using b'' or '', as appropriate
        result.data = type(data)().join(chunks)
        # log.debug("Finishing reading from stream %r..." % stream.__repr__())
        # log.debug("Read %4d bytes total" % len(result.data))

    def _collect_output(self, process, result, writer=None, stdin=None):
        """Drain the subprocesses output streams, writing the collected output
        to the result. If a writer thread (writing to the subprocess) is given,
        make sure it's joined before returning. If a stdin stream is given,
        close it before returning.
        """
        stderr = codecs.getreader(self._encoding)(process.stderr)
        rr = threading.Thread(target=self._read_response,
                              args=(stderr, result))
        rr.setDaemon(True)
        # log.debug('stderr reader: %r', rr)
        rr.start()

        stdout = process.stdout
        dr = threading.Thread(target=self._read_data, args=(stdout, result))
        dr.setDaemon(True)
        # log.debug('stdout reader: %r', dr)
        dr.start()

        dr.join()
        rr.join()
        if writer is not None:
            writer.join()
        process.wait()
        if stdin is not None:
            try:
                stdin.close()
            except IOError:
                pass
        stderr.close()
        stdout.close()

    def _read_response(self, stream, result):
        lines = []

        while True:
            line = stream.readline()
            if len(line) == 0:
                break
            lines.append(line)
            line = line.rstrip()

        result.stderr = ''.join(lines)
