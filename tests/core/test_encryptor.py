import os
import tempfile
from unittest import TestCase
from backup.core.encryptor import PyCryptoEncryptor, GpgEncryptor


class TestPyCryptoEncryptor(TestCase):
    def create_test_file(self, name, size=14):
        with open(name, 'w') as temp:
            for i in range(size):
                temp.write("a")

    def test_encrypt_decrypt(self):
        with tempfile.NamedTemporaryFile() as source_file:
            with tempfile.NamedTemporaryFile() as encrypt_file:
                with tempfile.NamedTemporaryFile() as decrypt_file:
                    tar = PyCryptoEncryptor()

                    self.create_test_file(source_file.name, 20)
                    key = "0123456789123456"

                    tar.encrypt_file(key, source_file.name, encrypt_file.name)
                    tar.decrypt_file(key, encrypt_file.name, decrypt_file.name)

                    assert os.path.getsize(decrypt_file.name) == os.path.getsize(source_file.name)

                    with open(source_file.name, 'r') as f:
                        assert 'aaaaaaaaaaaaaaaaaaaa' == f.readline()


class TestGpgEncryptor(TestCase):
    def create_test_file(self, name, size=14):
        with open(name, 'w') as temp:
            for i in range(size):
                temp.write("a")

    def test_encrypt_decrypt(self):
        with tempfile.NamedTemporaryFile() as source_file:
            with tempfile.NamedTemporaryFile() as encrypt_file:
                with tempfile.NamedTemporaryFile() as decrypt_file:
                    tar = GpgEncryptor()

                    self.create_test_file(source_file.name, 20)
                    key = "0123456789123456"

                    tar.encrypt_file(key, source_file.name, encrypt_file.name)
                    tar.decrypt_file(key, encrypt_file.name, decrypt_file.name)

                    assert os.path.getsize(decrypt_file.name) == os.path.getsize(source_file.name)

                    with open(source_file.name, 'r') as f:
                        assert 'aaaaaaaaaaaaaaaaaaaa' == f.readline()
