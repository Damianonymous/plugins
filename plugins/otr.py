import logging
import re

from streamlink.plugin import Plugin
from streamlink.plugin.api import useragents
from streamlink.plugin.api.utils import itertags
from streamlink.stream import HLSStream

log = logging.getLogger(__name__)


class OTR(Plugin):

    _url_re = re.compile(r'^https?://otr-online\.ru/online/?$')

    @classmethod
    def can_handle_url(cls, url):
        return cls._url_re.match(url) is not None

    def _get_streams(self):
        log.debug('Version 2018-07-12')
        log.info('This is a custom plugin. '
                 'For support visit https://github.com/back-to/plugins')
        self.session.http.headers.update({'User-Agent': useragents.FIREFOX})

        res = self.session.http.get(self.url)
        iframe_res = ''
        for iframe in itertags(res.text, 'iframe'):
            log.debug('Found iframe: {0}'.format(iframe))
            if iframe.attributes.get('id') == 'videoFrame':
                iframe_res = self.session.http.get(iframe.attributes['src'])
                break

        if not iframe_res:
            log.debug('No iframe found.')
            return

        xml_url = ''
        for span in itertags(iframe_res.text, 'span'):
            if span.attributes.get('class') == 'webcaster-player':
                xml_url = span.attributes['data-config']
                xml_url = re.sub(r'^config=(.*)', r'\1', xml_url)
                break

        if not xml_url:
            log.debug('No xml_url found.')
            return

        res = self.session.http.get(xml_url)
        root = self.session.http.xml(res, ignore_ns=True)

        for child in root.findall('./video_hd'):
            log.debug('Found video_hd')
            res = self.session.http.get(child.text)
            root = self.session.http.xml(res, ignore_ns=True)
            for child in root.findall('./iphone/track'):
                log.debug('Found iphone/track')
                hls_url = child.text
                log.debug('URL={0}'.format(hls_url))
                streams = HLSStream.parse_variant_playlist(self.session,
                                                           hls_url)
                if not streams:
                    return {'live': HLSStream(self.session, hls_url)}
                else:
                    return streams


__plugin__ = OTR
