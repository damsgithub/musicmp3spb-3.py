# musicmp3spb-3.py
Python 3 port of https://github.com/xor512/musicmp3spb.org (http://musicmp3spb.org/ music downloader) with some differences.

Features included:
* Cover downloading
* Windows/Linux support: install python 3 (tested with 3.6.2), then do "python -m pip install BeautifulSoup4 Pysocks"
* Resume incomplete songs and albums downloads
* Creation of directory with "Artist - Album" name.
* Multiple simultaneous downloads to download faster
* Able to download all albums from an artist
* Socks proxy support


TODO:
* make some kind of progress bar (difficult because of the simultaneous downloads).
* streaming mode?
