import gzip
import logging
import os
import pickle
import struct
import time
import _lzma
import zstandard as zstd
from tkinter import messagebox


import argoncrypto as ac
from utils import get_file_data
from compressor import Compressor

HEADER_FORMAT = '16s22sI16s17sI7sII5s'  # Example format: 16 bytes for name, 32 bytes for description, 4 bytes for size


def get_vpk_info(data, bin=False):
    if not bin:
        # read the header from a file in binary mode
        with open(data, 'rb') as file:
            header_data = file.read(struct.calcsize(HEADER_FORMAT))
            filename, fileinfo, filesize, author, copyright, timestamp, encryption, key_length, version, compression = struct.unpack(HEADER_FORMAT, header_data)
    
    else:
        # read the header from binary data
        header_data = data[:struct.calcsize(HEADER_FORMAT)]
        filename, fileinfo, filesize, author, copyright, timestamp, encryption, key_length, version, compression = struct.unpack(HEADER_FORMAT, header_data)
    
    return filename.decode(), fileinfo.decode(), filesize, author.decode(), copyright.decode(), timestamp, encryption.decode(), key_length, version, compression.decode()

class Packager:
    def __init__(self, argonize: tuple, config: dict):
        self.timestamp = None
        self.byte_dict: dict = None
        self.directory: str = None
        self.package: str = None
        self.config: dict = config
        self.argonize = ac.generate_argon_key(argonize[0], argonize[1])
        
    def read_files(self) -> int:
        # Iterate through each file and sub-folder in the directory
        found_files = 0
        for root, _, files in os.walk(self.directory):
            for filename in files:
                # file_extension = os.path.splitext(filename)[1].lower()
                file_path = os.path.join(root, filename)
                
                folder_name = os.path.basename(root)
                file_dict = self.byte_dict.setdefault(folder_name, {})
                
                file_dict[filename] = get_file_data(file_path)
                found_files += 1
                
        return found_files
    
    def save(self):
        pickled_data = pickle.dumps(self.byte_dict)
        encrypted_data = ac.encrypt_data(self.argonize, pickled_data, mode = ac.MODES[self.config['ArgonCrypto']['mode'].upper()])
        encrypted_data_bytes = pickle.dumps(encrypted_data)
        
        if "/" in self.package:
            filename = self.package.split("/")[-1].replace(".vpk", "").encode('utf-8')
        elif "\\" in self.package:
            filename = self.package.split("\\")[-1].replace(".vpk", "").encode('utf-8')
        else:
            filename = self.package.replace(".vpk", "").encode('utf-8')
        fileinfo = "Encrypted data package".encode('utf-8')
        filesize = len(encrypted_data_bytes)
        author    = self.config['Settings']['author'].encode('utf-8')
        copyright = "VALKYTEQ ⓒ 2023".encode('utf-8')
        timestamp = int(time.time())
        encryption = self.config['ArgonCrypto']['mode'].upper().encode('utf-8')
        key_length = len(self.argonize)
        version = 1
        compression = self.config['Compressor']['mode'].encode('utf-8')
        
        header_data = struct.pack(HEADER_FORMAT, filename, fileinfo, filesize, author, copyright, timestamp, encryption, key_length, version, compression)
        v_package_c = header_data + Compressor.deflate(encrypted_data_bytes, compression.decode())
        
        with open(self.package, 'wb') as file:
            file.write(v_package_c)
    
    def load(self):
        error = False
        with open(self.package, 'rb') as file:
            header_data = file.read(struct.calcsize(HEADER_FORMAT))
            info = struct.unpack(HEADER_FORMAT, header_data)
            try:
                encrypted_data = Compressor.inflate(file.read(info[2]), self.config['Compressor']['mode'])
            except ValueError:
                error = True
            except gzip.BadGzipFile:
                error = True
            except OSError:
                error = True
            except _lzma.LZMAError:
                error = True
            except RuntimeError:
                error = True
            except zstd.ZstdError:
                error = True
        
        if not error:
            try:
                decrypted_data_bytes = pickle.loads(encrypted_data)
                decrypted_data = ac.decrypt_data(self.argonize, decrypted_data_bytes, mode = ac.MODES[self.config['ArgonCrypto']['mode'].upper()])
                self.byte_dict = pickle.loads(decrypted_data)
                
            except ValueError:
                messagebox.showerror("Argon Crypto | Error", "The crypto Key and IV do not match for this package!")
        else:
            messagebox.showerror("Compressor | Error", "The compression method does not match for this package!")
    
    def create_vpk(self):
        if self.directory != str and self.directory != '' and self.directory is not None:
            self.timestamp = time.time()
            
            self.byte_dict: dict = {}
            self.package = f"{self.directory}.vpk"
            
            i = self.read_files()
            file_amount = ('{: >8}'.format(str(i)))
            
            package = self.directory.split('\\')[-1]
            package_name = ('{: >20}'.format(str(package)))

            self.save()
            
            elapsed = round(time.time()-self.timestamp, 2)
            elapsed_time = ('{: >10}'.format(str(elapsed)))
            logging.info(f"Finished | {package_name}.vpk | {file_amount} Files | {elapsed_time} sec")
        else:
            raise Exception("Error in directory path!")
