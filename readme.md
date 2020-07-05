
# PyButcherBackup

[![Build Status](https://travis-ci.org/markus-seidl/pybutcherbackup.svg?branch=master)](https://travis-ci.org/markus-seidl/pybutcherbackup)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=markus-seidl_pybutcherbackup&metric=alert_status)](https://sonarcloud.io/dashboard?id=markus-seidl_pybutcherbackup)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=markus-seidl_pybutcherbackup&metric=reliability_rating)](https://sonarcloud.io/dashboard?id=markus-seidl_pybutcherbackup)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=markus-seidl_pybutcherbackup&metric=coverage)](https://sonarcloud.io/dashboard?id=markus-seidl_pybutcherbackup)
[![Bugs](https://sonarcloud.io/api/project_badges/measure?project=markus-seidl_pybutcherbackup&metric=bugs)](https://sonarcloud.io/dashboard?id=markus-seidl_pybutcherbackup)

Simple backup that chops up a directory (including compression and encryption) into smaller chunks. 
The main use case is backing up to a smaller medium (blu-ray) for cold storage.

Additionally the techniques used to encrypt and store the data should be "simple". Meaning that, if the 
software is lost in the future (no one knows the future), the user is able to restore the files using bash
and common apps. Currently only bash, tar, bz2 and gnupg (if encrypted) is needed. Sqlite is optional. 

# Workflow / Concept

Works in the following steps

* Ingests the whole directory and builds up a database of all files with sha256/512 hashsums
* Builds a diff against the supplied database (maybe from the last backup?)
* Creates single disc backups performing the following steps
    * Loop
        * Gather around 1G of source data
            * If source file is larger than 1G?
                * Binary split the file in 1G chunks
        * Compress this
        * Encrypt this
        * Store the information what is stored where in the database
    * Until a full blu-ray is reached
        * Burn all archives and the current state of the DB to disk
* Continue until all differences have been stored

# Installation

## From source

```bash
git clone https://github.com/markus-seidl/pybutcherbackup.git
pip install -r requirements
python main.py #see usage below#
```

## Using docker

```bash
docker run -it -v <path-to-src>:/src -v <path-to-dest>:/dest augunrik/pybutcherbackup backup /src /dest
```

# Example

## Backup

```bash
python main.py backup #src# #dest# --passphrase "password"
```

## Restore

```bash
python main.py restore #src# #dest# --passphrase "password"
```

# Restore by hand

PyButcherBackup is designed so, that you could restore every backup with a bit of bash magic and standard unix tools (tar, gpg, cat, gzip/bzip, sqlite).

