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
import traceback
from multiprocessing import Pool
from bs4 import BeautifulSoup

version = 5.1

def script_help(version, script_name):
    description = "Python script to download albums from http://musicmp3spb.org, version %s." % version
    help_string = description + """

------------------------------------------------------------------------------------------------------------------
################## To download an album, give it an url with '/album/' in it #####################################
------------------------------------------------------------------------------------------------------------------
user@computer:/tmp$ %s [-p /path] http://musicmp3spb.org/album/cueille_le_jour.html
** We will try to use 6 simultaneous downloads, progress will be shown **
** after each completed file but not necessarily in album's order. **

Artist: Carpe Diem
Album: Cueille Le Jour
Year: 1976
cover.jpg                                                 00.07 of 00.07 MB [100%%]
02-naissance.mp3                                          07.83 of 07.83 MB [100%%]
01-couleurs.mp3                                           49.59 of 49.59 MB [100%%]
[...]

It will create an "Artist - Album" directory in the path given as argument (or else in current
 directory if not given), and download all songs and covers available on that page.


------------------------------------------------------------------------------------------------------------------
################## To download all albums from an artist, give it an url with '/artist/' in it ###################
------------------------------------------------------------------------------------------------------------------

user@computer:/tmp$ %s [-p /path] http://musicmp3spb.org/artist/carpe_diem.html
** We will try to use 3 simultaneous downloads, progress will be shown **
** after each completed file but not necessarily in album's order. **
** Warning: we are going to download all albums from this artist! **

Artist: Carpe Diem
Album: Cueille Le Jour
Year: 1976
cover.jpg                                                 00.07 of 00.07 MB [100%%]
02-naissance.mp3                                          07.83 of 07.83 MB [100%%]
01-couleurs.mp3                                           49.59 of 49.59 MB [100%%]
[...]

Artist: Carpe Diem
Album: En Regardant Passer Le Temps
Year: 1975
cover.jpg                                                 00.08 of 00.08 MB [100%%]
cover1.jpg                                                00.03 of 00.03 MB [100%%]
01-voyage_du_non-retour.mp3                               08.92 of 08.92 MB [100%%]
02-reincarnation.mp3                                      29.60 of 29.60 MB [100%%]
[...]


It will iterate on all albums of this artist.


------------------------------------------------------------------------------------------------------------------
################# Command line help ##############################################################################
------------------------------------------------------------------------------------------------------------------

For more info, see https://github.com/damsgithub/musicmp3spb-3.py


""" % (script_name, script_name)
    return help_string


def to_MB(a_bytes):
    return a_bytes / 1024. / 1024.


def check_os():
    if sys.platform.startswith('win'):
        return "win"
    else:
        return "unix"


def color_message(msg, color):
    if (check_os() == "win"):
        os.system('') # enables VT100 Escape Sequence for WINDOWS 10 Ver. 1607
    colors = {}
    colors['yellow']       = "\033[0;33m"
    colors['lightyellow']  = "\033[1;33m"
    colors['red']          = "\033[0;31m"
    colors['lightred']     = "\033[1;31m"
    colors['green']        = "\033[0;32m"
    colors['lightgreen']   = "\033[1;32m"
    colors['magenta']      = "\033[0;35m"
    colors['clear']        = "\033[0;39m"
    print(colors[color] + msg + colors['clear'])

   
def spinning_wheel():
    while True:
        for cursor in '|/-\\':
            yield cursor


def dl_status(file_name, dlded_size, real_size):
    status = r'%-50s        %05.2f of %05.2f MB [%3d%%]' % \
        (file_name, to_MB(dlded_size), to_MB(real_size), dlded_size * 100. / real_size)
    return status


def dl_cover(page_soup, url, debug, socks_proxy, socks_port, timeout):
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
            image['src'] = get_base_url(url, debug) + image['src']
        if debug: print("image: %s" % image['src'])

        image_name = "cover"
        if image_num > 0 :
            image_name = image_name + str(image_num)

        download_file(image['src'], image_name + ".jpg", debug, socks_proxy, socks_port, timeout)

        image_num += 1

    if (image_num == 0):
        color_message("** No cover found for this album **", "yellow")


def get_base_url(url, debug):
    # get website base address to preprend it to images, songs and albums relative urls'
    base_url = url.split('//', 1)
    base_url = base_url[0] + '//' + base_url[1].split('/', 1)[0]
    if debug > 1: print("base_url: %s" % base_url)
    return base_url


def open_url(url, socks_proxy, socks_port, timeout, data):
    if socks_proxy and socks_port:
        socks.set_default_proxy(socks.SOCKS5, socks_proxy, socks_port)
        socket.socket = socks.socksocket

    while True:
        try:
            u = urllib.request.urlopen(url, data, timeout=timeout)
            redirect = u.geturl()
            if re.search(r'/404.*', redirect):
                color_message("** Page not found (404), aborting on url: %s **" % url, "lightred")
                u = None
        except (urllib.error.HTTPError) as e:
            color_message("** Connection problem (%s), reconnecting **" % e.reason, "yellow")
            time.sleep(random.randint(2,5))
            continue
        except (socket.timeout, socket.error, ConnectionError) as e:
            color_message("** Connection problem (%s), reconnecting **" % str(e), "yellow")
            time.sleep(random.randint(2,5))
            continue
        except urllib.error.URLError as e:
            if re.search('timed out', str(e.reason)):
                # on linux "timed out" is a socket.timeout exception, 
                # on Windows it is an URLError exception....
                color_message("** Connection problem (%s), reconnecting **" % e.reason, "yellow")
                time.sleep(random.randint(2,5))
                continue
            else:
                color_message("** URLError exception (%s), aborting **" % e.reason, "lightred")
                u = None
        except Exception as e:
                color_message("** Exception: aborting (%s) with error: %s **" % (url, str(e)), "lightred")
                u = None

        return u


def get_page_soup(url, data, debug, socks_proxy, socks_port, timeout):
    page = open_url(url, socks_proxy, socks_port, timeout, data=data)
    if not page:
        return None
    page_soup = BeautifulSoup(page, "html.parser", from_encoding=page.info().get_param('charset'))
    if debug > 1: print("page_soup: %s" % page_soup)
    page.close()
    return page_soup


def prepare_album_dir(page_content, base_path, debug):
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
    #else:
    #    year = input("Unable to get ALBUM YEAR. Please enter here (may leave blank): ")

    if year:
        album_dir = artist + " - " + title + " (" + year + ")"
    else:
        album_dir = artist + " - " + title

    album_dir = os.path.normpath(base_path + os.sep + sanitize_path(album_dir))
    if debug: print("Album's dir: %s" % (album_dir))

    if not os.path.exists(album_dir):
        os.mkdir(album_dir)

    return album_dir


def sanitize_path(path):
    chars_to_remove = str.maketrans('/\\?*|":><', '         ')
    return path.translate(chars_to_remove)


def download_file(url, file_name, debug, socks_proxy, socks_port, timeout):
    process_id = os.getpid()
    try:
        real_size = -1
        partial_dl = 0
        dlded_size = 0
    
        if os.path.exists(file_name):
            dlded_size = os.path.getsize(file_name)
        if (dlded_size <= 8192):
            # we may have downloaded an "Exceed the download limit" (Превышение лимита скачивания) page 
            # instead of the song, restart at beginning.
            dlded_size = 0

    
        req = urllib.request.Request(url)
        u = open_url(req, socks_proxy, socks_port, timeout, data=None)
        if not u:
            return -1


        i = 0
        while (i < 5):
            try:
                real_size = int(u.info()['content-length'])
                if real_size <= 8192:
                   # we got served an "Exceed the download limit" (Превышение лимита скачивания) page, 
                   # retry without incrementing counter
                   continue
                else:
                   # we got the size, exit this loop
                   break
            except Exception as e:
                if (i == 4):
                    color_message("** Unable to get the real size of %s from the server because: %s. **" 
                                  % (file_name, str(e)), "yellow")
                    break # real_size == -1
                else:
                    i += 1
                    if debug: print("%s problem while getting content-length: %s, retrying" 
                                    % (process_id, str(e)), file=sys.stderr)
                    continue
 

        # find where to start the file download (continue or start at beginning)
        if (0 < dlded_size < real_size):
            # file incomplete, we need to resume download
            u.close()
            req = urllib.request.Request(url, headers={'Range': 'bytes=%s-%s' % (dlded_size, real_size)})
            u = open_url(req, socks_proxy, socks_port, timeout, data=None)
            if not u: return -1
    
            # test if the server supports the Range header
            if (u.getcode() == 206):
                partial_dl = 1
            else:
                color_message("** Range/partial download is not supported by server, restarting download at beginning **", "yellow")
                dlded_size = 0
    
        elif (dlded_size == real_size):
            # file already completed, skipped
            color_message("%s" % dl_status(file_name, dlded_size, real_size), "green")
            u.close()
            return
        elif (dlded_size > real_size):
            # we got a problem, restart download
            color_message("** The real size of %s could not be found or an other problem occured, retrying **" % file_name, "yellow")
            u.close()
            return -1
    

        # append or truncate
        if partial_dl:
            f = open(file_name, 'ab+')
        else:
            f = open(file_name, 'wb+')
    
        # get the file
        block_sz = 8192
        #spin = spinning_wheel()
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
            color_message("%s (file downloaded, but could not verify if it is complete)" 
                   % dl_status(file_name, dlded_size, real_size), "yellow")
        elif (real_size == dlded_size):
            color_message("%s" # file downloaded and complete
                   % dl_status(file_name, dlded_size, real_size), "green")
        elif (dlded_size < real_size):
            color_message("%s (file download incomplete, retrying)" 
                   % dl_status(file_name, dlded_size, real_size), "yellow")
            u.close()
            f.close()
            return -1
    
        #sys.stdout.write('\n')
        u.close()
        f.close()
    except KeyboardInterrupt as e:
        if debug: print("** %s : download_file: keyboard interrupt detected **" % process_id, file=sys.stderr)
        raise e
    except Exception as e:
        color_message('** Exception caught in download_file(%s,%s) with error: "%s". We will continue anyway. **' 
               % (url, file_name, str(e)), "yellow")
        traceback.print_stack(file=sys.stderr)
        pass


def download_song(params):
    (url, debug, socks_proxy, socks_port, timeout) = params
    process_id = os.getpid()

    while True: # continue until we have the song
        try:
            if debug: print("%s: downloading song from %s" % (process_id, url))
            file_name = ""
        
            page_soup = get_page_soup(url, str.encode(''), debug, socks_proxy, socks_port, timeout)
            if not page_soup: 
                if debug: print("** %s: Unable to get song's page soup, retrying **" % process_id, file=sys.stderr)
                continue
        
            # get the filename
            for form in page_soup.find_all('form'):
                if re.match(r'/file/.*', form.attrs['action']):
                    break
            if debug > 1: print("form_attr: " + form.attrs['action'])
        
            for link in page_soup.find_all('a', href=True):
                if re.match(form.attrs['action'], link['href']):
                    file_name = link.contents[0]
                    break
            if file_name != "":
                if debug: print("%s: got_filename: %s" % (process_id, file_name))
            else:
                color_message("** %s: Cannot find filename for: %s , retrying **" % (process_id, link['href']), "yellow")
                continue
        
            # we need to re-submit the same page with an hidden input value to get the real link
            submit_value = page_soup.find('input', {'name': 'robot_code'}).get('value')
            if debug: print("%s: submit_value: %s" % (process_id, submit_value))
        
            data = urllib.parse.urlencode([('robot_code', submit_value)])
        
            response = open_url(url, socks_proxy, socks_port, timeout, data=None)
            if not response:
                color_message("** %s: Error: Unable to submit form for %s, skipping song **" % (process_id, file_name), "lightred")
                return
            real_link = response.geturl()
            response.close()
            response_soup = get_page_soup(real_link, str.encode(data), debug, socks_proxy, socks_port, timeout)
            if not response_soup:
                color_message("** %s: Error: Unable to get song's page soup (2), skipping song **" % process_id, "lightred")
                return
        
            for song_link in response_soup.find_all('a', href=True):
                if re.match(r'http://tempfile.ru/download/.*', song_link['href']):
                    break
            if song_link['href'] != "" and song_link['href'] != "/":
                if debug: print("%s: song_link: %s" % (process_id, song_link['href']))
            else:
                color_message("** %s: Cannot find song's real link for: %s, retrying **" % (process_id, file_name), "yellow")
                if debug > 1: print("** %s: response_soup %s" % (process_id, response_soup))
                continue
        
            ret = download_file(song_link['href'], file_name, debug, socks_proxy, socks_port, timeout)
            if ret == -1:
                color_message("** %s: Problem detected while downloading %s, retrying **" % (process_id, file_name), "yellow")
                continue
            else:
                break
        except KeyboardInterrupt:
            if debug: print("** %s: keyboard interrupt detected, finishing process **" % process_id, file=sys.stderr)
            # just return, see: 
            # http://jessenoller.com/2009/01/08/multiprocessingpool-and-keyboardinterrupt/
            return
        except Exception as e:
            color_message('** %s: Exception caught in download_song(%s,%s) with error: "%s", retrying **'
                   % (process_id, url, file_name, str(e)), "yellow")
            traceback.print_stack(file=sys.stderr)
            pass



def download_album(url, base_path, debug, socks_proxy, socks_port, timeout, nb_conn):
    page_soup = get_page_soup(url, str.encode(''), debug, socks_proxy, socks_port, timeout)
    if not page_soup:
        if debug: print("** Unable to get album's page soup **", file=sys.stderr)
        return
    page_content = str(page_soup)
    if debug > 1: print(page_content)

    album_dir = prepare_album_dir(page_content, base_path, debug)

    os.chdir(album_dir)
 
    dl_cover(page_soup, url, debug, socks_proxy, socks_port, timeout)

    # create list of album's songs
    songs_links = []
    title_regexp = re.compile('.*Скачать mp3.*', re.IGNORECASE)
    for link in page_soup.find_all('a', href=True, title=True):
        if not re.match('/download/.*', link['href']):
            continue

        if title_regexp.match(link['title']):
            # prepend base url if necessary
            if re.match(r'^/', link['href']):
                link['href'] = get_base_url(url, debug) + link['href']
            songs_links.append(link['href'])

    if not songs_links:
        color_message("** Unable to detect any song links, skipping this album/url **", "lightred")
    else:
        # we launch the threads to do the downloads
        pool = Pool(processes=nb_conn)

        # pool.map accepts only one argument for the function call, so me must aggregate all in one
        params = [(url, debug, socks_proxy, socks_port, timeout) for url in songs_links]
        try:
            pool.map(download_song, params)
            pool.close()
            pool.join()
        except KeyboardInterrupt as e:
            color_message("** Program interrupted by user, exiting! **", "lightred")
            pool.terminate()
            pool.join()
            sys.exit(1)

    os.chdir('..')
    print("ALBUM DOWNLOAD FINISHED")


def download_artist(url, base_path, debug, socks_proxy, socks_port, timeout, nb_conn):
    page_soup = get_page_soup(url, str.encode(''), debug, socks_proxy, socks_port, timeout)
    if not page_soup:
        if debug: print("** Unable to get artist's page soup **", file=sys.stderr)
        return 

    color_message("** Warning: we are going to download all albums from this artist! **", "lightyellow")

    albums_links = []
    for link in page_soup.find_all('a', href=True):
        if re.match(r'/album/.*', link['href']):
            # most of album's links appear 2 times, we need to de-duplicate.
            if link['href'] not in albums_links:
                albums_links.append(link['href'])

    for album_link in albums_links:
            download_album(get_base_url(url, debug) + album_link, base_path, 
                           debug, socks_proxy, socks_port, timeout, nb_conn)
    print("")
    print("ARTIST DOWNLOAD FINISHED")
 

def main():
    global version
    debug = 0
    socks_proxy = ""
    socks_port = ""
    timeout = 10
    nb_conn = 3
    script_name = os.path.basename(sys.argv[0])

    parser = argparse.ArgumentParser(description=script_help(version, script_name), add_help=True, 
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument(
        "-d", "--debug", type=int, choices=range(0,3), default=0, help="Debug verbosity: 0, 1, 2" )
    parser.add_argument(
        "-s", "--socks", type=str, default=None, help='Socks proxy: "address:port" without "http://"')
    parser.add_argument(
        "-t", "--timeout", type=int, default=10, help='Timeout for HTTP connections in seconds')
    parser.add_argument(
        "-n", "--nb_conn", type=int, default=3, help='Number of simultaneous downloads (max 3 for tempfile.ru)')
    parser.add_argument(
        "-p", "--path", type=str, default=".", help="Base directory in which album(s) will be"
                                                    " downloaded. Defaults to current directory.")
    parser.add_argument(
        "-v", "--version", action='version', version='%(prog)s, version: '+str(version))

    parser.add_argument("url", action='store', help="URL of album or artist page")
    args = parser.parse_args()

    debug = int(args.debug)
    if debug: print("Debug level: %s" % debug)

    nb_conn = int(args.nb_conn)
    timeout = int(args.timeout)

    if (args.socks):
        (socks_proxy, socks_port) = args.socks.split(':')
        if debug: print("proxy socks: %s %s" % (socks_proxy, socks_port))
        if not socks_port.isdigit():
            color_message("** Error in your socks proxy definition, exiting. **", "lightred")
            sys.exit(1)
        socks_port = int(socks_port)

    try:
        print("** We will try to use %s simultaneous downloads, progress will be shown **" % nb_conn)
        print("** after each completed file but not necessarily in album's order. **")

        # modification of global variables do not work correctly under windows with multiprocessing,
        # so I have to pass all these parameters to these functions...
        if re.search(r'/artist/.*', args.url):
            download_artist(args.url, args.path, debug, socks_proxy, socks_port, timeout, nb_conn)
        elif re.search(r'/album/.*', args.url):
            download_album(args.url, args.path, debug, socks_proxy, socks_port, timeout, nb_conn)
        else:
            color_message("** Error: unable to recognize url, it should contain '/artist/' or '/album/'! **", "lightred")

    except Exception as e:
        color_message("** Error: Cannot download URL: %s, reason: %s **" % (args.url, str(e)), "lightred")
        traceback.print_stack(file=sys.stderr)

if __name__ == "__main__":
    main()

