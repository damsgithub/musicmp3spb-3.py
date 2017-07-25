# musicmp3spb-3.py
Python 3 port of https://github.com/xor512/musicmp3spb.org (http://musicmp3spb.org/ music downloader) with some differences.

Features included:
* Cover downloading
* Windows support (install latest python, then "python -m pip install BeautifulSoup4")
* Automatically retry incomplete downloads
* Automatically resume if re-run on same album
* Creation of directory with "Artist - Album" name.
* Multiple simultaneous downloads
* Downloads all albums from an artist
* socks proxy


TODO:
* make some kind of progress bar (difficult because of the simultaneous downloads).
* streaming mode?
