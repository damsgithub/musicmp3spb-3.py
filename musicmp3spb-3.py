#!/usr/bin/env python3
# -*- coding: utf-8 -*- 

# Copyright (c) 2016, Sergei Riaguzov (sergeiyyy42@gmail.com), Dams M.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
# OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY
# WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.

import re
import sys
import os
import urllib
from bs4 import BeautifulSoup

#base_path_lin = os.path.normpath("/root/musicmp3spb")
base_path_lin = os.path.normpath(".")
#base_path_win = os.path.normpath("C:/Users/localadmin/Downloads/zic_temp")
base_path_win = os.path.normpath(".")
debug = 1 # 3 levels of verbosity: 0 (none), 1 or 2
version = 3.1

def sanitize_path(path):
    chars_to_remove = str.maketrans('/\\?*|":><', '         ')
    return path.translate(chars_to_remove)


def download_file(url, file_name):
    partial_dl = 0
    dlded_size = 0

    if os.path.exists(file_name):
        dlded_size = os.path.getsize(file_name)

    req = urllib.request.Request(url)
    u = urllib.request.urlopen(req)

    real_size = int(u.info()['content-length'])

    # determine where to start the file download (continue or start at beginning)
    if (0 < dlded_size < real_size):
        req = urllib.request.Request(url, headers={'Range': 'bytes=%s-%s' % (dlded_size, real_size)})
        u = urllib.request.urlopen(req)

        if (u.getcode() == 206):
            partial_dl = 1
        else:
            dlded_size = 0
            if debug: print("Range/partial download is not supported")
    elif (dlded_size == real_size):
        print("Skipping: %s, Total Bytes: %s. Already Completed." % (file_name, real_size))
        return
    elif (dlded_size > real_size):
        print("Error: %s is bigger than original file, we will overwrite it!" % file_name)
        dlded_size = 0

    # append or truncate
    if (partial_dl):
        f = open(file_name, 'ab+')
        print("Resuming: %s at %s, Total Bytes: %s" % (file_name, dlded_size, real_size))
    else:
        f = open(file_name, 'wb+')
        print("Downloading: %s, Total Bytes: %s" % (file_name, real_size))

    # get the file
    block_sz = 8192
    while True:
        buffer = u.read(block_sz)
        if not buffer:
            break

        dlded_size += len(buffer)
        f.write(buffer)
        status = r"%10d  [%3.2f%%]" % (dlded_size, dlded_size * 100. / real_size)
        status = status + chr(8)*(len(status)+1)
        print(status,)

    f.close()


def download_song(url):
    print("Downloading song from %s" % url)
    file_name = ""

    page_open = urllib.request.urlopen(url)
    page_soup = BeautifulSoup(page_open, "html.parser", from_encoding=page_open.info().get_param('charset'))
    page_content = str(page_soup)

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
        print("Error: Cannot find filename for %s" % link['href'], file=sys.stderr)
        return

    # we need to re-submit the same page with an hidden input value to get the real link
    submit_value = page_soup.find('input', {'name': 'robot_code'}).get('value')
    if debug: print("submit_value: %s" % submit_value)

    data = urllib.parse.urlencode([('robot_code', submit_value)])
    if debug: print("url data: " + page_open.geturl() + "?" + data)

    response = urllib.request.urlopen(page_open.geturl(), str.encode(data))
    response_soup = BeautifulSoup(response, "html.parser", from_encoding=response.info().get_param('charset'))
    if debug > 1: print("response: " + str(response_soup))

    for song_link in response_soup.find_all('a', href=True):
        if re.match('http://tempfile.ru/download/.*', song_link['href']):
            break
    if song_link['href'] != "":
        if debug: print("song_link: " + song_link['href'])
    else:
        print("Error: Cannot find song's real link for: %s" % file_name, file=sys.stderr)
        return

    download_file(song_link['href'], file_name)


def download_album(url, base_path):
    # get website base address (we will need it later to preprend it to images and songs relative urls')
    base_url = url.split('//', 1)
    base_url = base_url[0] + '//' + base_url[1].split('/', 1)[0]
    if debug > 1: print("base_url: %s" % base_url)

    # get page content
    page_open = urllib.request.urlopen(url)
    page_soup = BeautifulSoup(page_open, "html.parser", from_encoding=page_open.info().get_param('charset'))
    page_content = str(page_soup)
    if debug > 1: print(page_content)

    # get album infos from html page content
    title_regexp = re.compile('.*Скачать mp3.*', re.IGNORECASE)
    artist = ""
    title = ""
    year = ""
    
    album_infos_re = re.compile('<h1><a href="/artist/.+?.html" title="(.+?) mp3">.+?<div class="Name">\n(.+?)<br\s?/>', re.S)
    album_infos = album_infos_re.search(page_content)

    if not album_infos:
        artist = input("Unable to get ARTIST NAME. Please enter here: ")
        title = input("Unable to get ALBUM NAME. Please enter here: ")
    else:
        artist = album_infos.group(1)
        title = album_infos.group(2)

    print("Artist: %s" % artist)
    print("Titre: %s" % title)

    # Get the year if it is available
    album_infos_re = re.compile('<h1><a href="/artist/.+?.html" title=".+? mp3">.+?<div class="Name">\n.+?<br\s?/>\n<i>(\d+)</i>', re.S)
    album_infos = album_infos_re.search(page_content)

    if album_infos and album_infos.group(1):
        year = album_infos.group(1)
        print("Year: %s" % year)
    else:
        year = input("Unable to get ALBUM YEAR. Please enter here (may leave blank): ")

    # create album's dir and cd to it
    album_dir = sanitize_path(os.path.join(base_path, artist) + " - " + title)
    if debug: print("Album's dir: %s" % album_dir)

    if not os.path.isdir(album_dir) and not os.path.exists(album_dir):
        os.mkdir(album_dir)
    os.chdir(album_dir)
 
    # download album's cover(s)
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
            image['src'] = base_url + image['src']
        if debug: print("image: %s" % image['src'])

        image_name = "cover"
        if image_num > 0 :
            image_name = image_name + str(image_num)

        download_file(image['src'], image_name + ".jpg")

        image_num += 1

    # download album's songs
    for link in page_soup.find_all('a', href=True, title=True):
        if not re.match('/download/.*', link['href']):
            continue

        if title_regexp.match(link['title']):
            url_arr = link['href'].split('/')

            # prepend base url if necessary
            if re.match(r'^/', link['href']):
                link['href'] = base_url + link['href']

            download_song(link['href'])

    # go back to upper dir once the album's download is completed
    os.chdir('..')


def help(version, script_name):
    print(
"""Simple Python script to download albums from http://musicmp3spb.org site, version %s.

Usage:

user@computer:/tmp$ %s 'http://musicmp3spb.org/album/dualism.html' [/local/path]
Downloading song from http://musicmp3spb.org/download/arms_of_the_sea/418ec9e6c514a8fb5a0d071ebd2a208a1387032264
Downloading: 01-arms_of_the_sea.mp3, Bytes: 15730982
      1826816 [11.61%]

Run the script passing it the URL of the album from http://musicmp3spb.org site (in this case it is
http://musicmp3spb.org/album/dualism.html). It will create album directory in the optionnal path argument (or
else in current directory), cd to it and download all songs and covers available on that page.

user@computer:/tmp$ %s -h
Prints this help.
""" % (version, script_name, script_name))


def main():
    if sys.platform.startswith('win'):
        base_path = base_path_win
    else:
        base_path = base_path_lin

    script_name = os.path.basename(sys.argv[0])

    if len(sys.argv) < 2:
        help(version, script_name)
        sys.exit(1)
    elif len(sys.argv) > 2:
        base_path = sys.argv[2]

    arg = sys.argv[1]

    if (arg == '-h') or (arg == '--help'):
        help(version, script_name)
    else:
        try:
            if debug > 1: print("base_path: %s" % base_path)
            download_album(arg, base_path)
        except Exception as e:
            print("Error: Cannot download URL: %s\n\t%s" % (arg, e), file=sys.stderr)

if __name__ == "__main__":
    main()
