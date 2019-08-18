import os
import platform
import re
import shlex
import subprocess

import codecs
import threading
import sys
import locale

import struct
from Crypto.Cipher import AES


class GpgEncryptor:
    """
    From: https://github.com/isislovecruft/python-gnupg/blob/master/pretty_bad_protocol/_*.py
    """

    class ResultDTO:
        def __init__(self):
            self.stderr = None
            self.data = None
            self.retval = None

    def __init__(self, gpg_location="/usr/local/bin/gpg"):  # TODO automagically find GPG
        self.gpg_location = gpg_location

        encoding = locale.getpreferredencoding()
        if encoding is None:  # This happens on Jython!
            encoding = sys.stdin.encoding
        self._encoding = encoding.lower().replace('-', '_')

    def encrypt_file(self, key, in_filename, out_filename):
        #  gpg --passphrase 1234 --batch --symmetric --cipher-algo AES256 XXX

        cmd = list()
        cmd.append(self.gpg_location)
        cmd.append("--batch")
        cmd.append("--yes")  # needed for unit tests, as the file already exists
        cmd.append("--symmetric")
        cmd.append("--output %s" % out_filename)
        cmd.append("-c")
        cmd.append("--cipher-algo AES256")
        cmd.append("--passphrase %s" % key)
        cmd.append(in_filename)

        process = self._open_subprocess(cmd)

        result = GpgEncryptor.ResultDTO()

        self._collect_output(process, result)
        result.retval = process.wait()

        return result

    def decrypt_file(self, key, in_filename, out_filename):
        #  gpg --passphrase 1234 --batch --symmetric --cipher-algo AES256 XXX

        cmd = list()
        cmd.append(self.gpg_location)
        cmd.append("--batch")
        cmd.append("--yes")  # needed because in tests the output file already exists
        cmd.append("--output %s" % out_filename)
        cmd.append("-d")
        cmd.append("--passphrase %s" % key)
        cmd.append(in_filename)

        process = self._open_subprocess(cmd)

        result = GpgEncryptor.ResultDTO()

        self._collect_output(process, result)
        result.retval = process.wait()

        return result

    def _open_subprocess(self, args=None):
        """Open a pipe to a GPG subprocess and return the file objects for
        communicating with it.
        :param list args: A list of strings of options and flags to pass to
                          ``GPG.binary``. This is input safe, meaning that
                          these values go through strict checks (see
                          ``parsers._sanitise_list``) before being passed to to
                          the input file descriptor for the GnuPG process.
                          Each string should be given exactly as it would be on
                          the commandline interface to GnuPG,
                          e.g. ["--cipher-algo AES256", "--default-key
                          A3ADB67A2CDB8B35"].
        :param bool passphrase: If True, the passphrase will be sent to the
                                stdin file descriptor for the attached GnuPG
                                process.
        """
        # see http://docs.python.org/2/library/subprocess.html#converting-an-argument-sequence-to-a-string-on-windows
        cmd = shlex.split(' '.join(args))
        # log.debug("Sending command to GnuPG process:%s%s" % (os.linesep, cmd))

        if platform.system() == "Windows":
            # TODO figure out what the hell is going on there.
            expand_shell = True
        else:
            expand_shell = False

        environment = {
            'LANGUAGE': os.environ.get('LANGUAGE') or 'en',
            'GPG_TTY': os.environ.get('GPG_TTY') or '',
            'DISPLAY': os.environ.get('DISPLAY') or '',
            'GPG_AGENT_INFO': os.environ.get('GPG_AGENT_INFO') or '',
            'GPG_TTY': os.environ.get('GPG_TTY') or '',
            'GPG_PINENTRY_PATH': os.environ.get('GPG_PINENTRY_PATH') or '',
        }

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
        """Reads all the stderr output from GPG, taking notice only of lines
        that begin with the magic [GNUPG:] prefix.
        Calls methods on the response object for each valid token found, with
        the arg being the remainder of the status line.
        :param stream: A byte-stream, file handle, or a
                       :data:`subprocess.PIPE` for parsing the status codes
                       from the GnuPG process.
        :param result: The result parser class from :mod:`~gnupg._parsers` ―
                       the ``handle_status()`` method of that class will be
                       called in order to parse the output of ``stream``.
        """
        # All of the userland messages (i.e. not status-fd lines) we're not
        # interested in passing to our logger
        # userland_messages_to_ignore = []

        # if self.ignore_homedir_permissions:
        #    userland_messages_to_ignore.append('unsafe ownership on homedir')

        lines = []

        while True:
            line = stream.readline()
            if len(line) == 0:
                break
            lines.append(line)
            line = line.rstrip()

            # if line.startswith('[GNUPG:]'):
            #     line = _util._deprefix(line, '[GNUPG:] ', log.status)
            #     keyword, value = _util._separate_keyword(line)
            #     result._handle_status(keyword, value)
            # elif line.startswith('gpg:'):
            #     line = _util._deprefix(line, 'gpg: ')
            #     keyword, value = _util._separate_keyword(line)
            #
            #     # Silence warnings from gpg we're supposed to ignore
            #     ignore = any(msg in value for msg in userland_messages_to_ignore)
            #
            #     if not ignore:
            #         # Log gpg's userland messages at our own levels:
            #         if keyword.upper().startswith("WARNING"):
            #             log.warn("%s" % value)
            #         elif keyword.upper().startswith("FATAL"):
            #             log.critical("%s" % value)
            #             # Handle the gpg2 error where a missing trustdb.gpg is,
            #             # for some stupid reason, considered fatal:
            #             if value.find("trustdb.gpg") and value.find("No such file"):
            #                 result._handle_status('NEED_TRUSTDB', '')
            # else:
            #     if self.verbose:
            #         log.info("%s" % line)
            #     else:
            #         log.debug("%s" % line)
        result.stderr = ''.join(lines)


class PyCryptoEncryptor:
    def encrypt_file(self, key, in_filename, out_filename, chunksize=64 * 1024):  # cython could improve performance?
        """ Encrypts a file using AES (CBC mode) with the
            given key.
            From: https://github.com/eliben/code-for-blog/blob/master/2010/aes-encrypt-pycrypto/pycrypto_file.py
            key:
                The encryption key - a bytes object that must be
                either 16, 24 or 32 bytes long. Longer keys
                are more secure.
            chunksize:
                chunksize must be divisible by 16.
        """
        iv = os.urandom(16)
        encryptor = AES.new(key, AES.MODE_CBC, iv)
        filesize = os.path.getsize(in_filename)

        with open(in_filename, 'rb') as infile:
            with open(out_filename, 'wb') as outfile:
                outfile.write(struct.pack('<Q', filesize))
                outfile.write(iv)

                while True:
                    chunk = infile.read(chunksize)
                    if len(chunk) == 0:
                        break
                    elif len(chunk) % 16 != 0:
                        chunk += b' ' * (16 - len(chunk) % 16)

                    outfile.write(encryptor.encrypt(chunk))

    def decrypt_file(self, key, in_filename, out_filename, chunksize=64 * 1024):  # cython could improve performance?
        """ Decrypts a file using AES (CBC mode) with the
            given key. Parameters are similar to encrypt_file.
            From: https://github.com/eliben/code-for-blog/blob/master/2010/aes-encrypt-pycrypto/pycrypto_file.py
        """
        with open(in_filename, 'rb') as infile:
            origsize = struct.unpack('<Q', infile.read(struct.calcsize('Q')))[0]
            iv = infile.read(16)
            decryptor = AES.new(key, AES.MODE_CBC, iv)

            with open(out_filename, 'wb') as outfile:
                while True:
                    chunk = infile.read(chunksize)
                    if len(chunk) == 0:
                        break
                    outfile.write(decryptor.decrypt(chunk))

                outfile.truncate(origsize)
