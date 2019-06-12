
# PyButcherBackup

Simple backup that chops up a directory (including compression and encryption) into smaller chunks. 
The main use case is backing up to a smaller medium (blu-ray). 


# Workflow

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
