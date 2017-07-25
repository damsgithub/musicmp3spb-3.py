#!/usr/bin/env python3
# -*- coding: utf-8 -*- 

# Copyright (C) 2017: Siergiej Riaguzow <xor256@gmx.com>, Dams
# This work is free. You can redistribute it and/or modify it under the
# terms of the Do What The Fuck You Want To Public License, Version 2,
# as published by Sam Hocevar.  See the COPYING file for more details.

# requires installation of the following modules: PySocks and Beautifulsoup4

import re
import sys
import os
import signal
import time
import random
import socks
import socket
import urllib.request
import html
import argparse
from multiprocessing import Pool
from bs4 import BeautifulSoup


version = 4.4
debug = 0 # 3 levels of verbosity: 0 (none), 1 or 2
net_timeout = 10 # timeout in seconds for network requests
nb_conn = 3 # nb of simultaneous download threads, tempfile.ru doesn't like more than 3 or 4!
socks_proxy = ""
socks_port = ""
script_name = os.path.basename(sys.argv[0])

description = "Python script to download albums from http://musicmp3spb.org, version %s." % version
help_string = description + """

------------------------------------------------------------------------------------------------------------------
################## To download an album, give it an url with '/album/' in it #####################################
------------------------------------------------------------------------------------------------------------------
user@computer:/tmp$ %s [-p /path] 'http://musicmp3spb.org/album/thunder_and_lightning.html'
** We will try to use 6 simultaneous downloads, progress will be shown **
** after each completed file but not necessarily in album's order. **

Artist: Art Zoyd
Album: Phase IV
Year: 1982
cover.jpg                                                 00.03 of 00.03 MB [100%%] (file downloaded and complete)
cover1.jpg                                                00.03 of 00.03 MB [100%%] (file downloaded and complete)
06-deux_preludes.mp3                                      05.19 of 05.19 MB [100%%] (file downloaded and complete)
05-ballade.mp3                                            09.41 of 09.41 MB [100%%] (file downloaded and complete)
03-derniere_danse.mp3                                     10.54 of 10.54 MB [100%%] (file downloaded and complete)
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


Artist: Thin Lizzy
Album: Live At O2 Shepherds Bush Empire, London (17.12.2012) CD1
Year: 2013
cover.jpg                                                 00.05 of 00.05 MB [100%%] (file downloaded and complete)
03-dont_believe_a_word.mp3                                05.33 of 05.33 MB [100%%] (file downloaded and complete)
01-are_you_ready.mp3                                      07.53 of 07.53 MB [100%%] (file downloaded and complete)
02-jailbreak.mp3                                          09.49 of 09.49 MB [100%%] (file downloaded and complete)


It will iterate on all albums of this artist.


------------------------------------------------------------------------------------------------------------------
################# Command line help ##############################################################################
------------------------------------------------------------------------------------------------------------------

For more info, see https://github.com/damsgithub/musicmp3spb-3.py


""" % (script_name, script_name)


def to_MB(a_bytes):
    return a_bytes / 1024. / 1024.


def spinning_wheel():
    while True:
        for cursor in '|/-\\':
            yield cursor


def dl_status(file_name, dlded_size, real_size):
    status = r'%-50s        %05.2f of %05.2f MB [%3d%%]' % \
        (file_name, to_MB(dlded_size), to_MB(real_size), dlded_size * 100. / real_size)
    return status


def dl_cover(page_soup, url):
    # download albums' cover(s)
    image_tags = page_soup.find_all('img')
    image_num = 0
    for image in image_tags:
        if not re.match('/images/.+jpg', image['src']):
            continue

        # to get the cover in full size, we have to prepend an "f" to the file name
        entries = re.split("/", image['src'])
        entries[-1] = "f" + entries[-1]
        image['src'] = "/".join(entries)

        # prepend base url if necessary
        if not re.match(r'^http:', image['src']):
            image['src'] = get_base_url(url) + image['src']
        if debug: print("image: %s" % image['src'])

        image_name = "cover"
        if image_num > 0 :
            image_name = image_name + str(image_num)

        download_file(image['src'], image_name + ".jpg")

        image_num += 1

    if (image_num == 0):
        print("** No cover found for this album **", file=sys.stderr)


def get_base_url(url):
    # get website base address to preprend it to images, songs and albums relative urls'
    base_url = url.split('//', 1)
    base_url = base_url[0] + '//' + base_url[1].split('/', 1)[0]
    if debug > 1: print("base_url: %s" % base_url)
    return base_url


def open_url(url, data):
    if socks_proxy and socks_port:
        socks.set_default_proxy(socks.SOCKS5, socks_proxy, socks_port)
        socket.socket = socks.socksocket

    while True:
        try:
            u = urllib.request.urlopen(url, data, timeout=net_timeout)
            redirect = u.geturl()
            if re.search(r'/404.*', redirect):
                print("** Page not found (404), aborting on url: %s **" % url, file=sys.stderr)
                u = None
        except (urllib.error.HTTPError, socket.timeout, ConnectionError) as e:
            time.sleep(random.randint(2,5))
            print("** Connection problem (%s), reconnecting **" % e.reason, file=sys.stderr)
            continue
        except (urllib.error.URLError, Exception) as e:
            print("** Url seems invalid, aborting (%s) **" % url, file=sys.stderr)
            if (e.reason):
                print("** reason : %s **" % e.reason)
            u = None
        return u


def get_page_soup(url, data):
    page = open_url(url, data=data)
    if not page:
        return None
    page_soup = BeautifulSoup(page, "html.parser", from_encoding=page.info().get_param('charset'))
    if debug > 1: print("page_soup: %s" % page_soup)
    page.close()
    return page_soup


def prepare_album_dir(page_content, base_path):
    # get album infos from html page content
    artist = ""
    title = ""
    year = ""

    album_infos_re = re.compile('<h1><a href="/artist/.+?.html" title="(.+?) mp3">'
                                '.+?<div class="Name">\n(.+?)<br\s?/>', re.S)
    # Beautifulsoup converts "&" to "&amp;" so that it be valid html.
    # We need to convert them back with html.unescape
    album_infos = album_infos_re.search(html.unescape(page_content))

    print("")
    if not album_infos:
        artist = input("Unable to get ARTIST NAME. Please enter here: ")
        title = input("Unable to get ALBUM NAME. Please enter here: ")
    else:
        artist = album_infos.group(1)
        title = album_infos.group(2)
   
    print("Artist: %s" % artist)
    print("Album: %s" % title)

    # Get the year if it is available
    album_infos_re = re.compile('<h1><a href="/artist/.+?.html" title=".+? mp3">'
                                '.+?<div class="Name">\n.+?<br\s?/>\n<i>(\d+)</i>', re.S)
    album_infos = album_infos_re.search(page_content)

    if album_infos and album_infos.group(1):
        year = album_infos.group(1)
        print("Year: %s" % year)
    else:
        year = input("Unable to get ALBUM YEAR. Please enter here (may leave blank): ")

    album_dir = os.path.normpath(base_path + os.sep + sanitize_path(artist + " - " + title))
    if debug: print("Album's dir: %s" % (album_dir))

    if not os.path.exists(album_dir):
        os.mkdir(album_dir)

    return album_dir


def sanitize_path(path):
    chars_to_remove = str.maketrans('/\\?*|":><', '         ')
    return path.translate(chars_to_remove)


def download_file(url, file_name):
    try:
        partial_dl = 0
        dlded_size = 0
    
        if os.path.exists(file_name):
            dlded_size = os.path.getsize(file_name)
    
        req = urllib.request.Request(url)
        u = open_url(req, data=None)
        if not u: return

        i = 0
        while (i < 5):
            try:
                real_size = int(u.info()['content-length'])
            except Exception as e:
                if (i == 4):
                    print("** Unable to get the real size of %s from the server. **" % file_name, file=sys.stderr)
                    real_size = -1
                else:
                    i = +1
                continue
            break
    
        # find where to start the file download (continue or start at beginning)
        if (0 < dlded_size < real_size):
            u.close()
            req = urllib.request.Request(url, headers={'Range': 'bytes=%s-%s' % (dlded_size, real_size)})
            u = open_url(req, data=None)
            if not u: return
    
            # test if the server supports the Range header
            if (u.getcode() == 206):
                partial_dl = 1
            else:
                dlded_size = 0
                nb_conn = 0
                if debug: print("** Range/partial download is not supported by server **", file=sys.stderr)
    
        elif (dlded_size == real_size):
            print("%s (file already complete, skipped)" % dl_status(file_name, dlded_size, real_size))
            return
        elif (dlded_size > real_size):
            print("** Error: %s is bigger than original file or the real size could "
                  "not be determined, we will (re)download it! **" % file_name, file=sys.stderr)
            dlded_size = 0
    
        # append or truncate
        if partial_dl:
            f = open(file_name, 'ab+')
        else:
            f = open(file_name, 'wb+')
    
        # get the file
        block_sz = 8192
        spin = spinning_wheel()
        while True:
            buffer = u.read(block_sz)
            if not buffer:
                break
    
            dlded_size += len(buffer)
            f.write(buffer)
    
            # show progress
            #sys.stdout.write(next(spin))
            #sys.stdout.flush()
            #time.sleep(0.1)
            #sys.stdout.write('\b')
    
        if (real_size == -1): 
            real_size = dlded_size
            print("%s (file downloaded, but could not verify if it is complete)" 
                   % dl_status(file_name, dlded_size, real_size))
        elif (real_size == dlded_size):
            print("%s (file downloaded and complete)" 
                   % dl_status(file_name, dlded_size, real_size))
        elif (dlded_size < real_size):
            print("%s (file download incomplete!)" 
                   % dl_status(file_name, dlded_size, real_size))
    
        #sys.stdout.write('\n')
        u.close()
        f.close()
    except KeyboardInterrupt as e:
        if debug: print("** download_file: keyboard interrupt detected **", file=sys.stderr)
        raise e


def download_song(url):
    try:
        if debug: print("Downloading song from %s" % url)
        file_name = ""
    
        page_soup = get_page_soup(url, str.encode(''))
        if not page_soup: 
            if debug: print("** Unable to get song's page soup **", file=sys.stderr)
            return
    
        # get the filename
        for form in page_soup.find_all('form'):
            if re.match(r'/file/.*', form.attrs['action']):
                break
        if debug: print("form_attr: " + form.attrs['action'])
    
        for link in page_soup.find_all('a', href=True):
            if re.match(form.attrs['action'], link['href']):
                file_name = link.contents[0]
                break
        if file_name != "":
            if debug: print("got_filename: " + file_name)
        else:
            print("** Error: Cannot find filename for: %s **" % link['href'], file=sys.stderr)
            return
    
        # we need to re-submit the same page with an hidden input value to get the real link
        submit_value = page_soup.find('input', {'name': 'robot_code'}).get('value')
        if debug: print("submit_value: %s" % submit_value)
    
        data = urllib.parse.urlencode([('robot_code', submit_value)])
    
        response = open_url(url, data=None)
        if not response: return
        real_link = response.geturl()
        response.close()
        response_soup = get_page_soup(real_link, str.encode(data))
        if not response_soup:
            if debug: print("** Unable to get song's page soup (2) **", file=sys.stderr)
            return
    
        for song_link in response_soup.find_all('a', href=True):
            if re.match('http://tempfile.ru/download/.*', song_link['href']):
                break
        if song_link['href'] != "":
            if debug: print("song_link: " + song_link['href'])
        else:
            print("** Error: Cannot find song's real link for: %s **" % file_name, file=sys.stderr)
            return
    
        download_file(song_link['href'], file_name)
    except KeyboardInterrupt:
        print("** keyboard interrupt detected, finishing processes! **", file=sys.stderr)
        # just return, see: 
        # http://jessenoller.com/2009/01/08/multiprocessingpool-and-keyboardinterrupt/
        return


def download_album(url, base_path):
    page_soup = get_page_soup(url, str.encode(''))
    if not page_soup:
        if debug: print("** Unable to get album's page soup **", file=sys.stderr)
        return
    page_content = str(page_soup)
    if debug > 1: print(page_content)

    album_dir = prepare_album_dir(page_content, base_path)

    os.chdir(album_dir)
 
    dl_cover(page_soup, url)

    # create list of album's songs
    songs_links = []
    title_regexp = re.compile('.*Скачать mp3.*', re.IGNORECASE)
    for link in page_soup.find_all('a', href=True, title=True):
        if not re.match('/download/.*', link['href']):
            continue

        if title_regexp.match(link['title']):
            # prepend base url if necessary
            if re.match(r'^/', link['href']):
                link['href'] = get_base_url(url) + link['href']
            songs_links.append(link['href'])

    if not songs_links:
        print("** Unable to detect any song links, skipping this album/url **")
    else:
        # we launch the threads to do the downloads
        pool = Pool(processes=nb_conn)
        try:
            pool.map(download_song, songs_links)
            pool.close()
            pool.join()
        except KeyboardInterrupt as e:
            print("** Program interrupted by user, exiting! **", file=sys.stderr)
            pool.terminate()
            pool.join()
            sys.exit(1)

    os.chdir('..')


def download_artist(url, base_path):
    page_soup = get_page_soup(url, str.encode(''))
    if not page_soup:
        if debug: print("** Unable to get artist's page soup **", file=sys.stderr)
        return 

    print("** Warning: we are going to download all albums from this artist! **")

    for link in page_soup.find_all('a', href=True):
        if re.match(r'/album/.*', link['href']):
            download_album(get_base_url(url) + link['href'], base_path)
 

def main():
    parser = argparse.ArgumentParser(description=help_string, add_help=True, 
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument(
        "-d", "--debug", type=int, choices=range(0,3), default=1, help="Debug verbosity: 0, 1, 2" )
    parser.add_argument(
        "-s", "--socks", type=str, default=None, help='Sock proxy: "address:port" without "http://"')
    parser.add_argument(
        "-p", "--path", type=str, default=".", help="Base directory in which album(s) will be"
                                                    " downloaded. Defaults to current directory")
    parser.add_argument(
        "-v", "--version", action='version', version='%(prog)s, version: '+str(version))

    parser.add_argument("url", action='store', help="URL of album or artist page")
    args = parser.parse_args()

    if (args.debug):
        debug = args.debug

    if (args.socks):
        (socks_proxy, socks_port) = args.socks.split(':')
        if debug: print("proxy socks: %s %s" % (socks_proxy, socks_port))
        if not socks_port.isdigit():
            print ("** Error in your socks proxy definition, exiting. **")
            sys.exit(1)

    try:
        print("** We will try to use %s simultaneous downloads, progress will be shown **" % nb_conn)
        print("** after each completed file but not necessarily in album's order. **")

        if re.search(r'/artist/.*', args.url):
            download_artist(args.url, args.path)
        elif re.search(r'/album/.*', args.url):
            download_album(args.url, args.path)
        else:
            print("** Error: unable to recognize url, it should contain '/artist/' or '/album/'! **", 
                  file=sys.stderr)

    except Exception as e:
        print("** Error: Cannot download URL: %s\n\t%s **" % (args.url, e), file=sys.stderr)

if __name__ == "__main__":
    main()

