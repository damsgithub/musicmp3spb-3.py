# musicmp3spb-3.py
Python 3 port of https://github.com/xor512/musicmp3spb.org (http://musicmp3spb.org/ music downloader) with some differences.

Features included:
* Cover downloading
* Windows/Linux support
* Resume incomplete songs and albums downloads
* Creation of directory with "Artist - Album" name.
* Multiple simultaneous downloads to download faster
* Able to download all albums from an artist
* Socks proxy support


TODO:
* make some kind of progress bar (difficult because of the simultaneous downloads).
* streaming mode?

Install:
* install python 3 (tested with 3.6.2) if not already present on your distrib. For Windows, see here https://www.python.org/downloads/windows/
* install required modules: BeautifulSoup4 and Pysocks. Use your standard repo for linux, for Windows do 
```sh
python -m pip install BeautifulSoup4 Pysocks"
```

Usage:

```sh
------------------------------------------------------------------------------------------------------------------
################## To download an album, give it an url with '/album/' in it #####################################
------------------------------------------------------------------------------------------------------------------
user@computer:/tmp$ %s [-p /path] 'http://musicmp3spb.org/album/thunder_and_lightning.html'
** We will try to use 6 simultaneous downloads, progress will be shown **
** after each completed file but not necessarily in album's order. **

Artist: Carpe Diem
Album: Cueille Le Jour
Year: 1976
cover.jpg                                                 00.07 of 00.07 MB [100%] (file downloaded and complete)
02-naissance.mp3                                          07.83 of 07.83 MB [100%] (file downloaded and complete)
01-couleurs.mp3                                           49.59 of 49.59 MB [100%] (file downloaded and complete)
[...]

It will create an "Artist - Album" directory in the path given as argument (or else in current
 directory if not given), and download all songs and covers available on that page.


------------------------------------------------------------------------------------------------------------------
################## To download all albums from an artist, give it an url with '/artist/' in it ###################
------------------------------------------------------------------------------------------------------------------

user@computer:/tmp$ %s [-p /path] 'http://musicmp3spb.org/artist/thin_lizzy.html'
** We will try to use 3 simultaneous downloads, progress will be shown **
** after each completed file but not necessarily in album's order. **
** Warning: we are going to download all albums from this artist! **

Artist: Carpe Diem
Album: Cueille Le Jour
Year: 1976
cover.jpg                                                 00.07 of 00.07 MB [100%] (file downloaded and complete)
02-naissance.mp3                                          07.83 of 07.83 MB [100%] (file downloaded and complete)
01-couleurs.mp3                                           49.59 of 49.59 MB [100%] (file downloaded and complete)
[...]

Artist: Carpe Diem
Album: En Regardant Passer Le Temps
Year: 1975
cover.jpg                                                 00.08 of 00.08 MB [100%] (file downloaded and complete)
cover1.jpg                                                00.03 of 00.03 MB [100%] (file downloaded and complete)
01-voyage_du_non-retour.mp3                               08.92 of 08.92 MB [100%] (file downloaded and complete)
02-reincarnation.mp3                                      29.60 of 29.60 MB [100%] (file downloaded and complete)
[...]


It will iterate on all albums of this artist.

------------------------------------------------------------------------------------------------------------------
################# Command line help ##############################################################################
------------------------------------------------------------------------------------------------------------------

For more info, see https://github.com/damsgithub/musicmp3spb-3.py

positional arguments:
  url                   URL of album or artist page

optional arguments:
  -h, --help            show this help message and exit
  -d {0,1,2}, --debug {0,1,2}
                        Debug verbosity: 0, 1, 2
  -s SOCKS, --socks SOCKS
                        Sock proxy: "address:port" without "http://"
  -p PATH, --path PATH  Base directory in which album(s) will be downloaded. Defaults to current directory
  -v, --version         show program's version number and exit
```
