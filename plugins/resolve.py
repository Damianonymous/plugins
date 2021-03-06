# -*- coding: utf-8 -*-
import logging
import re

from streamlink import NoPluginError, NoStreamsError
from streamlink.exceptions import FatalPluginError
from streamlink.compat import unquote, urljoin, urlparse
from streamlink.plugin import Plugin, PluginArgument, PluginArguments
from streamlink.plugin.api import useragents
from streamlink.plugin.plugin import HIGH_PRIORITY, NO_PRIORITY
from streamlink.stream import HDSStream, HLSStream, HTTPStream, DASHStream
from streamlink.utils import update_scheme
from streamlink.utils.args import comma_list, num

log = logging.getLogger(__name__)


class ResolveCache:
    '''used as temporary session cache
       - ResolveCache.blacklist_path
       - ResolveCache.cache_url_list
       - ResolveCache.whitelist_path
    '''
    pass


class Resolve(Plugin):

    _url_re = re.compile(r'''(resolve://)?(?P<url>.+)''')

    # regex for iframes
    _iframe_re = re.compile(r'''
        <ifr(?:["']\s?\+\s?["'])?ame
        (?!\sname=["']g_iFrame).*?src=
        ["'](?P<url>[^"'\s<>]+)["']
        [^<>]*?>
        ''', re.VERBOSE | re.IGNORECASE | re.DOTALL)

    # regex for playlists
    _playlist_re = re.compile(r'''
        (?:["']|=|&quot;)(?P<url>
            (?<!title=["'])
            (?<!["']title["']:["'])
                [^"'<>\s\;{}]+\.(?:m3u8|f4m|mp3|mp4|mpd)
            (?:\?[^"'<>\s\\{}]+)?)
        (?:\\?["']|(?<!;)\s|>|\\&quot;)
        ''', re.DOTALL | re.VERBOSE)

    # regex for mp3 and mp4 files
    _httpstream_bitrate_re = re.compile(r'''
        (?:_|\.)
        (?:
            (?P<bitrate>\d{1,4})
            |
            (?P<resolution>\d{1,4}p)
        )
        \.mp(?:3|4)
        ''', re.VERBOSE)

    # Regex for: javascript redirection
    _window_location_re = re.compile(r'''
        <script[^<]+window\.location\.href\s?=\s?["']
        (?P<url>[^"']+)["'];[^<>]+
        ''', re.DOTALL | re.VERBOSE)
    _unescape_iframe_re = re.compile(r'''
        unescape\050["']
        (?P<data>%3C(?:
            iframe|%69%66%72%61%6d%65
        )%20[^"']+)["']
        ''', re.IGNORECASE | re.VERBOSE)

    _unescape_hls_re = re.compile(r'''
        unescape\050["']
        (?P<data>%3C(?:
            [^"']+m3u8[^"']+
        )%20[^"']+)["']
        ''', re.IGNORECASE | re.VERBOSE)

    # Regex for obviously ad paths
    _ads_path_re = re.compile(r'''
        (?:/(?:static|\d+))?
        /ads?/?(?:\w+)?
        (?:\d+x\d+)?
        (?:_\w+)?\.(?:html?|php)
        ''', re.VERBOSE)

    # START - _make_url_list
    # Not allowed at the end of the parsed url path
    blacklist_endswith = (
        '.gif',
        '.jpg',
        '.png',
        '.svg',
        '.vtt',
        '/chat.html',
        '/chat',
        '/novideo.mp4',
        '/vidthumb.mp4',
    )
    # Not allowed at the end of the parsed url netloc
    blacklist_netloc = (
        '127.0.0.1',
        'about:blank',
        'abv.bg',
        'adfox.ru',
        'cbox.ws',
        'googletagmanager.com',
        'javascript:false',
    )
    # END - _make_url_list

    arguments = PluginArguments(
        PluginArgument(
            'playlist-max',
            metavar='NUMBER',
            type=num(int, min=0, max=25),
            default=5,
            help='''
            Number of how many playlist URLs of the same type
            are allowed to be resolved with this plugin.

            Default is 5
            '''
        ),
        PluginArgument(
            'playlist-referer',
            metavar='URL',
            help='''
            Set a custom referer URL for the playlist URLs.

            This only affects playlist URLs of this plugin.

            Default URL of the last website.
            '''
        ),
        PluginArgument(
            'blacklist-netloc',
            metavar='NETLOC',
            type=comma_list,
            help='''
            Blacklist domains that should not be used,
            by using a comma-separated list:

              'example.com,localhost,google.com'

            Useful for websites with a lot of iframes.
            '''
        ),
        PluginArgument(
            'blacklist-path',
            metavar='PATH',
            type=comma_list,
            help='''
            Blacklist the path of a domain that should not be used,
            by using a comma-separated list:

              'example.com/mypath,localhost/example,google.com/folder'

            Useful for websites with different iframes of the same domain.
            '''
        ),
        PluginArgument(
            'blacklist-filepath',
            metavar='FILEPATH',
            type=comma_list,
            help='''
            Blacklist file names for iframes and playlists
            by using a comma-separated list:

              'index.html,ignore.m3u8,/ad/master.m3u8'

            Sometimes there are invalid URLs in the result list,
            this can be used to remove them.
            '''
        ),
        PluginArgument(
            'whitelist-netloc',
            metavar='NETLOC',
            type=comma_list,
            help='''
            Whitelist domains that should only be searched for iframes,
            by using a comma-separated list:

              'example.com,localhost,google.com'

            Useful for websites with lots of iframes,
            where the main iframe always has the same hosting domain.
            '''
        ),
        PluginArgument(
            'whitelist-path',
            metavar='PATH',
            type=comma_list,
            help='''
            Whitelist the path of a domain that should only be searched
            for iframes, by using a comma-separated list:

              'example.com/mypath,localhost/example,google.com/folder'

            Useful for websites with different iframes of the same domain,
            where the main iframe always has the same path.
            '''
        ),
    )

    def __init__(self, url):
        super(Resolve, self).__init__(url)
        ''' generates default options
            and caches them into ResolveCache class
        '''
        self.url = update_scheme(
            'http://', self._url_re.match(self.url).group('url'))

        self.html_text = ''
        self.title = None

        # START - cache every used url and set a referer
        if hasattr(ResolveCache, 'cache_url_list'):
            ResolveCache.cache_url_list += [self.url]
            # set the last url as a referer
            self.referer = ResolveCache.cache_url_list[-2]
        else:
            ResolveCache.cache_url_list = [self.url]
            self.referer = self.url
        self.session.http.headers.update({'Referer': self.referer})
        # END

        # START - how often _get_streams already run
        self._run = len(ResolveCache.cache_url_list)
        # END

    @classmethod
    def priority(cls, url):
        '''
        Returns
        - NO priority if the URL is not prefixed
        - HIGH priority if the URL is prefixed
        :param url: the URL to find the plugin priority for
        :return: plugin priority for the given URL
        '''
        m = cls._url_re.match(url)
        if m:
            prefix, url = cls._url_re.match(url).groups()
            if prefix is not None:
                return HIGH_PRIORITY
        return NO_PRIORITY

    @classmethod
    def can_handle_url(cls, url):
        m = cls._url_re.match(url)
        if m:
            return m.group('url') is not None

    def compare_url_path(self, parsed_url, check_list):
        '''compare a parsed url, if it matches an item from a list

        Args:
           parsed_url: an URL that was used with urlparse
           check_list: a list of URLs as a tuple
                       [('foo.bar', '/path/'), ('foo2.bar', '/path/')]

        Returns:
            True
                if parsed_url in check_list
            False
                if parsed_url not in check_list
        '''
        status = False
        for netloc, path in check_list:
            if (parsed_url.netloc.endswith(netloc)
                    and parsed_url.path.startswith(path)):
                status = True
                break
        return status

    def merge_path_list(self, static, user):
        '''merge the static list, with an user list

        Args:
           static (list): static list from this plugin
           user (list): list from an user command

        Returns:
            A new valid list
        '''
        for _path_url in user:
            if not _path_url.startswith(('http', '//')):
                _path_url = update_scheme('http://', _path_url)
            _parsed_path_url = urlparse(_path_url)
            if _parsed_path_url.netloc and _parsed_path_url.path:
                static += [(_parsed_path_url.netloc, _parsed_path_url.path)]
        return static

    def repair_url(self, url, base_url, stream_base=''):
        '''repair a broken url'''
        # remove \
        new_url = url.replace('\\', '')
        # repairs broken scheme
        if new_url.startswith('http&#58;//'):
            new_url = 'http:' + new_url[9:]
        elif new_url.startswith('https&#58;//'):
            new_url = 'https:' + new_url[10:]
        # creates a valid url from path only urls
        # and adds missing scheme for // urls
        if stream_base and new_url[1] is not '/':
            if new_url[0] is '/':
                new_url = new_url[1:]
            new_url = urljoin(stream_base, new_url)
        else:
            new_url = urljoin(base_url, new_url)
        return new_url

    def _make_url_list(self, old_list, base_url, url_type=''):
        '''removes unwanted URLs and creates a list of valid URLs

        Args:
            old_list: list of URLs
            base_url: URL that will get used for scheme and netloc repairs
            url_type: can be ... and is used for ...
                - iframe
                    --resolve-whitelist-netloc
                - playlist
                    Not used
        Returns:
            (list) A new valid list of urls.
        '''
        # START - List for not allowed URL Paths
        # --resolve-blacklist-path
        if not hasattr(ResolveCache, 'blacklist_path'):

            # static list
            blacklist_path = [
                ('bigo.tv', '/show.mp4'),
                ('expressen.se', '/_livetvpreview/'),
                ('facebook.com', '/connect'),
                ('facebook.com', '/plugins'),
                ('haber7.com', '/radyohome/station-widget/'),
                ('static.tvr.by', '/upload/video/atn/promo'),
                ('twitter.com', '/widgets'),
                ('vesti.ru', '/native_widget.html'),
                ('youtube.com', '/['),
            ]

            # merge user and static list
            blacklist_path_user = self.get_option('blacklist_path')
            if blacklist_path_user is not None:
                blacklist_path = self.merge_path_list(
                    blacklist_path, blacklist_path_user)

            ResolveCache.blacklist_path = blacklist_path
        # END

        # START - List of only allowed URL Paths for Iframes
        # --resolve-whitelist-path
        if not hasattr(ResolveCache, 'whitelist_path'):
            whitelist_path = []
            whitelist_path_user = self.get_option('whitelist_path')
            if whitelist_path_user is not None:
                whitelist_path = self.merge_path_list(
                    [], whitelist_path_user)
            ResolveCache.whitelist_path = whitelist_path
        # END

        # sorted after the way streamlink will try to remove an url
        status_remove = [
            'SAME-URL',
            'SCHEME',
            'WL-netloc',
            'WL-path',
            'BL-static',
            'BL-netloc',
            'BL-path',
            'BL-ew',
            'BL-filepath',
            'ADS',
        ]

        new_list = []
        for url in old_list:
            new_url = self.repair_url(url, base_url)
            # parse the url
            parse_new_url = urlparse(new_url)

            # START - removal of unwanted urls
            REMOVE = False
            count = 0

            # status_remove must be updated on changes
            for url_status in (
                    # Removes an already used iframe url
                    (new_url in ResolveCache.cache_url_list),
                    # Allow only an url with a valid scheme
                    (not parse_new_url.scheme.startswith(('http'))),
                    # Allow only whitelisted domains for iFrames
                    # --resolve-whitelist-netloc
                    (url_type == 'iframe'
                     and self.get_option('whitelist_netloc')
                     and parse_new_url.netloc.endswith(tuple(self.get_option('whitelist_netloc'))) is False),
                    # Allow only whitelisted paths from a domain for iFrames
                    # --resolve-whitelist-path
                    (url_type == 'iframe'
                     and ResolveCache.whitelist_path
                     and self.compare_url_path(parse_new_url, ResolveCache.whitelist_path) is False),
                    # Removes blacklisted domains from a static list
                    # self.blacklist_netloc
                    (parse_new_url.netloc.endswith(self.blacklist_netloc)),
                    # Removes blacklisted domains
                    # --resolve-blacklist-netloc
                    (self.get_option('blacklist_netloc')
                     and parse_new_url.netloc.endswith(tuple(self.get_option('blacklist_netloc')))),
                    # Removes blacklisted paths from a domain
                    # --resolve-blacklist-path
                    (self.compare_url_path(parse_new_url, ResolveCache.blacklist_path) is True),
                    # Removes unwanted endswith images and chatrooms
                    (parse_new_url.path.endswith(self.blacklist_endswith)),
                    # Removes blacklisted file paths
                    # --resolve-blacklist-filepath
                    (self.get_option('blacklist_filepath')
                     and parse_new_url.path.endswith(tuple(self.get_option('blacklist_filepath')))),
                    # Removes obviously AD URL
                    (self._ads_path_re.match(parse_new_url.path)),
            ):

                count += 1
                if url_status:
                    REMOVE = True
                    break

            if REMOVE is True:
                log.debug('{0} - Removed: {1}'.format(status_remove[count - 1],
                                                      new_url))
                continue
            # END - removal of unwanted urls

            # Add repaired url
            new_list += [new_url]
        # Remove duplicates
        log.debug('List length: {0} (with duplicates)'.format(len(new_list)))
        new_list = sorted(list(set(new_list)))
        return new_list

    def _unescape_type(self, _re, _type_re):
        '''search for unescaped iframes or m3u8 URLs'''
        unescape_type = _re.findall(self.html_text)
        if unescape_type:
            unescape_text = []
            for data in unescape_type:
                unescape_text += [unquote(data)]
            unescape_text = ','.join(unescape_text)
            unescape_type = _type_re.findall(unescape_text)
            if unescape_type:
                log.debug('Found unescape_type: {0}'.format(
                    len(unescape_type)))
                return unescape_type
        log.trace('No unescape_type')
        return False

    def _window_location(self):
        '''Try to find a script with window.location.href

        Args:
            res_text: Content from self._res_text

        Returns:
            (str) url
              or
            False
                if no url was found.
        '''

        match = self._window_location_re.search(self.html_text)
        if match:
            temp_url = urljoin(self.url, match.group('url'))
            log.debug('Found window_location: {0}'.format(temp_url))
            return temp_url

        log.trace('No window_location')
        return False

    def _resolve_playlist(self, playlist_all):
        ''' create streams '''
        playlist_referer = self.get_option('playlist_referer') or self.url
        self.session.http.headers.update({'Referer': playlist_referer})

        playlist_max = self.get_option('playlist_max') or 5
        count_playlist = {
            'dash': 0,
            'hds': 0,
            'hls': 0,
            'http': 0,
        }
        for url in playlist_all:
            parsed_url = urlparse(url)
            if (parsed_url.path.endswith(('.m3u8'))
                    or parsed_url.query.endswith(('.m3u8'))):
                if count_playlist['hls'] >= playlist_max:
                    log.debug('Skip - {0}'.format(url))
                    continue
                try:
                    streams = HLSStream.parse_variant_playlist(self.session, url).items()
                    if not streams:
                        yield 'live', HLSStream(self.session, url)
                    for s in streams:
                        yield s
                    log.debug('HLS URL - {0}'.format(url))
                    count_playlist['hls'] += 1
                except Exception as e:
                    log.error('Skip HLS with error {0}'.format(str(e)))
            elif (parsed_url.path.endswith(('.f4m'))
                    or parsed_url.query.endswith(('.f4m'))):
                if count_playlist['hds'] >= playlist_max:
                    log.debug('Skip - {0}'.format(url))
                    continue
                try:
                    for s in HDSStream.parse_manifest(self.session, url).items():
                        yield s
                    log.debug('HDS URL - {0}'.format(url))
                    count_playlist['hds'] += 1
                except Exception as e:
                    log.error('Skip HDS with error {0}'.format(str(e)))
            elif (parsed_url.path.endswith(('.mp3', '.mp4'))
                    or parsed_url.query.endswith(('.mp3', '.mp4'))):
                if count_playlist['http'] >= playlist_max:
                    log.debug('Skip - {0}'.format(url))
                    continue
                try:
                    name = 'vod'
                    m = self._httpstream_bitrate_re.search(url)
                    if m:
                        bitrate = m.group('bitrate')
                        resolution = m.group('resolution')
                        if bitrate:
                            name = '{0}k'.format(m.group('bitrate'))
                        elif resolution:
                            name = resolution
                    yield name, HTTPStream(self.session, url)
                    log.debug('HTTP URL - {0}'.format(url))
                    count_playlist['http'] += 1
                except Exception as e:
                    log.error('Skip HTTP with error {0}'.format(str(e)))
            elif (parsed_url.path.endswith(('.mpd'))
                    or parsed_url.query.endswith(('.mpd'))):
                if count_playlist['dash'] >= playlist_max:
                    log.debug('Skip - {0}'.format(url))
                    continue
                try:
                    for s in DASHStream.parse_manifest(self.session,
                                                       url).items():
                        yield s
                    log.debug('DASH URL - {0}'.format(url))
                    count_playlist['dash'] += 1
                except Exception as e:
                    log.error('Skip DASH with error {0}'.format(str(e)))
            else:
                log.error('parsed URL - {0}'.format(url))

    def _res_text(self, url):
        '''Content of a website

        Args:
            url: URL with an embedded Video Player.

        Returns:
            Content of the response
        '''
        try:
            res = self.session.http.get(url, allow_redirects=True)
        except Exception as e:
            if 'Received response with content-encoding: gzip' in str(e):
                headers = {
                    'User-Agent': useragents.FIREFOX,
                    'Accept-Encoding': 'deflate'
                }
                res = self.session.http.get(url, headers=headers, allow_redirects=True)
            elif '403 Client Error' in str(e):
                log.error('Website Access Denied/Forbidden, you might be geo-'
                          'blocked or other params are missing.')
                raise NoStreamsError(self.url)
            elif '404 Client Error' in str(e):
                log.error('Website was not found, the link is broken or dead.')
                raise NoStreamsError(self.url)
            else:
                raise e

        if res.history:
            for resp in res.history:
                log.debug('Redirect: {0} - {1}'.format(resp.status_code, resp.url))
            log.debug('URL: {0}'.format(res.url))
        return res.text

    def settings_url(self):
        '''store custom settings for URLs'''
        o = urlparse(self.url)

        # User-Agent
        _android = []
        _chrome = []
        _ipad = []
        _iphone = [
            'bigo.tv',
        ]

        if self.session.http.headers['User-Agent'].startswith('python-requests'):
            if o.netloc.endswith(tuple(_android)):
                self.session.http.headers.update({'User-Agent': useragents.ANDROID})
            elif o.netloc.endswith(tuple(_chrome)):
                self.session.http.headers.update({'User-Agent': useragents.CHROME})
            elif o.netloc.endswith(tuple(_ipad)):
                self.session.http.headers.update({'User-Agent': useragents.IPAD})
            elif o.netloc.endswith(tuple(_iphone)):
                self.session.http.headers.update({'User-Agent': useragents.IPHONE_6})
            else:
                # default User-Agent
                self.session.http.headers.update({'User-Agent': useragents.FIREFOX})

        # SSL Verification - http.verify
        http_verify = [
            '.cdn.bg',
            'sportal.bg',
        ]
        if (o.netloc.endswith(tuple(http_verify)) and self.session.http.verify):
            self.session.http.verify = False
            log.warning('SSL Verification disabled.')

    def get_title(self):
        if self.title is None:
            if not self.html_text:
                self.html_text = self._res_text(self.url)
            _title_re = re.compile(r'<title>(?P<title>[^<>]+)</title>')
            m = _title_re.search(self.html_text)
            if m:
                self.title = m.group('title')
            if self.title is None:
                # fallback if there is no <title>
                self.title = self.url
        return self.title

    def _get_streams(self):
        self.settings_url()

        if self._run <= 1:
            log.debug('Version 2018-08-19')
            log.info('This is a custom plugin.')
            log.debug('User-Agent: {0}'.format(self.session.http.headers['User-Agent']))

        new_session_url = False

        log.info('  {0}. URL={1}'.format(self._run, self.url))

        # GET website content
        self.html_text = self._res_text(self.url)

        # Playlist URL
        playlist_all = self._playlist_re.findall(self.html_text)

        _p_u = self._unescape_type(self._unescape_hls_re, self._playlist_re)
        if _p_u:
            playlist_all += _p_u

        if playlist_all:
            log.debug('Found Playlists: {0}'.format(len(playlist_all)))
            playlist_list = self._make_url_list(playlist_all,
                                                self.url,
                                                url_type='playlist',
                                                )
            if playlist_list:
                log.info('Found Playlists: {0} (valid)'.format(
                    len(playlist_list)))
                return self._resolve_playlist(playlist_list)
        else:
            log.trace('No Playlists')

        # iFrame URL
        iframe_list = []
        for _iframe_list in (self._iframe_re.findall(self.html_text),
                             self._unescape_type(self._unescape_iframe_re,
                                                 self._iframe_re)):
            if not _iframe_list:
                continue
            iframe_list += _iframe_list

        if iframe_list:
            log.debug('Found Iframes: {0}'.format(len(iframe_list)))
            # repair and filter iframe url list
            new_iframe_list = self._make_url_list(iframe_list,
                                                  self.url,
                                                  url_type='iframe')
            if new_iframe_list:
                number_iframes = len(new_iframe_list)
                if number_iframes == 1:
                    new_session_url = new_iframe_list[0]
                else:
                    log.info('--- IFRAMES ---')
                    for i, item in enumerate(new_iframe_list, start=1):
                        log.info('{0} - {1}'.format(i, item))
                    log.info('--- IFRAMES ---')

                    try:
                        number = int(self.input_ask(
                            'Choose an iframe number from above').split(' ')[0])
                        new_session_url = new_iframe_list[number - 1]
                    except FatalPluginError:
                        new_session_url = new_iframe_list[0]
                    except ValueError:
                        log.error('invalid input answer')
                    except (IndexError, TypeError):
                        log.error('invalid input number')

                    if not new_session_url:
                        new_session_url = new_iframe_list[0]
        else:
            log.trace('No Iframes')

        if not new_session_url:
            # search for window.location.href
            new_session_url = self._window_location()

        if new_session_url:
            # the Dailymotion Plugin does not work with this Referer
            if 'dailymotion.com' in new_session_url:
                del self.session.http.headers['Referer']

            return self.session.streams(new_session_url)

        raise NoPluginError


__plugin__ = Resolve
