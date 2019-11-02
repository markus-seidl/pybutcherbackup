
* Rework name resolution in XXXController (-> naming strategy for dirs and archives)
* More and finer log output
* Documentation
* More functions in restoring/listing/investigating
    * ex: Direct BluRay burning
* Bugfixing
    * Database is put in workdir, instead of backup dir
    * "Bug" with PyCharm: Don't use tqdm when running unit tests (or make it disableable)
* 4 eye testing / peer review
* Think about multi-threading
    * Compression takes time and mostly uses 1 core
    * GnuGPG (encryption) takes time and also just uses 1 core
* Test on arm64
* Test inside docker
* Should thumbnails be generated and stored? Because 70k files already have a 20m database
* More feedback (or any at all) while restoring
