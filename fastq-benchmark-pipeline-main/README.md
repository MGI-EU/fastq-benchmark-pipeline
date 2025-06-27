# Benchmarking FASTQ Compressors

This repository provides a benchmark comparison of various FASTQ compression tools, evaluating their performance in terms of compression ratio and compression/decompression speed. FASTQ files are widely used in genomic sequencing, and efficient compression is crucial for storage and data transfer.

## Features

* comparison of multiple FASTQ compressors;
* metrics: compression ratio, and compression/decompression time;
* simple reproducible benchmarking setup:
    - script manages containers with supported tools using Docker or Podman; 
    - execution on the host is also supported (though tools will need to be installed manually in this case);
* helper scripts for filtering and downloading data from SRA;
* requires only Python 3.9+ and Docker/Podman.

## Supported compressors
* gzip/pigz 
* fqzcomp4 & fqzcomp5
* DSRC
* Leon
* FaStore
* repaq
* Spring

## Usage

```bash
# Download dataset
python scripts/download.py SRR11200796 

# Run benchmarks in docker, using 4 compression/decompression threads
# (the first run will take additional time to build images) 
python run_benchmark.py -i1 SRR11200796 --threads 4 --container-runtime docker
```

A folder named `Results-{date}_{time}` will be created; it contains logs from each compressor invocation, and a .csv file which should look like:

|tool    |dataset|threads|original_size|compressed_size|total_cr|compression_time|decompression_time|decompressed_same_size|
|--------|-------|-------|-------------|---------------|--------|----------------|------------------|----------------------|
|pigz    |SRR11200796|4      |44006940     |9430121        |4.667   |0.36            |0.1               |1                     |
|DSRC    |SRR11200796|4      |44006940     |8056290        |5.462   |0.1             |0.08              |1                     |
|fqzcomp5|SRR11200796|4      |44006940     |4252131        |10.349  |1.83            |0.95              |1                     |
|repaq   |SRR11200796|4      |44006940     |5693716        |7.729   |5.97            |0.5               |1                     |
|Spring  |SRR11200796|4      |44006940     |4730880        |9.302   |3.0             |1.71              |1                     |
|FaStore |SRR11200796|4      |44006940     |5863904        |7.505   |3.67            |1.38              |1                     |
|Leon    |SRR11200796|4      |44006940     |6125292        |7.184   |3.69            |0.79              |1                     |

The last column is 0 if size of decompressed files did not match with the originals (we do not perform a thorough validation, as it would slow things quite a bit, especially for reordering compressors). 
Other columns are self-explanatory. 
File sizes are in bytes, and time is in seconds.
