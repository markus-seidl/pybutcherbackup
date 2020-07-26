
* More and finer log output
* Documentation
* More functions in restoring/listing/investigating
    * ex: Direct BluRay burning
    * FUSE file system
* Backup should work with storage controllers, that consider different backends
    * Directories (one simple directory is the destination, one per backup run)
    * BluRay (loads of blurays are the destination)
    * External Hard drives (loads of external hard drives are the destination)
    * Tape (LTO and Co)
* Bugfixing
    * Database is put in workdir, instead of backup dir
* 4 eye testing / peer review
* Think about multi-threading
    * Compression takes time and mostly uses 1 core
    * GnuGPG (encryption) takes time and also just uses 1 core
* Test on arm64
* Test inside docker
* Should thumbnails be generated and stored? Because 70k files already have a 20m database
* More feedback (or any at all) while restoring

* ~~Rework name resolution in XXXController (naming strategy for dirs and archives)~~
    * should be done with storage controllers 

* Bug: If a backup exactly needs 2 Discs, a third disc would be created as the backup process doesn't know that there isn't any more files to store (and possibly where to put the index.db)
* Maybe: Used libarchive?

