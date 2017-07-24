#!/usr/bin/env python3
# -*- coding: utf-8 -*- 

# Copyright (C) 2017: Siergiej Riaguzow <xor256@gmx.com>, Dams
# This work is free. You can redistribute it and/or modify it under the
# terms of the Do What The Fuck You Want To Public License, Version 2,
# as published by Sam Hocevar.  See the COPYING file for more details.

import re
import sys
import os
import html
import time
import random
import urllib.request
from multiprocessing import Pool
from bs4 import BeautifulSoup


version = 4.0
debug = 0 # 3 levels of verbosity: 0 (none), 1 or 2
net_timeout = 10 # timeout in s for network requests
nb_conn = 3 # nb of simultaneous download threads, tempfile.ru doesn't like more than 3 or 4!


def help():
    script_name = os.path.basename(sys.argv[0])
    print(
"""Python script to automatically download albums from http://musicmp3spb.org site, version %s.

### To download an album, give it an url with '/album/' in it :

user@computer:/tmp$ %s 'http://musicmp3spb.org/album/thunder_and_lightning.html' [/local/path]
Artist: Thin Lizzy
Album: Thunder And Lightning
Year: 1983
Downloading: cover.jpg, Total Bytes: 48619
Downloading: 01-thunder_and_lightning.mp3, Total Bytes: 12208063
    606208  [4.97%%]

It will create an "Artist - Album" directory in the path given as argument (or else in current directory if not given),
and download all songs and covers available on that page.


### To download all albums from an artist, give it an url with '/artist/' in it:

user@computer:/tmp$ %s 'http://musicmp3spb.org/artist/thin_lizzy.html' [/local/path]
Info: we are going to download all albums from this artist!

Artist: Thin Lizzy
Album: Live At O2 Shepherds Bush Empire, London (17.12.2012) CD1
Year: 2013
Downloading: cover.jpg, Total Bytes: 54860
Downloading: 01-are_you_ready.mp3, Total Bytes: 7893202
    966656 [12.25%%]

It will iterate on all albums of this artist.


### For more info, see https://github.com/damsgithub/musicmp3spb-3.py
""" % (version, script_name, script_name))


def to_MB(a_bytes):
    return a_bytes / 1024. / 1024.


def spinning_wheel():
    while True:
        for cursor in '|/-\\':
            yield cursor


def dl_status(file_name, dlded_size, real_size):
    status = r'%-40s        %05.2f of %05.2f MB [%3d%%]' % \
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


def get_base_url(url):
    # get website base address to preprend it to images, songs and albums relative urls'
    base_url = url.split('//', 1)
    base_url = base_url[0] + '//' + base_url[1].split('/', 1)[0]
    if debug > 1: print("base_url: %s" % base_url)
    return base_url


def open_url(url, data):
    while True:
        try:
            u = urllib.request.urlopen(url, data, timeout=net_timeout)
        except Exception as e:
            #msg = "Trying to (re)connect"
            #sys.stdout.write(msg)
            #sys.stdout.flush()
            # we dont want all threads to try again at the same time:
            time.sleep(random.randint(2,5)) 
            #backspaces = chr(8)*(len(msg))
            #sys.stdout.write(backspaces)
            print("** Connection failed, trying to (re)connect **")
            continue
        return u


def get_page_soup(url, data):
    page = open_url(url, data=data)
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
    # Beautifulsoup converts "&" to "&amp;" so that it be valid html, 
    # we need to convert them back with html.unescape
    album_infos = album_infos_re.search(html.unescape(page_content))

    print("\n")
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
    partial_dl = 0
    dlded_size = 0

    if os.path.exists(file_name):
        dlded_size = os.path.getsize(file_name)

    req = urllib.request.Request(url)
    u = open_url(req, data=None)

    i = 0
    while (i < 5):
        try:
            real_size = int(u.info()['content-length'])
        except Exception as e:
            if (i == 4):
                print("** Unable to get the real size of %s from the server. **" % file_name)
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

        # test if the server supports the Range header
        if (u.getcode() == 206):
            partial_dl = 1
        else:
            dlded_size = 0
            nb_conn = 0
            if debug: print("** Range/partial download is not supported **")

    elif (dlded_size == real_size):
        print("%s (file already complete, skipped)" % dl_status(file_name, dlded_size, real_size))
        return
    elif (dlded_size > real_size):
        print("** Error: %s is bigger than original file or the real size could "
              "not be determined, we will (re)download it! **" % file_name)
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


def download_song(url):
    if debug: print("Downloading song from %s" % url)
    file_name = ""

    page_soup = get_page_soup(url, str.encode(''))

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
    real_link = response.geturl()
    response.close()
    response_soup = get_page_soup(real_link, str.encode(data))

    for song_link in response_soup.find_all('a', href=True):
        if re.match('http://tempfile.ru/download/.*', song_link['href']):
            break
    if song_link['href'] != "":
        if debug: print("song_link: " + song_link['href'])
    else:
        print("** Error: Cannot find song's real link for: %s **" % file_name, file=sys.stderr)
        return

    download_file(song_link['href'], file_name)


def download_album(url, base_path):
    page_soup = get_page_soup(url, str.encode(''))
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
            #url_arr = link['href'].split('/')

            # prepend base url if necessary
            if re.match(r'^/', link['href']):
                link['href'] = get_base_url(url) + link['href']

    #       download_song(link['href'])
            songs_links.append(link['href'])

    pool = Pool(processes=nb_conn)
    pool.map(download_song, songs_links)
    pool.close()
    pool.join()

    os.chdir('..')


def download_artist(url, base_path):
    page_soup = get_page_soup(url, str.encode(''))
    print("** Info: we are going to download all albums from this artist! **")

    for link in page_soup.find_all('a', href=True):
        if re.match(r'/album/.*', link['href']):
            download_album(get_base_url(url) + link['href'], base_path)
 

def main():
    base_path = "."

    if len(sys.argv) < 2:
        help()
        sys.exit(1)
    elif len(sys.argv) > 2:
        base_path = sys.argv[2]

    arg = sys.argv[1]

    if (arg == '-h') or (arg == '--help'):
        help()
    else:
        try:
            if debug > 1: print("arg: %s, base_path: %s" % (arg, base_path))
            print("** We will try to use %s simultaneous downloads, progress will be shown" % nb_conn, 
                  "after each completed file but not necessarily in album's order **")

            if re.search(r'/artist/.*', arg):
                download_artist(arg, base_path)
            elif re.search(r'/album/.*', arg):
                download_album(arg, base_path)
            else:
                print("** Error: unable to recognize url, it should contain '/artist/' or '/album/'! **")

        except Exception as e:
            print("** Error: Cannot download URL: %s\n\t%s **" % (arg, e), file=sys.stderr)

if __name__ == "__main__":
    main()
